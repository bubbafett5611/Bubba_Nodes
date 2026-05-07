from ..models import BubbaMetadata

METADATA_TYPE = "BUBBA_METADATA"


class BubbaMetadataDebug:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "metadata": (METADATA_TYPE,),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("metadata_text",)
    FUNCTION = "debug_metadata"
    CATEGORY = "Bubba Nodes/Metadata"
    OUTPUT_NODE = True
    DESCRIPTION = "Converts Bubba metadata object to pretty JSON text and displays it on the node."

    def debug_metadata(self, metadata):
        normalized = BubbaMetadata.coerce(metadata)
        metadata_text = normalized.to_json(pretty=True)
        return {"ui": {"metadata_text": [metadata_text]}, "result": (metadata_text,)}
