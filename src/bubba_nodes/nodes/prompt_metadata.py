"""Prompt builder that integrates with and updates BubbaMetadata."""

# TODO(new-feature): Add optional style/character preset inputs that expand into sections before prompt assembly.
# TODO(new-node): Add a metadata prompt diff node that compares previous and current sections for iterative tuning.

from ..models import BubbaMetadata
from ..utils.prompting import (
    assemble_prompt_sections,
    build_prompts_from_sections,
    encode_conditioning,
)


class BubbaMetadataPromptBuilder:
    """Builds prompts from sections and adds them to metadata."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Metadata object to update with prompt sections.",
                    },
                ),
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
        }

    RETURN_TYPES = ("BUBBA_METADATA", "STRING", "STRING", "STRING", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("metadata", "positive_prompt", "negative_prompt", "sections", "positive_conditioning", "negative_conditioning")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Builds positive/negative prompts from character sections, encodes conditioning, and updates metadata with sections."

    def build_prompt(
        self,
        metadata,
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
    ):
        # TODO(optimize): Short-circuit CLIP encoding when prompts are unchanged from incoming metadata.
        # Coerce metadata to ensure it's the right type
        current_metadata = BubbaMetadata.coerce(metadata)

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

        # Update metadata with prompts and sections
        updated_metadata = current_metadata.updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            prompt_sections=sections_text,
        )

        positive_conditioning = encode_conditioning(clip, positive_prompt)
        negative_conditioning = encode_conditioning(clip, negative_prompt)

        return (updated_metadata, positive_prompt, negative_prompt, sections_text, positive_conditioning, negative_conditioning)
