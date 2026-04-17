from comfy_api.latest import UI

from ..models import BubbaMetadata


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
    DESCRIPTION = "Saves images using filepath or metadata.filepath, with optional preview-only temp mode."

    def save_images(self, images, filepath, preview_only, metadata=None):
        normalized_metadata = BubbaMetadata.coerce(metadata)
        resolved_filepath = (filepath or "").strip() or normalized_metadata.filepath or "Character/Scene"

        if preview_only:
            result = UI.PreviewImage(images, cls=None).as_dict()
            if normalized_metadata.to_dict() != BubbaMetadata().to_dict():
                result["metadata_text"] = normalized_metadata.to_json(pretty=True)
            return {"ui": result}

        result = UI.ImageSaveHelper.get_save_images_ui(
                images=images,
                filename_prefix=resolved_filepath,
                cls=None,
            ).as_dict()
        if normalized_metadata.to_dict() != BubbaMetadata().to_dict():
            result["metadata_text"] = normalized_metadata.to_json(pretty=True)
        return {"ui": result}
