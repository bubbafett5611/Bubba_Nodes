import time

import comfy.samplers
from nodes import common_ksampler

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value

# TODO(new-node): Add an advanced sampler node with optional highres-fix two-pass sampling and per-pass metadata.
# TODO(optimize): Capture and emit sampler timing breakdown (prep vs denoise) for performance profiling.


class BubbaKSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                        "tooltip": "The random seed used for creating the noise.",
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 20,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "The number of steps used in the denoising process.",
                    },
                ),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                        "tooltip": "The Classifier-Free Guidance scale used during sampling.",
                    },
                ),
                "sampler_name": (
                    comfy.samplers.KSampler.SAMPLERS,
                    {
                        "tooltip": "The sampling algorithm used to generate the image.",
                    },
                ),
                "scheduler": (
                    comfy.samplers.KSampler.SCHEDULERS,
                    {
                        "tooltip": "The scheduler controls how noise is removed across steps.",
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "The amount of denoising applied.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing model, conditioning, VAE, and latent."}),
                "latent_image": (
                    "LATENT",
                    {"tooltip": "Optional latent override. Overrides pipe.latent when connected."},
                ),
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata override. Overrides pipe.metadata when connected.",
                    },
                ),
                "model": (
                    "MODEL",
                    {"tooltip": "Optional model override. Overrides pipe.model when connected."},
                ),
                "vae": (
                    "VAE",
                    {
                        "tooltip": "Optional VAE override. Overrides pipe.vae when connected.",
                    },
                ),
                "positive": (
                    "CONDITIONING",
                    {
                        "tooltip": "Optional positive conditioning override. Overrides pipe.positive when connected.",
                    },
                ),
                "negative": (
                    "CONDITIONING",
                    {
                        "tooltip": "Optional negative conditioning override. Overrides pipe.negative when connected.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "IMAGE", "LATENT", "BUBBA_METADATA", "STRING")
    RETURN_NAMES = ("pipe", "image", "latent", "metadata", "info")
    FUNCTION = "sample"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = "Runs KSampler, outputs latent+info, and updates metadata when provided."

    @staticmethod
    def _format_info(elapsed_seconds, seed, steps, cfg, sampler_name, scheduler, denoise):
        return (
            f"Time: {elapsed_seconds:.3f}s  Seed: {seed}  Steps: {steps}  CFG: {cfg}"
            f"  Sampler: {sampler_name}  Scheduler: {scheduler}  Denoise: {denoise}"
        )

    def sample(
        self,
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
        info = self._format_info(
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
        return (updated_pipe, image, latent, updated_metadata, info)
