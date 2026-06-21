from ..models import BubbaMetadata, BubbaPipe
from ..utils.paths import sanitize_path_component

# TODO(new-node): Add a template-based filename node with date, seed, and model placeholders.
# TODO(optimize): Precompute an optional transliteration/slugify pipeline for consistent cross-platform paths.


class BubbaFilename:
    """
    Builds a file path string in the format: <character_name>/<scene_name>
    Spaces are replaced with underscores and characters invalid in file paths are removed.
    If sanitization produces an empty string, falls back to "Character" or "Scene".
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character_name": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "Character",
                        "tooltip": "Used as the folder name in the output path.",
                    },
                ),
                "scene_name": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "Scene",
                        "tooltip": "Used as the image/file name in the output path.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe to update with the save prefix."}),
                "metadata": ("BUBBA_METADATA", {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."}),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "save_prefix")
    FUNCTION = "build_path"
    CATEGORY = "Bubba Nodes/Workflow"
    DESCRIPTION = "Combines a character name (folder) and scene name (filename) into a relative save prefix."

    def build_path(self, character_name, scene_name, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        folder = sanitize_path_component(character_name, "Character")
        filename = sanitize_path_component(scene_name, "Scene")
        save_prefix = f"{folder}/{filename}"
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(save_prefix=save_prefix)
        return (source_pipe.updated(metadata=updated_metadata), updated_metadata, save_prefix)
