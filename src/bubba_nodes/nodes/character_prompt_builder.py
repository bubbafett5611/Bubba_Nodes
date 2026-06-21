from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
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
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing the CLIP to use."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata override. Overrides pipe.metadata when connected.",
                    },
                ),
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "Optional CLIP override. Overrides pipe.clip when connected.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "CONDITIONING", "CONDITIONING", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "positive", "negative", "positive_prompt", "negative_prompt")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Builds positive/negative prompts from character sections and encodes conditioning with CLIP. Returns metadata with prompts and sections."

    def build_prompt(
        self,
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
        pipe=None,
        metadata=None,
        clip=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
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
        positive_prompt, negative_prompt, _ = build_prompts_from_sections(
            sections,
            cleanup=cleanup,
            dedupe=dedupe,
            include_character_in_positive=False,
        )
        positive_conditioning = encode_conditioning(resolved_clip, positive_prompt)
        negative_conditioning = encode_conditioning(resolved_clip, negative_prompt)

        # Update metadata with prompts and sections
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
        updated_pipe = source_pipe.updated(
            clip=resolved_clip,
            positive=positive_conditioning,
            negative=negative_conditioning,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            metadata=updated_metadata,
        )

        return (updated_pipe, updated_metadata, positive_conditioning, negative_conditioning, positive_prompt, negative_prompt)
