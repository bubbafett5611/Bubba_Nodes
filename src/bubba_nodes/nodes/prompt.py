from ..models import BubbaMetadata
from ..utils.prompting import (
    assemble_prompt_sections,
    build_prompts_from_sections,
    encode_conditioning,
)


# TODO(new-node): Add a prompt preset library node that can load/save reusable section sets by character or scene.
# TODO(new-feature): Add token-budget guidance output (per-model limits) to warn before conditioning truncation.


class BubbaCharacterPromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "CLIP used to encode positive and negative conditioning outputs.",
                    },
                ),
                "appearance": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "appearance"},
                        "tooltip": "Face, hair, age, and identifying visual traits.",
                    },
                ),
                "body": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "body"},
                        "tooltip": "Body proportions, physique, and anatomy descriptors.",
                    },
                ),
                "clothing": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "clothing"},
                        "tooltip": "Outfit, accessories, and materials.",
                    },
                ),
                "pose": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "pose"},
                        "tooltip": "Body pose and camera-facing orientation.",
                    },
                ),
                "expression": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "expression"},
                        "tooltip": "Facial expression and emotion.",
                    },
                ),
                "scene": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "scene"},
                        "tooltip": "Environment, lighting, and composition context.",
                    },
                ),
                "style_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "style"},
                        "tooltip": "Style and rendering tags, comma-separated.",
                    },
                ),
                "quality_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "quality"},
                        "tooltip": "Quality/detail tags, comma-separated.",
                    },
                ),
                "negative_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Negative prompt tags, comma-separated.",
                    },
                ),
                "format_mode": (
                    ["booru", "prose", "hybrid"],
                    {
                        "default": "hybrid",
                        "tooltip": "Prompt formatting style for positive output.",
                    },
                ),
                "cleanup": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Normalize spacing and trim separators.",
                    },
                ),
                "dedupe": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove duplicate tags while preserving first occurrence order.",
                    },
                ),
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object to update with prompt sections and prompts.",
                    },
                ),
                "clip_skip": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 128,
                        "tooltip": "Number of CLIP encoder layers to skip (0 = no skip).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "CONDITIONING", "CONDITIONING", "BUBBA_METADATA")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "sections", "positive_conditioning", "negative_conditioning", "metadata")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Builds positive/negative prompts from character sections and encodes conditioning with CLIP. Returns metadata with prompts and sections."

    def build_prompt(
        self,
        clip,
        appearance,
        body,
        clothing,
        pose,
        expression,
        scene,
        style_tags,
        quality_tags,
        negative_tags,
        format_mode,
        cleanup,
        dedupe,
        metadata=None,
        clip_skip=0,
    ):
        sections = assemble_prompt_sections(
            appearance=appearance,
            body=body,
            clothing=clothing,
            pose=pose,
            expression=expression,
            scene=scene,
            style_tags=style_tags,
            quality_tags=quality_tags,
            negative_tags=negative_tags,
            format_mode=format_mode,
        )
        positive_prompt, negative_prompt, sections_text = build_prompts_from_sections(
            sections,
            cleanup=cleanup,
            dedupe=dedupe,
            include_character_in_positive=False,
        )
        positive_conditioning = encode_conditioning(clip, positive_prompt)
        negative_conditioning = encode_conditioning(clip, negative_prompt)

        # Update metadata with prompts and sections
        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            clip_skip=clip_skip,
        )

        return (positive_prompt, negative_prompt, sections_text, positive_conditioning, negative_conditioning, updated_metadata)
