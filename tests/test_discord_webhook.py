import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import torch
from comfy_api.latest import IO

import src.bubba_nodes.nodes.discord_webhook as discord_node_module
import src.bubba_nodes.server.discord_webhook as discord_server
from src.bubba_nodes.models import BubbaMetadata
from src.bubba_nodes.nodes.discord_webhook import BubbaDiscordWebhook


@pytest.fixture
def discord_paths(tmp_path, monkeypatch):
    profiles_path = tmp_path / "webhook_profiles.json"
    staging_root = tmp_path / "staged"
    monkeypatch.setattr(discord_server, "_profiles_path", lambda: profiles_path)
    monkeypatch.setattr(discord_server, "_staging_root", lambda: staging_root)
    return profiles_path, staging_root


def test_profile_storage_never_exposes_urls(discord_paths):
    profiles_path, _staging_root = discord_paths
    url = "https://discord.com/api/webhooks/123/token-value"

    discord_server.save_profile("default", url)

    assert discord_server.list_profile_names() == ["default"]
    assert json.loads(profiles_path.read_text(encoding="utf-8")) == {"default": url}
    assert discord_server.delete_profile("default") is True
    assert discord_server.list_profile_names() == []


@pytest.mark.parametrize(
    "url",
    [
        "http://discord.com/api/webhooks/123/token",
        "https://example.com/api/webhooks/123/token",
        "https://discord.com/channels/123/456",
    ],
)
def test_profile_rejects_non_discord_webhook_urls(discord_paths, url):
    with pytest.raises(ValueError):
        discord_server.save_profile("default", url)


def test_send_staged_payload_splits_large_batches(discord_paths, monkeypatch, tmp_path):
    discord_server.save_profile("default", "https://discord.com/api/webhooks/123/token")
    sources = []
    for index in range(12):
        source = tmp_path / f"source-{index}.png"
        source.write_bytes(b"png")
        sources.append(source)
    discord_server.replace_staged_payload(
        "42",
        sources,
        {
            "webhook_profile": "default",
            "message": "hello",
            "metadata": BubbaMetadata(model_name="model", seed=7).to_dict(),
            "include_generation_info": True,
        },
    )
    post = MagicMock()
    monkeypatch.setattr(discord_server, "_post_webhook", post)

    result = discord_server.send_staged_payload("42")

    assert result == {"status": "sent", "image_count": 12, "message_count": 2, "profile": "default"}
    assert len(post.call_args_list[0].args[2]) == 10
    assert len(post.call_args_list[1].args[2]) == 2
    assert post.call_args_list[0].args[1]["content"] == "hello"
    assert "content" not in post.call_args_list[1].args[1]


def test_send_staged_payload_can_disable_embed(discord_paths, monkeypatch, tmp_path):
    discord_server.save_profile("default", "https://discord.com/api/webhooks/123/token")
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    discord_server.replace_staged_payload(
        "43",
        [source],
        {
            "webhook_profile": "default",
            "message": "images only",
            "metadata": BubbaMetadata(model_name="model", seed=7).to_dict(),
            "include_embed": False,
        },
    )
    post = MagicMock()
    monkeypatch.setattr(discord_server, "_post_webhook", post)

    discord_server.send_staged_payload("43")

    payload = post.call_args.args[1]
    assert payload == {"content": "images only"}


def test_node_captures_while_disabled_and_updates_pipe(monkeypatch):
    captured = {}

    def fake_replace(staging_id, image_paths, manifest):
        captured.update(staging_id=staging_id, count=len(image_paths), manifest=manifest)

    monkeypatch.setattr(discord_node_module, "replace_staged_payload", fake_replace)
    images = torch.zeros((2, 8, 8, 3), dtype=torch.float32)
    metadata = BubbaMetadata(model_name="model", seed=9)

    node_class = BubbaDiscordWebhook.PREPARE_CLASS_CLONE({"hidden_inputs": {IO.Hidden.unique_id: "17"}})
    result = node_class.execute(
        enabled=False,
        webhook_profile="default",
        include_embed=False,
        images=images,
        metadata=metadata,
    )

    pipe, returned_metadata, info = result.result
    assert captured["staging_id"] == "17"
    assert captured["count"] == 2
    assert captured["manifest"]["metadata"]["seed"] == 9
    assert captured["manifest"]["include_embed"] is False
    assert pipe.image is images
    assert returned_metadata is metadata
    assert "Captured 2 image(s)" in info
    assert result.ui["discord_status"] == ["staged"]


def test_node_auto_send_failure_is_non_fatal(monkeypatch):
    monkeypatch.setattr(discord_node_module, "replace_staged_payload", lambda *_args, **_kwargs: Path("staged"))
    monkeypatch.setattr(discord_node_module, "send_staged_payload", MagicMock(side_effect=RuntimeError("network down")))

    node_class = BubbaDiscordWebhook.PREPARE_CLASS_CLONE({"hidden_inputs": {IO.Hidden.unique_id: "18"}})
    result = node_class.execute(
        enabled=True,
        images=torch.zeros((1, 4, 4, 3), dtype=torch.float32),
    )

    assert result.ui["discord_status"] == ["error"]
    assert "network down" in result.result[2]


def test_node_socket_and_output_order():
    schema = BubbaDiscordWebhook.GET_SCHEMA()

    assert [item.id for item in schema.inputs if item.optional] == ["pipe", "images", "metadata"]
    assert [output.io_type for output in BubbaDiscordWebhook.GET_SCHEMA().outputs] == ["BUBBA_PIPE", "BUBBA_METADATA", "STRING"]
    assert tuple(item.id for item in BubbaDiscordWebhook.GET_SCHEMA().outputs) == ("pipe", "metadata", "info")
    assert BubbaDiscordWebhook.GET_SCHEMA().is_output_node is True
    assert BubbaDiscordWebhook.GET_SCHEMA().display_name == "Bubba Discord Webhook"
    assert IO.Hidden.unique_id in BubbaDiscordWebhook.GET_SCHEMA().hidden
