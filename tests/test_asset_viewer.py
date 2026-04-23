import json
import os
import struct

import pytest
from PIL import Image, PngImagePlugin

from src.bubba_nodes.utils.asset_viewer import (
    AssetRoot,
    build_asset_item,
    find_root_for_path,
    generate_thumbnail_bytes,
    make_unique_destination_path,
    resolve_requested_file,
    resolve_requested_root,
    sanitize_upload_filename,
    scan_assets,
    summarize_metadata,
)


def _write_fake_safetensors(path, metadata):
    payload = {
        "tensor": {
            "dtype": "F16",
            "shape": [1],
            "data_offsets": [0, 2],
        },
        "__metadata__": metadata,
    }
    header = json.dumps(payload).encode("utf-8")
    with open(path, "wb") as handle:
        handle.write(struct.pack("<Q", len(header)))
        handle.write(header)
        handle.write(b"\x00\x00")


def test_summarize_metadata_reads_safetensors_header(tmp_path):
    model_path = tmp_path / "demo_model.safetensors"
    _write_fake_safetensors(model_path, {"ss_sd_model_name": "myModel", "author": "tester"})

    summary = summarize_metadata(".safetensors", str(model_path))

    assert summary["format"] == "safetensors"
    assert "ss_sd_model_name" in summary["keys"]
    assert summary["metadata"]["author"] == "tester"


def test_resolve_requested_root_accepts_key_and_path():
    roots = [AssetRoot(key="loras", label="LoRAs", path=r"C:\models\loras")]

    assert resolve_requested_root("loras", roots) == r"C:\models\loras"
    assert resolve_requested_root(r"C:\models\loras", roots) == r"C:\models\loras"


@pytest.mark.parametrize("requested", ["", None])
def test_resolve_requested_root_defaults_to_first(requested):
    roots = [AssetRoot(key="a", label="A", path=r"C:\root_a"), AssetRoot(key="b", label="B", path=r"C:\root_b")]

    assert resolve_requested_root(requested, roots) == r"C:\root_a"


def test_scan_assets_filters_extension_and_query(tmp_path):
    lora_dir = tmp_path / "loras"
    lora_dir.mkdir()

    one = lora_dir / "hero_v1.safetensors"
    two = lora_dir / "hero_preview.png"
    three = lora_dir / "villain_v2.safetensors"

    _write_fake_safetensors(one, {"ss_tag_frequency": "hero"})
    _write_fake_safetensors(three, {"ss_tag_frequency": "villain"})
    two.write_bytes(b"not a real png")

    assets = scan_assets(
        root=str(lora_dir),
        query="hero",
        extensions=[".safetensors"],
        limit=100,
        include_metadata=True,
    )

    assert len(assets) == 1
    assert assets[0]["name"] == "hero_v1.safetensors"
    assert assets[0]["extension"] == ".safetensors"
    assert os.path.isabs(assets[0]["path"])
    assert assets[0]["metadata"]["format"] == "safetensors"


def test_scan_assets_searches_embedded_bubba_metadata(tmp_path):
    image_dir = tmp_path / "output"
    image_dir.mkdir()
    image_path = image_dir / "sample.png"

    metadata = {
        "model_name": "novaFurryXL",
        "positive_prompt": "cinematic lighting, dragon rider",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
    }
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("bubba_metadata", json.dumps(metadata))
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(image_path, pnginfo=png_info)

    assets = scan_assets(
        root=str(image_dir),
        query="dragon rider",
        extensions=[".png"],
        limit=50,
        include_metadata=True,
    )

    assert len(assets) == 1
    assert assets[0]["name"] == "sample.png"
    assert assets[0]["metadata"]["metadata"]["bubba_metadata"]["model_name"] == "novaFurryXL"


def test_resolve_requested_file_allows_file_inside_root(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    image = root / "example.png"
    image.write_bytes(b"png")

    roots = [AssetRoot(key="input", label="Comfy Input", path=str(root))]
    resolved = resolve_requested_file(str(image), roots)

    assert resolved == str(image.resolve())


def test_resolve_requested_file_blocks_file_outside_root(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    image = tmp_path / "other.png"
    image.write_bytes(b"png")

    roots = [AssetRoot(key="input", label="Comfy Input", path=str(root))]

    with pytest.raises(PermissionError):
        resolve_requested_file(str(image), roots)


def test_scan_assets_supports_offset_pagination(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    for index in range(6):
        (root / f"img_{index}.png").write_bytes(b"png")

    first_page = scan_assets(root=str(root), extensions=[".png"], limit=3, include_metadata=False, offset=0)
    second_page = scan_assets(root=str(root), extensions=[".png"], limit=3, include_metadata=False, offset=3)

    assert len(first_page) == 3
    assert len(second_page) == 3
    first_names = {item["name"] for item in first_page}
    second_names = {item["name"] for item in second_page}
    assert first_names.isdisjoint(second_names)


def test_scan_assets_can_skip_metadata_in_payload(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    image_path = root / "with_meta.png"

    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("bubba_metadata", json.dumps({"model_name": "nova"}))
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(image_path, pnginfo=png_info)

    assets = scan_assets(root=str(root), query="nova", extensions=[".png"], limit=10, include_metadata=False)

    assert len(assets) == 1
    assert assets[0]["name"] == "with_meta.png"
    assert "metadata" not in assets[0]


def test_build_asset_item_includes_metadata_when_requested(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    image_path = root / "example.png"
    Image.new("RGB", (8, 8), color=(4, 5, 6)).save(image_path)

    item = build_asset_item(str(image_path), str(root), include_metadata=True)

    assert item["name"] == "example.png"
    assert item["relative_path"] == "example.png"
    assert item["metadata"]["format"] == "png"


def test_find_root_for_path_returns_matching_root(tmp_path):
    output_root = tmp_path / "output"
    input_root = tmp_path / "input"
    output_root.mkdir()
    input_root.mkdir()

    image_path = output_root / "a.png"
    image_path.write_bytes(b"png")
    roots = [
        AssetRoot(key="input", label="Comfy Input", path=str(input_root)),
        AssetRoot(key="output", label="Comfy Output", path=str(output_root)),
    ]

    matched = find_root_for_path(str(image_path), roots)

    assert matched is not None
    assert matched.key == "output"


def test_generate_thumbnail_bytes_for_png(tmp_path):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (1024, 1024), color=(12, 34, 56)).save(image_path)

    payload = generate_thumbnail_bytes(str(image_path), max_size=128)

    assert payload is not None
    assert payload.startswith(b"\x89PNG")


def test_scan_assets_extracts_generation_from_comfy_prompt_metadata(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    image_path = output_dir / "comfy_saved.png"

    prompt_graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "dream_model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "hero portrait, dramatic lighting"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality"}},
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1234,
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_3m_sde",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
            },
        },
    }

    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("prompt", json.dumps(prompt_graph))
    Image.new("RGB", (8, 8), color=(20, 30, 40)).save(image_path, pnginfo=png_info)

    assets = scan_assets(root=str(output_dir), extensions=[".png"], limit=20, include_metadata=True)

    assert len(assets) == 1
    generation = assets[0]["metadata"]["metadata"]["generation"]
    assert generation["model_name"] == "dream_model.safetensors"
    assert generation["seed"] == 1234
    assert generation["steps"] == 30
    assert generation["sampler_name"] == "dpmpp_3m_sde"
    assert generation["positive_prompt"] == "hero portrait, dramatic lighting"


