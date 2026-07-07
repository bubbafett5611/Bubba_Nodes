from comfy_api.latest import IO, UI
from ..models import BubbaMetadata, BubbaPipe

BUBBA_PIPE = IO.Custom("BUBBA_PIPE")
BUBBA_METADATA = IO.Custom("BUBBA_METADATA")


class BubbaMetadataDebug(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaMetadataDebug",
            display_name="Bubba Metadata Debug",
            category="Bubba Nodes/Metadata",
            description="Converts Bubba metadata object to pretty JSON text and displays it on the node.",
            inputs=[
                BUBBA_PIPE.Input("pipe", optional=True, tooltip="Optional incoming pipe containing metadata to debug."),
                BUBBA_METADATA.Input("metadata", optional=True),
            ],
            outputs=[IO.String.Output("metadata_text")],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        normalized = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        metadata_text = normalized.to_json(pretty=True)
        ui = UI.PreviewText(metadata_text).as_dict()
        # Preserve the established frontend key while deriving the payload from the public PreviewText class.
        ui["metadata_text"] = ui["text"]
        return IO.NodeOutput(metadata_text, ui=ui)
