from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..utils.paths import sanitize_path_component


class BubbaFilename(IO.ComfyNode):
    """
    Builds a file path string in the format: <character_name>/<scene_name>
    Spaces are replaced with underscores and characters invalid in file paths are removed.
    If sanitization produces an empty string, falls back to "Character" or "Scene".
    """

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaFilename",
            display_name="Bubba Filename Builder",
            category="Bubba Nodes/Workflow",
            description="Combines a character name and scene name into a relative save prefix.",
            inputs=[
                IO.String.Input("character_name", default="Character", tooltip="Output folder name."),
                IO.String.Input("scene_name", default="Scene", tooltip="Output file name."),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
            ],
            outputs=[pipe.Output("pipe"), metadata.Output("metadata"), IO.String.Output("save_prefix")],
        )

    @classmethod
    def execute(cls, character_name, scene_name, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        folder = sanitize_path_component(character_name, "Character")
        filename = sanitize_path_component(scene_name, "Scene")
        save_prefix = f"{folder}/{filename}"
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(save_prefix=save_prefix)
        return IO.NodeOutput(source_pipe.updated(metadata=updated_metadata), updated_metadata, save_prefix)
