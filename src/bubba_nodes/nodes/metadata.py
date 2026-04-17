from ..models import BubbaMetadata


METADATA_TYPE = "BUBBA_METADATA"


def _coerce_metadata(metadata) -> BubbaMetadata:
    return BubbaMetadata.coerce(metadata)


def _encode_conditioning(clip, text: str):
    tokens = clip.tokenize(text or "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)

    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
    return [[cond, {"pooled_output": pooled}]]


def _empty_conditioning():
    return [[None, {}]]


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
    CATEGORY = "Bubba Nodes"
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
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Converts Bubba metadata object to pretty JSON text for preview/debug nodes."

    @staticmethod
    def _coerce_metadata(metadata) -> BubbaMetadata:
        return _coerce_metadata(metadata)

    def debug_metadata(self, metadata):
        normalized = self._coerce_metadata(metadata)
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
    CATEGORY = "Bubba Nodes"
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
        current = _coerce_metadata(metadata)
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
            return (updated, updated.seed, _empty_conditioning(), _empty_conditioning())

        return (
            updated,
            updated.seed,
            _encode_conditioning(clip, updated.positive_prompt),
            _encode_conditioning(clip, updated.negative_prompt),
        )
