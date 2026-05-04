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
    DESCRIPTION = "Converts Bubba metadata object to pretty JSON text for preview/debug nodes."

    def debug_metadata(self, metadata):
        normalized = BubbaMetadata.coerce(metadata)
        return (normalized.to_json(pretty=True),)
