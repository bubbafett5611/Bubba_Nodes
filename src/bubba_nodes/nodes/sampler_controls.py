from __future__ import annotations

from comfy_api.latest import IO

from ..compat.sampling import sampler_names, scheduler_names


class BubbaSamplerControls(IO.ComfyNode):
    """Fan one set of sampler settings out to multiple sampler branches."""

    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaSamplerControls",
            display_name="Bubba Sampler Controls",
            category="Bubba Nodes/Workflow",
            description="Provides shared steps, CFG, sampler, scheduler, and denoise values for multiple samplers.",
            inputs=[
                IO.Int.Input("steps", default=20, min=1, max=10000),
                IO.Float.Input("cfg", default=8.0, min=0.0, max=100.0, step=0.1, round=0.01),
                IO.Combo.Input("sampler_name", options=sampler_names()),
                IO.Combo.Input("scheduler", options=scheduler_names()),
                IO.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
            ],
            outputs=[
                IO.Int.Output("steps"),
                IO.Float.Output("cfg"),
                IO.Combo.Output("sampler_name"),
                IO.Combo.Output("scheduler"),
                IO.Float.Output("denoise"),
            ],
        )

    @classmethod
    def execute(cls, steps, cfg, sampler_name, scheduler, denoise):
        return IO.NodeOutput(int(steps), float(cfg), sampler_name, scheduler, float(denoise))
