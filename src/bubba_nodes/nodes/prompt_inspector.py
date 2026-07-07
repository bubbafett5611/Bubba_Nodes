from comfy_api.latest import IO

from ..models import BubbaPipe
from ..utils.prompting import clean_prompt_value, dedupe_prompt_tokens, split_prompt_tokens
from ..utils.prompt_analysis import find_duplicate_prompt_tokens, find_pair_conflicts


class BubbaPromptInspector(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe = IO.Custom("BUBBA_PIPE")
        autocomplete = lambda group: {"bubba.autocomplete": {"group": group}}
        return IO.Schema(
            node_id="BubbaPromptInspector",
            display_name="Bubba Prompt Inspector",
            category="Bubba Nodes/Prompt",
            description="Analyzes prompts for token count, duplicates, conflicts, and cleaned preview text.",
            inputs=[
                pipe.Input("pipe", optional=True),
                IO.String.Input("positive_prompt", default="", multiline=True, optional=True, extra_dict=autocomplete("positive")),
                IO.String.Input("negative_prompt", default="", multiline=True, optional=True, extra_dict=autocomplete("negative")),
            ],
            outputs=[
                IO.Int.Output("token_count"),
                IO.String.Output("duplicate_tags"),
                IO.String.Output("conflict_warnings"),
                IO.String.Output("formatted_preview"),
            ],
        )

    @staticmethod
    def _clean_parts(text: str) -> list[str]:
        parts = split_prompt_tokens(text)
        cleaned = [clean_prompt_value(part) for part in parts]
        return [part for part in cleaned if part]

    @classmethod
    def execute(cls, pipe=None, positive_prompt=None, negative_prompt=None):
        # TODO(optimize): Add optional fast-path mode that skips duplicate and conflict checks for very long prompts.
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_positive = positive_prompt if positive_prompt is not None else source_pipe.positive_prompt
        resolved_negative = negative_prompt if negative_prompt is not None else source_pipe.negative_prompt
        positive_parts = cls._clean_parts(resolved_positive)
        negative_parts = cls._clean_parts(resolved_negative)

        token_count = len(positive_parts) + len(negative_parts)

        positive_duplicates = find_duplicate_prompt_tokens(positive_parts)
        negative_duplicates = find_duplicate_prompt_tokens(negative_parts)
        duplicate_lines: list[str] = []
        if positive_duplicates:
            duplicate_lines.append(f"positive: {', '.join(positive_duplicates)}")
        if negative_duplicates:
            duplicate_lines.append(f"negative: {', '.join(negative_duplicates)}")
        duplicate_tags = "\n".join(duplicate_lines) if duplicate_lines else "none"

        positive_set = {part.lower() for part in positive_parts}
        negative_set = {part.lower() for part in negative_parts}
        cross_conflicts = sorted(positive_set.intersection(negative_set))

        warning_lines: list[str] = []
        if cross_conflicts:
            warning_lines.append(f"present in both positive and negative: {', '.join(cross_conflicts)}")
        positive_pair_conflicts = find_pair_conflicts(positive_parts)
        if positive_pair_conflicts:
            warning_lines.append(f"positive pair conflicts: {', '.join(positive_pair_conflicts)}")
        negative_pair_conflicts = find_pair_conflicts(negative_parts)
        if negative_pair_conflicts:
            warning_lines.append(f"negative pair conflicts: {', '.join(negative_pair_conflicts)}")
        conflict_warnings = "\n".join(warning_lines) if warning_lines else "none"

        formatted_positive = ", ".join(dedupe_prompt_tokens(positive_parts))
        formatted_negative = ", ".join(dedupe_prompt_tokens(negative_parts))
        formatted_preview = f"Positive: {formatted_positive}\n\nNegative: {formatted_negative}\n\nToken count: {token_count}"

        return IO.NodeOutput(token_count, duplicate_tags, conflict_warnings, formatted_preview)
