from ..models import BubbaMetadata

METADATA_TYPE = "BUBBA_METADATA"


class BubbaMetadataBundle:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Model/checkpoint name.",
                    },
                ),
                "positive_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Final positive prompt text.",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Final negative prompt text.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": False,
                        "tooltip": "Generation seed.",
                    },
                ),
                "filepath": (
                    "STRING",
                    {
                        "default": "Character/Scene",
                        "multiline": False,
                        "tooltip": "Relative output filepath prefix.",
                    },
                ),
            },
        }

    RETURN_TYPES = (METADATA_TYPE,)
    RETURN_NAMES = ("metadata",)
    FUNCTION = "build_metadata"
    CATEGORY = "Bubba Nodes/Metadata"
    DESCRIPTION = "Bundles generation metadata into a typed metadata object for downstream nodes."

    def build_metadata(self, model_name, positive_prompt, negative_prompt, seed, filepath):
        payload = BubbaMetadata(
            model_name=model_name,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            filepath=filepath,
        )
        return (payload,)
