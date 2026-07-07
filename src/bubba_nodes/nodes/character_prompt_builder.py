from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.prompting import (
    assemble_prompt_sections,
    build_prompts_from_sections,
    encode_conditioning,
)


# TODO(new-node): Add a prompt preset library node that can load/save reusable section sets by character or scene.
# TODO(new-feature): Add token-budget guidance output (per-model limits) to warn before conditioning truncation.


class BubbaCharacterPromptBuilder(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        groups = ["appearance", "body", "clothing", "pose", "expression", "scene", "style", "quality", "negative"]
        names = ["appearance", "body", "clothing", "pose", "expression", "scene", "style_tags", "quality_tags", "negative_tags"]
        inputs = [
            IO.String.Input(name, default="", multiline=True, extra_dict={"bubba.autocomplete": {"group": group}})
            for name, group in zip(names, groups)
        ]
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        inputs += [
            IO.Combo.Input("format_mode", options=["booru", "prose", "hybrid"], default="hybrid"),
            IO.Boolean.Input("cleanup", default=True),
            IO.Boolean.Input("dedupe", default=True),
            pipe.Input("pipe", optional=True),
            metadata.Input("metadata", optional=True),
            IO.Clip.Input("clip", optional=True),
        ]
        return IO.Schema(
            node_id="BubbaCharacterPromptBuilder",
            display_name="Bubba Character Prompt Builder",
            category="Bubba Nodes/Prompt",
            description="Builds character prompts from structured sections and encodes conditioning.",
            inputs=inputs,
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("positive_prompt"),
                IO.String.Output("negative_prompt"),
            ],
        )

    @classmethod
    def execute(
        cls,
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
    ) -> IO.NodeOutput:
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

        return IO.NodeOutput(updated_pipe, updated_metadata, positive_conditioning, negative_conditioning, positive_prompt, negative_prompt)
