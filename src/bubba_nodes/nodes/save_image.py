from comfy_api.latest import UI


class BubbaSaveImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "filepath": (
                    "STRING",
                    {
                        "default": "Character/Scene",
                        "tooltip": "Relative output path prefix, e.g. Character/Scene.",
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
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Saves images using the given filepath prefix, with optional preview-only temp mode."

    def save_images(self, images, filepath, preview_only):
        if preview_only:
            return {"ui": UI.PreviewImage(images, cls=None).as_dict()}

        return {
            "ui": UI.ImageSaveHelper.get_save_images_ui(
                images=images,
                filename_prefix=filepath,
                cls=None,
            ).as_dict()
        }
