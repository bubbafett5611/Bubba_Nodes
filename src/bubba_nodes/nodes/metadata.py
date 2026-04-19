from ..models import BubbaMetadata
from ..utils.prompting import empty_conditioning, encode_conditioning

# TODO(new-node): Add a metadata merge node that combines multiple metadata objects with explicit conflict strategy options.
# TODO(new-feature): Add metadata schema version + migration display in debug output to help long-lived workflows.


METADATA_TYPE = "BUBBA_METADATA"


class BubbaMetadataBundle:
    @classmethod
    def INPUT_TYPES(s):
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
                "sampler_info": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Sampler/settings summary string.",
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

    def build_metadata(self, model_name, sampler_info, positive_prompt, negative_prompt, seed, filepath):
        payload = BubbaMetadata(
            model_name=model_name,
            sampler_info=sampler_info,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            filepath=filepath,
        )
        return (payload,)


class BubbaMetadataDebug:
    @classmethod
    def INPUT_TYPES(s):
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


class BubbaMetadataUpdate:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "metadata": (METADATA_TYPE,),
            },
            "optional": {
                "model_name": ("STRING", {"default": "", "multiline": False, "tooltip": "Override model/checkpoint name when not empty."}),
                "sampler_info": ("STRING", {"default": "", "multiline": True, "tooltip": "Override sampler/settings summary when not empty."}),
                "positive_prompt": ("STRING", {"default": "", "multiline": True, "tooltip": "Override positive prompt when not empty."}),
                "negative_prompt": ("STRING", {"default": "", "multiline": True, "tooltip": "Override negative prompt when not empty."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": False, "tooltip": "Override seed when set_seed is enabled."}),
                "set_seed": ("BOOLEAN", {"default": False, "tooltip": "Enable to overwrite the seed field."}),
                "filepath": ("STRING", {"default": "", "multiline": False, "tooltip": "Override filepath when not empty."}),
                "clip": ("CLIP", {"tooltip": "Optional CLIP to encode positive and negative conditioning outputs from metadata prompts."}),
            },
        }

    RETURN_TYPES = (METADATA_TYPE, "INT", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("metadata", "seed", "positive_conditioning", "negative_conditioning")
    FUNCTION = "update_metadata"
    CATEGORY = "Bubba Nodes/Metadata"
    DESCRIPTION = "Updates selected metadata fields and optionally emits CLIP conditioning for positive/negative prompts."

    def update_metadata(
        self,
        metadata,
        model_name="",
        sampler_info="",
        positive_prompt="",
        negative_prompt="",
        seed=0,
        set_seed=False,
        filepath="",
        clip=None,
    ):
        # TODO(optimize): Replace repetitive field checks with a shared map-based updater to reduce maintenance overhead.
        current = BubbaMetadata.coerce(metadata)
        changes = {}
        if str(model_name or "").strip():
            changes["model_name"] = model_name
        if str(sampler_info or "").strip():
            changes["sampler_info"] = sampler_info
        if str(positive_prompt or "").strip():
            changes["positive_prompt"] = positive_prompt
        if str(negative_prompt or "").strip():
            changes["negative_prompt"] = negative_prompt
        if set_seed:
            changes["seed"] = seed
        if str(filepath or "").strip():
            changes["filepath"] = filepath

        updated = current.updated(**changes)
        if clip is None:
            return (updated, updated.seed, empty_conditioning(), empty_conditioning())

        return (
            updated,
            updated.seed,
            encode_conditioning(clip, updated.positive_prompt),
            encode_conditioning(clip, updated.negative_prompt),
        )
