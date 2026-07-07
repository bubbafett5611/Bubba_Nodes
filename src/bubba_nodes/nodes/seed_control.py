from __future__ import annotations

from comfy_api.latest import IO


class BubbaSeedControl(IO.ComfyNode):
    """Expose one shared seed for sampler wiring."""

    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaSeedControl",
            display_name="Bubba Seed Control",
            category="Bubba Nodes/Workflow",
            description="Provides one shared seed for direct connections to multiple samplers.",
            inputs=[
                IO.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True),
            ],
            outputs=[
                IO.Int.Output("seed"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(cls, seed):
        return IO.NodeOutput(int(seed), f"Seed: {int(seed)}")