def test_scan_assets_extracts_generation_from_parameters_text(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    image_path = output_dir / "a1111_like.png"

    parameters_text = (
        "hero in armor, cinematic\n"
        "Negative prompt: blurry, lowres\n"
        "Steps: 25, Sampler: DPM++ 2M Karras, CFG scale: 6.5, Seed: 4242"
    )

    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("parameters", parameters_text)
    Image.new("RGB", (8, 8), color=(50, 60, 70)).save(image_path, pnginfo=png_info)

    assets = scan_assets(root=str(output_dir), extensions=[".png"], limit=20, include_metadata=True)

    assert len(assets) == 1
    generation = assets[0]["metadata"]["metadata"]["generation"]
    assert generation["steps"] == "25"
    assert generation["seed"] == "4242"
    assert generation["cfg"] == "6.5"
    assert generation["positive_prompt"] == "hero in armor, cinematic"
    assert generation["negative_prompt"] == "blurry, lowres"


def test_sanitize_upload_filename_normalizes_name_and_extension():
    assert sanitize_upload_filename("..\\evil?.JPG") == "evil_.jpg"
    assert sanitize_upload_filename("", fallback="capture.png") == "capture.png"
    assert sanitize_upload_filename("preview.unsupported") == "preview.png"


def test_make_unique_destination_path_adds_numeric_suffix(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    first = root / "sample.png"
    first.write_bytes(b"png")

    second_path = make_unique_destination_path(str(root), "sample.png")
    assert second_path.endswith("sample_1.png")

    second_file = root / "sample_1.png"
    second_file.write_bytes(b"png")

    third_path = make_unique_destination_path(str(root), "sample.png")
    assert third_path.endswith("sample_2.png")


def test_scan_assets_returns_deterministic_sorted_order(tmp_path):
    root = tmp_path / "output"
    root.mkdir()

    (root / "zeta.png").write_bytes(b"png")
    (root / "Alpha.png").write_bytes(b"png")
    (root / "mid.png").write_bytes(b"png")

    first = scan_assets(root=str(root), extensions=[".png"], limit=10, include_metadata=False)
    second = scan_assets(root=str(root), extensions=[".png"], limit=10, include_metadata=False)

    first_names = [item["name"] for item in first]
    second_names = [item["name"] for item in second]
    assert first_names == second_names
    assert first_names == ["Alpha.png", "mid.png", "zeta.png"]


def test_scan_assets_skips_metadata_parse_when_filename_matches_query(tmp_path, monkeypatch):
    root = tmp_path / "output"
    root.mkdir()
    image_path = root / "hero_shot.png"
    Image.new("RGB", (8, 8), color=(11, 22, 33)).save(image_path)

    calls = {"count": 0}
    original = summarize_metadata

    def _counted(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("src.bubba_nodes.utils.asset_viewer.summarize_metadata", _counted)

    assets = scan_assets(
        root=str(root),
        query="hero",
        extensions=[".png"],
        limit=10,
        include_metadata=False,
        search_in_metadata=True,
    )

    assert len(assets) == 1
    assert calls["count"] == 0


def test_scan_assets_still_parses_metadata_for_metadata_only_query(tmp_path, monkeypatch):
    root = tmp_path / "output"
    root.mkdir()
    image_path = root / "sample.png"

    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("bubba_metadata", json.dumps({"positive_prompt": "dragon rider"}))
    Image.new("RGB", (8, 8), color=(9, 8, 7)).save(image_path, pnginfo=png_info)

    calls = {"count": 0}
    original = summarize_metadata

    def _counted(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("src.bubba_nodes.utils.asset_viewer.summarize_metadata", _counted)

    assets = scan_assets(
        root=str(root),
        query="dragon rider",
        extensions=[".png"],
        limit=10,
        include_metadata=False,
        search_in_metadata=True,
    )

    assert len(assets) == 1
    assert calls["count"] >= 1
