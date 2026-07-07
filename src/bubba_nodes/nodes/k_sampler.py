import time
from comfy_api.latest import IO

from ..compat.core_nodes import common_ksampler
from ..compat.sampling import sampler_names, scheduler_names
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value


class BubbaKSampler(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaKSampler",
            display_name="Bubba KSampler",
            category="Bubba Nodes/Generation",
            description="Runs KSampler, decodes when a VAE is available, and updates generation metadata.",
            inputs=[
                IO.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True),
                IO.Int.Input("steps", default=20, min=1, max=10000),
                IO.Float.Input("cfg", default=8.0, min=0.0, max=100.0, step=0.1, round=0.01),
                IO.Combo.Input("sampler_name", options=sampler_names()),
                IO.Combo.Input("scheduler", options=scheduler_names()),
                IO.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01),
                pipe.Input("pipe", optional=True),
                IO.Latent.Input("latent_image", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Model.Input("model", optional=True),
                IO.Vae.Input("vae", optional=True),
                IO.Conditioning.Input("positive", optional=True),
                IO.Conditioning.Input("negative", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                IO.Image.Output("image"),
                IO.Latent.Output("latent"),
                metadata.Output("metadata"),
                IO.String.Output("info"),
            ],
        )

    @staticmethod
    def _format_info(elapsed_seconds, seed, steps, cfg, sampler_name, scheduler, denoise):
        return (
            f"Time: {elapsed_seconds:.3f}s  Seed: {seed}  Steps: {steps}  CFG: {cfg}"
            f"  Sampler: {sampler_name}  Scheduler: {scheduler}  Denoise: {denoise}"
        )

    @classmethod
    def execute(
        cls,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise=1.0,
        pipe=None,
        latent_image=None,
        metadata=None,
        model=None,
        vae=None,
        positive=None,
        negative=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_model = resolve_pipe_value(model, source_pipe.model, "model")
        resolved_latent = resolve_pipe_value(latent_image, source_pipe.latent, "latent")
        resolved_positive = resolve_pipe_value(positive, source_pipe.positive, "positive conditioning")
        resolved_negative = resolve_pipe_value(negative, source_pipe.negative, "negative conditioning")
        resolved_vae = vae if vae is not None else source_pipe.vae
        start_time = time.perf_counter()
        latent = common_ksampler(
            resolved_model,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            resolved_positive,
            resolved_negative,
            resolved_latent,
            denoise=denoise,
        )[0]
        elapsed_seconds = time.perf_counter() - start_time
        info = cls._format_info(
            elapsed_seconds,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
        )
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            sampler_time_seconds=elapsed_seconds,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
        )
        image = None
        if resolved_vae is not None:
            latent_samples = latent["samples"]
            if getattr(latent_samples, "is_nested", False):
                latent_samples = latent_samples.unbind()[0]
            image = resolved_vae.decode(latent_samples)
            if len(image.shape) == 5:
                image = image.reshape(-1, image.shape[-3], image.shape[-2], image.shape[-1])
        updated_pipe = source_pipe.updated(
            model=resolved_model,
            vae=resolved_vae,
            positive=resolved_positive,
            negative=resolved_negative,
            image=image if image is not None else source_pipe.image,
            latent=latent,
            metadata=updated_metadata,
        )
        return IO.NodeOutput(updated_pipe, image, latent, updated_metadata, info)
