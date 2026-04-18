from pathlib import Path

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
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object. When filepath is blank, metadata.filepath is used.",
                    },
                ),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Saves images using filepath or metadata.filepath, with optional preview-only temp mode and embedded Bubba metadata for PNG files."

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
    def _embed_metadata_in_png(image_path: Path, metadata_json: str) -> None:
        if image_path.suffix.lower() != ".png" or not image_path.exists():
            return

        with Image.open(image_path) as source:
            png_info = PngInfo()
            for key, value in source.info.items():
                if isinstance(value, str):
                    png_info.add_text(key, value)
            png_info.add_text("bubba_metadata", metadata_json)
            source.save(image_path, pnginfo=png_info)

    @classmethod
    def _embed_metadata_in_saved_images(cls, save_result: dict, metadata_json: str) -> None:
        # TODO(optimize): Parallelize metadata embedding when multiple images are saved in one batch.
        for item in save_result.get("images", []):
            if not isinstance(item, dict):
                continue
            path = cls._resolve_saved_image_path(item)
            if path is None:
                continue
            try:
                cls._embed_metadata_in_png(path, metadata_json)
            except Exception:
                # Keep save flow resilient if metadata embedding fails on any file.
                continue

    def save_images(self, images, filepath, preview_only, metadata=None):
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
        if has_metadata:
            metadata_json = normalized_metadata.to_json(pretty=False)
            self._embed_metadata_in_saved_images(result, metadata_json)
            result["metadata_text"] = normalized_metadata.to_json(pretty=True)
        return {"ui": result}
