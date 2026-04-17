import time

import comfy.samplers
from nodes import common_ksampler

from ..models import BubbaMetadata


class BubbaKSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (
                    "MODEL",
                    {"tooltip": "The model used for denoising the input latent."},
                ),
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
                "positive": (
                    "CONDITIONING",
                    {
                        "tooltip": "The conditioning describing the attributes you want to include in the image.",
                    },
                ),
                "negative": (
                    "CONDITIONING",
                    {
                        "tooltip": "The conditioning describing the attributes you want to exclude from the image.",
                    },
                ),
                "latent_image": (
                    "LATENT",
                    {"tooltip": "The latent image to denoise."},
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
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object to update with sampler info and seed.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("LATENT", "STRING", "BUBBA_METADATA")
    RETURN_NAMES = ("LATENT", "INFO", "metadata")
    FUNCTION = "sample"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Runs KSampler, outputs formatted info text, and updates metadata when provided."

    @staticmethod
    def _format_info(elapsed_seconds, seed, steps, cfg, sampler_name, scheduler, denoise):
        return (f"Time: {elapsed_seconds:.3f}s  Seed: {seed}  Steps: {steps}  CFG: {cfg}"
                f"  Sampler: {sampler_name}  Scheduler: {scheduler}  Denoise: {denoise}")

    def sample(
        self,
        model,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        positive,
        negative,
        latent_image,
        denoise=1.0,
        metadata=None,
    ):
        start_time = time.perf_counter()
        latent = common_ksampler(
            model,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            positive,
            negative,
            latent_image,
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
        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            sampler_info=info,
            seed=seed,
        )
        return (latent, info, updated_metadata)
