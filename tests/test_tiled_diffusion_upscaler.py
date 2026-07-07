from unittest.mock import MagicMock

import torch

import src.bubba_nodes.nodes.tiled_diffusion_upscaler as diffusion_module
from src.bubba_nodes.utils.progress import ProgressReporter
from src.bubba_nodes.models import BubbaMetadata, BubbaPipe
from src.bubba_nodes.nodes import BubbaTiledDiffusionUpscaler


class _IdentityVAE:
    def encode(self, pixels):
        return pixels.movedim(-1, 1)

    def decode(self, samples):
        return samples.movedim(1, -1)


class TestBubbaTiledDiffusionUpscaler:
    def test_pipe_image_is_preferred_over_pipe_latent(self, monkeypatch):
        source_image = torch.zeros(1, 32, 48, 3)
        old_latent = {"samples": torch.ones(1, 3, 4, 6)}
        result_image = torch.ones(1, 64, 96, 3)
        model = object()
        vae = _IdentityVAE()
        source_pipe = BubbaPipe(
            image=source_image,
            latent=old_latent,
            model=model,
            vae=vae,
            positive=[],
            negative=[],
            metadata=BubbaMetadata(seed=1),
        )
        initial = MagicMock(return_value=result_image)
        redraw = MagicMock(return_value=(result_image, 4))
        monkeypatch.setattr(diffusion_module, "_initial_pixel_upscale", initial)
        monkeypatch.setattr(diffusion_module, "_run_tiled_redraw", redraw)

        result_pipe, image, latent, metadata, info = BubbaTiledDiffusionUpscaler().execute(
            10,
            12,
            5.5,
            "euler",
            "normal",
            0.2,
            512,
            512,
            2.0,
            32,
            "lanczos",
            pipe=source_pipe,
        )

        assert torch.equal(initial.call_args.args[0], source_image)
        assert redraw.call_args.args[0] is result_image
        assert image is result_image
        assert result_pipe.image is result_image
        assert result_pipe.latent is latent
        assert metadata.seed == 10
        assert "Tiles/passes: 4" in info

    def test_explicit_image_overrides_pipe_image(self, monkeypatch):
        pipe_image = torch.zeros(1, 16, 16, 3)
        explicit_image = torch.ones(1, 16, 16, 3)
        pipe = BubbaPipe(image=pipe_image, model=object(), vae=_IdentityVAE(), positive=[], negative=[])
        initial = MagicMock(return_value=explicit_image)
        monkeypatch.setattr(diffusion_module, "_initial_pixel_upscale", initial)
        monkeypatch.setattr(diffusion_module, "_run_tiled_redraw", lambda image, *args: (image, 1))

        BubbaTiledDiffusionUpscaler().execute(
            1,
            2,
            3.0,
            "euler",
            "normal",
            0.2,
            256,
            256,
            1.0,
            32,
            "bicubic",
            pipe=pipe,
            image=explicit_image,
        )

        assert torch.equal(initial.call_args.args[0], explicit_image)

    def test_region_sampling_changes_only_softly_masked_core(self, monkeypatch):
        working = torch.zeros(1, 16, 24, 3)
        monkeypatch.setattr(diffusion_module, "_sample_pixel_crop", lambda crop, *args: torch.ones_like(crop))

        diffusion_module._process_region(
            working,
            batch_index=0,
            core=(8, 4, 16, 12),
            context_width=16,
            context_height=16,
            mask_blur=0,
            model=object(),
            vae=object(),
            positive=[],
            negative=[],
            seed=7,
            steps=2,
            cfg=3.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=0.2,
        )

        assert torch.all(working[:, 4:12, 8:16] == 1)
        assert torch.all(working[:, :4] == 0)
        assert torch.all(working[:, :, :8] == 0)

    def test_redraw_reuses_same_seed_for_every_tile(self, monkeypatch):
        image = torch.zeros(1, 8, 16, 3)
        seeds = []

        def record_seed(crop, model, vae, positive, negative, seed, *args):
            seeds.append(seed)
            return crop

        monkeypatch.setattr(diffusion_module, "_sample_pixel_crop", record_seed)
        monkeypatch.setattr(ProgressReporter, "update", lambda self, increment=1, **kwargs: None)

        result, count = diffusion_module._run_tiled_redraw(
            image,
            model=object(),
            vae=object(),
            positive=[],
            negative=[],
            seed=42,
            steps=2,
            cfg=3.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=0.2,
            tile_width=8,
            tile_height=8,
            context_padding=2,
            mask_blur=0,
            redraw_mode="linear",
            seam_fix_mode="none",
            seam_fix_denoise=0.1,
            seam_fix_width=2,
            seam_fix_mask_blur=0,
            seam_fix_padding=2,
        )

        assert result.shape == image.shape
        assert count == 2
        assert seeds == [42, 42]

    def test_seam_fix_targets_boundaries(self):
        regions = diffusion_module._seam_regions(1024, 1024, 512, 512, 64, "half_tile_plus_intersections")

        assert (480, 0, 544, 512) in regions
        assert (0, 480, 512, 544) in regions
        assert (480, 480, 544, 544) in regions

    def test_socket_order_and_registration(self):
        schema = BubbaTiledDiffusionUpscaler.GET_SCHEMA()
        required = [item.id for item in schema.inputs if not item.optional]
        optional = [item.id for item in schema.inputs if item.optional]

        assert tuple(required)[:11] == (
            "seed",
            "steps",
            "cfg",
            "sampler_name",
            "scheduler",
            "denoise",
            "tile_width",
            "tile_height",
            "scale_by",
            "overlap",
            "resize_method",
        )
        assert tuple(optional) == ("pipe", "image", "latent", "metadata", "model", "vae", "positive", "negative")
        assert tuple(item.id for item in BubbaTiledDiffusionUpscaler.GET_SCHEMA().outputs) == (
            "pipe",
            "image",
            "latent",
            "metadata",
            "info",
        )
        assert BubbaTiledDiffusionUpscaler.GET_SCHEMA().node_id == "BubbaTiledDiffusionUpscaler"
