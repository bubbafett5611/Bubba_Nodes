import re

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]')


class BubbaFilename:
    """
    Builds a file path string in the format: <character_name>/<scene_name>
    Spaces are replaced with underscores and characters invalid in file paths are removed.
    If sanitization produces an empty string, falls back to "Character" or "Scene".
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "character_name": ("STRING", {
                    "multiline": False,
                    "default": "Character",
                    "tooltip": "Used as the folder name in the output path.",
                }),
                "scene_name": ("STRING", {
                    "multiline": False,
                    "default": "Scene",
                    "tooltip": "Used as the image/file name in the output path.",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filepath",)
    FUNCTION = "build_path"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Combines a character name (folder) and scene name (filename) into a relative file path."

    def build_path(self, character_name, scene_name):
        def sanitize(name, fallback):
            name = name.strip()
            name = name.replace(" ", "_")
            name = INVALID_PATH_CHARS.sub('', name)
            return name or fallback

        folder = sanitize(character_name, "Character")
        filename = sanitize(scene_name, "Scene")
        filepath = f"{folder}/{filename}"
        return (filepath,)
