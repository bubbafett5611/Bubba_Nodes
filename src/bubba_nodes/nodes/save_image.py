import json
from pathlib import Path
from typing import Any, Mapping

from comfy_api.latest import UI
from PIL import Image
from PIL.PngImagePlugin import PngInfo

try:
    import folder_paths
except Exception:  # pragma: no cover - only used inside Comfy runtime
    folder_paths = None

from ..models import BubbaMetadata

# TODO(new-feature): Add sidecar JSON export option for non-PNG outputs to preserve metadata portability.
# TODO(new-node): Add a save manifest node that records every saved file path plus metadata digest for later audit/reload.


_DEFAULT_METADATA_DICT = BubbaMetadata().to_dict()


class BubbaSaveImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "filepath": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Relative output path prefix. Leave blank to use metadata.filepath when metadata is connected.",
                    },
                ),
                "preview_only": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable to save as temp preview images instead of writing to output.",
                    },
                ),
                "save_workflow_metadata": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Enable to embed ComfyUI prompt/workflow metadata into saved PNGs, matching the default Save Image node behavior.",
                    },
                ),
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object. When filepath is blank, metadata.filepath is used.",
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Bubba Nodes/Image/Save"
    DESCRIPTION = "Saves images using filepath or metadata.filepath, with optional preview-only temp mode, optional ComfyUI workflow metadata embedding, and embedded Bubba metadata for PNG files."

    @staticmethod
    def _is_default_metadata(metadata: BubbaMetadata) -> bool:
        return metadata.to_dict() == _DEFAULT_METADATA_DICT

    @staticmethod
    def _resolve_base_dir(image_type: str) -> Path:
        if folder_paths is not None:
            if image_type == "temp" and hasattr(folder_paths, "get_temp_directory"):
                return Path(folder_paths.get_temp_directory())
            if hasattr(folder_paths, "get_output_directory"):
                return Path(folder_paths.get_output_directory())
        return Path.cwd()

    @classmethod
    def _resolve_saved_image_path(cls, item: dict) -> Path | None:
        filename = str(item.get("filename", "")).strip()
        if not filename:
            return None
        subfolder = str(item.get("subfolder", "")).strip()
        image_type = str(item.get("type", "output")).strip() or "output"
        base_dir = cls._resolve_base_dir(image_type)
        return (base_dir / subfolder / filename).resolve()

    @staticmethod
    def _serialize_png_text_value(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value)
        except Exception:
            return None

    @classmethod
    def _build_png_text_entries(
        cls,
        metadata_json: str | None,
        save_workflow_metadata: bool,
        prompt: Any,
        extra_pnginfo: Mapping[str, Any] | None,
    ) -> dict[str, str]:
        entries: dict[str, str] = {}
        if save_workflow_metadata:
            prompt_text = cls._serialize_png_text_value(prompt)
            if prompt_text is not None:
                entries["prompt"] = prompt_text
            if isinstance(extra_pnginfo, Mapping):
                for key, value in extra_pnginfo.items():
                    text_value = cls._serialize_png_text_value(value)
                    if text_value is not None:
                        entries[str(key)] = text_value
        if metadata_json:
            entries["bubba_metadata"] = metadata_json
        return entries

    @staticmethod
    def _embed_metadata_in_png(image_path: Path, text_entries: Mapping[str, str]) -> None:
        if image_path.suffix.lower() != ".png" or not image_path.exists() or not text_entries:
            return

        with Image.open(image_path) as source:
            existing_text = {key: value for key, value in source.info.items() if isinstance(value, str)}
            if all(existing_text.get(str(key)) == value for key, value in text_entries.items()):
                return

            png_info = PngInfo()
            for key, value in existing_text.items():
                png_info.add_text(key, value)
            for key, value in text_entries.items():
                png_info.add_text(key, value)
            source.save(image_path, pnginfo=png_info)

    @classmethod
    def _embed_metadata_in_saved_images(cls, save_result: dict, text_entries: Mapping[str, str]) -> None:
        # TODO(optimize): Parallelize metadata embedding when multiple images are saved in one batch.
        if not text_entries:
            return
        for item in save_result.get("images", []):
            if not isinstance(item, dict):
                continue
            path = cls._resolve_saved_image_path(item)
            if path is None:
                continue
            try:
                cls._embed_metadata_in_png(path, text_entries)
            except Exception:
                # Keep save flow resilient if metadata embedding fails on any file.
                continue

    def save_images(self, images, filepath, preview_only, save_workflow_metadata, metadata=None, prompt=None, extra_pnginfo=None):
        normalized_metadata = BubbaMetadata.coerce(metadata)
        resolved_filepath = (filepath or "").strip() or normalized_metadata.filepath or "Character/Scene"
        has_metadata = not self._is_default_metadata(normalized_metadata)

        if preview_only:
            result = UI.PreviewImage(images, cls=None).as_dict()
            if has_metadata:
                result["metadata_text"] = normalized_metadata.to_json(pretty=True)
            return {"ui": result}

        result = UI.ImageSaveHelper.get_save_images_ui(
                images=images,
                filename_prefix=resolved_filepath,
                cls=None,
            ).as_dict()
        png_text_entries = self._build_png_text_entries(
            normalized_metadata.to_json(pretty=False) if has_metadata else None,
            save_workflow_metadata,
            prompt,
            extra_pnginfo,
        )
        if png_text_entries:
            self._embed_metadata_in_saved_images(result, png_text_entries)
        if has_metadata:
            result["metadata_text"] = normalized_metadata.to_json(pretty=True)
        return {"ui": result}
