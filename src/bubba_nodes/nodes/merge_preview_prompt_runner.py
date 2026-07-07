from __future__ import annotations
from comfy_api.latest import IO

from ..models import BubbaCheckpointMerge, BubbaMetadata, BubbaPipe
from ..utils.prompting import clean_prompt_value, empty_conditioning, encode_conditioning


_TEST_CASES = {
    "portrait_detail": {
        "name": "Portrait Detail",
        "positive": "portrait, detailed face, expressive eyes, natural skin texture, soft key light, sharp focus, high detail",
        "negative": "low quality, blurry, distorted face, bad eyes, bad anatomy, extra fingers, watermark, text",
    },
    "full_body_anatomy": {
        "name": "Full Body Anatomy",
        "positive": "full body, standing pose, balanced anatomy, detailed hands, detailed clothing, clean silhouette, studio lighting",
        "negative": "bad anatomy, bad hands, missing fingers, extra limbs, fused limbs, malformed feet, low quality, blurry",
    },
    "dynamic_scene": {
        "name": "Dynamic Scene",
        "positive": "dynamic action pose, cinematic composition, motion, detailed background, dramatic lighting, depth of field",
        "negative": "flat composition, stiff pose, blurry, low detail, messy background, duplicated subject, text, watermark",
    },
    "style_stress": {
        "name": "Style Stress",
        "positive": "highly stylized illustration, cohesive color palette, clean linework, strong shapes, detailed rendering, polished finish",
        "negative": "style inconsistency, muddy colors, rough sketch, unfinished, noisy, jpeg artifacts, low quality",
    },
    "lighting_color": {
        "name": "Lighting Color",
        "positive": "complex lighting, rim light, ambient occlusion, vibrant color contrast, reflective materials, detailed shadows",
        "negative": "overexposed, underexposed, flat lighting, washed out colors, harsh artifacts, noisy shadows, low quality",
    },
    "custom": {
        "name": "Custom",
        "positive": "",
        "negative": "",
    },
}


class BubbaMergePreviewPromptRunner(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        text = lambda name, group: IO.String.Input(name, default="", multiline=True, extra_dict={"bubba.autocomplete": {"group": group}})
        return IO.Schema(
            node_id="BubbaMergePreviewPromptRunner",
            display_name="Bubba Merge Preview Prompt Runner",
            category="Bubba Nodes/Merge",
            description="Outputs repeatable prompt text for previewing checkpoint merge results.",
            inputs=[
                IO.Combo.Input("test_case", options=list(_TEST_CASES), default="portrait_detail"),
                text("custom_positive", "positive"),
                text("custom_negative", "negative"),
                IO.Boolean.Input("append_custom_text", default=False),
                IO.Boolean.Input("cleanup", default=True),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Clip.Input("clip", optional=True),
                IO.Custom("BUBBA_CHECKPOINT_MERGE").Input("checkpoint_merge", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("positive_prompt"),
                IO.String.Output("negative_prompt"),
                IO.String.Output("test_name"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(
        cls,
        test_case,
        custom_positive,
        custom_negative,
        append_custom_text,
        cleanup,
        pipe=None,
        metadata=None,
        clip=None,
        checkpoint_merge=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = clip if clip is not None else source_pipe.clip
        case = _TEST_CASES.get(str(test_case), _TEST_CASES["portrait_detail"])
        test_name = case["name"]

        if test_case == "custom":
            positive_prompt = custom_positive
            negative_prompt = custom_negative
        else:
            positive_parts = [case["positive"]]
            negative_parts = [case["negative"]]
            if append_custom_text:
                positive_parts.append(custom_positive)
                negative_parts.append(custom_negative)
            positive_prompt = ", ".join(part for part in positive_parts if str(part or "").strip())
            negative_prompt = ", ".join(part for part in negative_parts if str(part or "").strip())

        if cleanup:
            positive_prompt = clean_prompt_value(positive_prompt)
            negative_prompt = clean_prompt_value(negative_prompt)

        existing = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        model_name = existing.model_name
        recipe_info = ""
        if checkpoint_merge is not None:
            payload = BubbaCheckpointMerge.coerce(checkpoint_merge)
            model_name = payload.suggested_name or model_name
            recipe_type = payload.recipe.get("type", "unknown")
            recipe_info = f"\nMerge recipe: {recipe_type} ({payload.suggested_name or 'unnamed'})"

        updated_metadata = existing.updated(
            model_name=model_name,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
        if resolved_clip is None:
            positive_conditioning = empty_conditioning()
            negative_conditioning = empty_conditioning()
        else:
            positive_conditioning = encode_conditioning(resolved_clip, positive_prompt)
            negative_conditioning = encode_conditioning(resolved_clip, negative_prompt)

        updated_pipe = source_pipe.updated(
            clip=resolved_clip,
            positive=positive_conditioning,
            negative=negative_conditioning,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            metadata=updated_metadata,
        )
        info = f"{test_name}\nPositive: {positive_prompt}\nNegative: {negative_prompt}{recipe_info}"
        return IO.NodeOutput(
            updated_pipe,
            updated_metadata,
            positive_conditioning,
            negative_conditioning,
            positive_prompt,
            negative_prompt,
            test_name,
            info,
        )
