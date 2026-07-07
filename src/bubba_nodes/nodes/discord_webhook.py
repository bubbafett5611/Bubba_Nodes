from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..server.discord_webhook import replace_staged_payload, send_staged_payload
from ..utils.image_ops import tensor_sample_to_pil


class BubbaDiscordWebhook(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaDiscordWebhook",
            display_name="Bubba Discord Webhook",
            category="Bubba Nodes/Image/Send",
            description="Captures images and metadata for Discord and optionally sends them automatically.",
            inputs=[
                IO.Boolean.Input("enabled", default=False),
                IO.String.Input("webhook_profile", default="default"),
                IO.String.Input("message", default="", multiline=True),
                IO.Boolean.Input("include_embed", default=True),
                IO.Boolean.Input("include_positive_prompt", default=True),
                IO.Boolean.Input("include_negative_prompt", default=False),
                IO.Boolean.Input("include_generation_info", default=True),
                IO.Boolean.Input("include_loras", default=True),
                IO.Combo.Input("image_format", options=["PNG", "JPEG"], default="PNG"),
                pipe.Input("pipe", optional=True),
                IO.Image.Input("images", optional=True),
                metadata.Input("metadata", optional=True),
            ],
            outputs=[pipe.Output("pipe"), metadata.Output("metadata"), IO.String.Output("info")],
            hidden=[IO.Hidden.unique_id],
            is_output_node=True,
        )

    @staticmethod
    def _save_staging_images(images: Any, image_format: str, directory: Path) -> list[Path]:
        extension = ".jpg" if image_format.upper() == "JPEG" else ".png"
        paths: list[Path] = []
        for index, sample in enumerate(images):
            image = tensor_sample_to_pil(sample)
            path = directory / f"source_{index + 1:03d}{extension}"
            if extension == ".jpg":
                image.convert("RGB").save(path, format="JPEG", quality=95)
            else:
                image.save(path, format="PNG")
            paths.append(path)
        return paths

    @classmethod
    def execute(
        cls,
        enabled=False,
        webhook_profile="default",
        message="",
        include_embed=True,
        include_positive_prompt=True,
        include_negative_prompt=False,
        include_generation_info=True,
        include_loras=True,
        image_format="PNG",
        pipe=None,
        images=None,
        metadata=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_images = resolve_pipe_value(images, source_pipe.image, "image")
        resolved_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_pipe = source_pipe.updated(image=resolved_images, metadata=resolved_metadata)
        staging_id = str(cls.hidden.unique_id if cls.hidden is not None else "").strip()
        if not staging_id:
            raise ValueError("Discord webhook node is missing its ComfyUI node ID.")

        temp_dir = Path(tempfile.mkdtemp(prefix="bubba-discord-"))
        try:
            image_paths = cls._save_staging_images(resolved_images, image_format, temp_dir)
            if not image_paths:
                raise ValueError("Discord webhook received an empty image batch.")
            captured_at = datetime.now(timezone.utc).isoformat()
            manifest = {
                "captured_at": captured_at,
                "webhook_profile": str(webhook_profile or "").strip(),
                "message": str(message or "").strip(),
                "metadata": resolved_metadata.to_dict(),
                "include_embed": bool(include_embed),
                "include_positive_prompt": bool(include_positive_prompt),
                "include_negative_prompt": bool(include_negative_prompt),
                "include_generation_info": bool(include_generation_info),
                "include_loras": bool(include_loras),
            }
            replace_staged_payload(staging_id, image_paths, manifest)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        info = f"Captured {len(image_paths)} image(s) for Discord profile '{webhook_profile}'."
        status = "staged"
        if enabled:
            try:
                result = send_staged_payload(staging_id)
                info = f"Sent {result['image_count']} image(s) to Discord in {result['message_count']} message(s)."
                status = "sent"
            except Exception as error:
                info = f"Discord send failed; the captured images remain available: {error}"
                status = "error"
        return IO.NodeOutput(
            updated_pipe,
            resolved_metadata,
            info,
            ui={"discord_status": [status], "discord_info": [info], "discord_staging_id": [staging_id]},
        )
