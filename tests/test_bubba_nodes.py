#!/usr/bin/env python

"""Tests for `bubba_nodes` package."""

# TODO(optimize): Add parametrized performance-focused tests for prompt cleaning and overlay text wrapping hot paths.
# TODO(new-feature): Add integration tests that validate metadata persistence across save -> load for multi-image batches.

import json
import sys
import types
import asyncio
from unittest.mock import MagicMock

import pytest
from PIL import Image
from comfy_api.latest import UI

import src.bubba_nodes.nodes.save_image as save_image_module
import src.bubba_nodes.nodes.checkpoint_loader as checkpoint_module
import src.bubba_nodes.nodes.prompt_randomizer as prompt_randomizer_module
import src.bubba_nodes.server.autocomplete as autocomplete_server

from src.bubba_nodes.nodes import (
    BubbaFilename,
    BubbaEmptyLatentBySize,
    BubbaLoadImageWithMetadata,
    BubbaCheckpointLoader,
    BubbaComboLoader,
    BubbaLoraLoader,
    BubbaUpscaler,
    BubbaImageCompare,
    BubbaKSampler,
    BubbaDetailer,
    BubbaSaveImage,
    BubbaOverlayFromMetadata,
    BubbaWatermark,
    BubbaMetadataDebug,
    BubbaCharacterPromptBuilder,
    BubbaSimplePromptBuilder,
    BubbaPromptRandomizer,
    BubbaPromptCleaner,
    BubbaPromptInspector,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from src.bubba_nodes.models import BubbaMetadata
from src.bubba_nodes.utils.detailer_masks import (
    bbox_to_mask,
    parse_label_filter,
    plan_crop,
    postprocess_mask,
)
from src.bubba_nodes.utils.detailer_models import discover_detector_models, resolve_detector_model_path
from src.bubba_nodes.utils.detailer_types import DetailerDetection
from src.bubba_nodes.utils.paths import sanitize_relative_save_prefix


class _DummyClip:
    def tokenize(self, text):
        return text

    def encode_from_tokens_scheduled(self, tokens):
        return [[f"COND:{tokens}", {}]]


class TestBubbaFilename:
    def test_basic_path(self):
        node = BubbaFilename()
        (result,) = node.build_path("My Character", "Battle Scene")
        assert result == "My_Character/Battle_Scene"

    def test_invalid_chars_stripped(self):
        node = BubbaFilename()
        (result,) = node.build_path("Hero<>:", "Scene?*")
        assert result == "Hero/Scene"

    def test_empty_character_falls_back(self):
        node = BubbaFilename()
        (result,) = node.build_path("", "Scene")
        assert result == "Character/Scene"

    def test_empty_scene_falls_back(self):
        node = BubbaFilename()
        (result,) = node.build_path("Hero", "")
        assert result == "Hero/Scene"

    def test_only_invalid_chars_falls_back(self):
        node = BubbaFilename()
        (result,) = node.build_path("<>:/\\", "?*|")
        assert result == "Character/Scene"

    def test_metadata(self):
        assert BubbaFilename.RETURN_TYPES == ("STRING",)
        assert BubbaFilename.RETURN_NAMES == ("save_prefix",)
        assert BubbaFilename.FUNCTION == "build_path"
        assert BubbaFilename.CATEGORY == "Bubba Nodes/Workflow"


class TestPathUtilities:
    def test_sanitize_relative_save_prefix_keeps_normal_prefix(self):
        assert sanitize_relative_save_prefix("Hero/Scene_01") == "Hero/Scene_01"

    def test_sanitize_relative_save_prefix_removes_unsafe_path_parts(self):
        assert sanitize_relative_save_prefix("../CON/C:/bad*name/Scene.") == "_CON/C/badname/Scene"

    def test_sanitize_relative_save_prefix_handles_empty_input(self):
        assert sanitize_relative_save_prefix("") == "Character/Scene"


class TestBubbaEmptyLatentBySize:
    def test_resolve_dimensions_default_and_inverted(self):
        width, height = BubbaEmptyLatentBySize._resolve_dimensions("Medium (1344x768)", False)
        assert width == 1344
        assert height == 768

        width, height = BubbaEmptyLatentBySize._resolve_dimensions("Medium (1344x768)", True)
        assert width == 768
        assert height == 1344

    def test_resolve_dimensions_header_raises_error(self):
        with pytest.raises(ValueError, match="Invalid size preset selection"):
            BubbaEmptyLatentBySize._resolve_dimensions("--- 16:9 ---", False)

    def test_build_empty_latent_outputs_shape_and_sizes(self):
        node = BubbaEmptyLatentBySize()
        latent, width, height = node.build_empty_latent("Tiny (896x512)", False, 2)

        assert width == 896
        assert height == 512
        assert "samples" in latent
        assert tuple(latent["samples"].shape) == (2, 4, 64, 112)

    def test_metadata(self):
        assert BubbaEmptyLatentBySize.RETURN_TYPES == ("LATENT", "INT", "INT")
        assert BubbaEmptyLatentBySize.FUNCTION == "build_empty_latent"
        assert BubbaEmptyLatentBySize.CATEGORY == "Bubba Nodes/Generation"


class TestBubbaLoadImageWithMetadata:
    def test_extract_bubba_metadata_from_png_info(self):
        metadata, metadata_text = BubbaLoadImageWithMetadata._extract_bubba_metadata(
            {
                "bubba_metadata": '{"model_name":"modelA","seed":42,"positive_prompt":"hero"}',
            }
        )

        assert isinstance(metadata, BubbaMetadata)
        assert metadata.model_name == "modelA"
        assert metadata.seed == 42
        assert "modelA" in metadata_text

    def test_extract_bubba_metadata_missing_key_returns_default(self):
        metadata, metadata_text = BubbaLoadImageWithMetadata._extract_bubba_metadata({})

        assert isinstance(metadata, BubbaMetadata)
        assert metadata.model_name == ""
        assert metadata.seed == 0
        assert '"model_name": ""' in metadata_text

    def test_load_rgb_image_returns_image_sized_mask(self, tmp_path):
        image_path = tmp_path / "rgb.png"
        Image.new("RGB", (17, 11), color=(10, 20, 30)).save(image_path)

        image, mask, _, _ = BubbaLoadImageWithMetadata().load_image(str(image_path))

        assert tuple(image.shape[1:3]) == (11, 17)
        assert tuple(mask.shape[-2:]) == (11, 17)
        assert mask.sum().item() == 0

    def test_metadata(self):
        assert BubbaLoadImageWithMetadata.RETURN_TYPES == ("IMAGE", "MASK", "BUBBA_METADATA", "STRING")
        assert BubbaLoadImageWithMetadata.FUNCTION == "load_image"
        assert BubbaLoadImageWithMetadata.CATEGORY == "Bubba Nodes/Image/Load"


class TestBubbaCheckpointLoader:
    def test_model_name_in_metadata_is_basename_without_extension(self, monkeypatch):
        fake_loader = MagicMock()
        fake_loader.load_checkpoint.return_value = ("MODEL_OBJ", "CLIP_OBJ", "VAE_OBJ")
        monkeypatch.setattr(checkpoint_module, "CheckpointLoaderSimple", MagicMock(return_value=fake_loader))

        node = BubbaCheckpointLoader()
        _, _, _, checkpoint_name, metadata = node.load_checkpoint_with_name("Illustrious\\anime\\novaAnimeXL_ilV180.safetensors")

        assert checkpoint_name == "Illustrious\\anime\\novaAnimeXL_ilV180.safetensors"
        assert metadata.model_name == "novaAnimeXL_ilV180"

    def test_metadata(self):
        assert BubbaCheckpointLoader.RETURN_TYPES == ("MODEL", "CLIP", "VAE", "STRING", "BUBBA_METADATA")
        assert BubbaCheckpointLoader.FUNCTION == "load_checkpoint_with_name"
        assert BubbaCheckpointLoader.CATEGORY == "Bubba Nodes/Generation"


class TestBubbaKSampler:
    def test_metadata(self):
        assert BubbaKSampler.RETURN_TYPES == ("LATENT", "STRING", "BUBBA_METADATA", "IMAGE")
        assert BubbaKSampler.FUNCTION == "sample"
        assert BubbaKSampler.CATEGORY == "Bubba Nodes/Generation"


class TestBubbaDetailerUtilities:
    def test_discover_detector_models_combines_bbox_and_segm_pt_files(self, tmp_path):
        bbox_dir = tmp_path / "bbox"
        segm_dir = tmp_path / "segm"
        bbox_dir.mkdir()
        segm_dir.mkdir()
        (bbox_dir / "face.pt").write_text("model")
        (bbox_dir / "face.json").write_text("{}")
        (segm_dir / "person.pt").write_text("model")

        assert discover_detector_models(tmp_path) == ["bbox/face.pt", "segm/person.pt"]

    def test_resolve_detector_model_path_validates_prefix_and_file(self, tmp_path):
        bbox_dir = tmp_path / "bbox"
        bbox_dir.mkdir()
        model_path = bbox_dir / "face.pt"
        model_path.write_text("model")

        mode, resolved = resolve_detector_model_path("bbox/face.pt", tmp_path)

        assert mode == "bbox"
        assert resolved == model_path
        with pytest.raises(ValueError, match="Invalid detector model mode"):
            resolve_detector_model_path("other/face.pt", tmp_path)

    def test_discovery_checks_registered_ultralytics_roots_after_models_dir(self, tmp_path, monkeypatch):
        import folder_paths
        import src.bubba_nodes.utils.detailer_models as detailer_models

        empty_models_dir = tmp_path / "empty_models"
        shared_models_root = tmp_path / "shared_models" / "Ultralytics"
        (empty_models_dir / "ultralytics").mkdir(parents=True)
        (shared_models_root / "bbox").mkdir(parents=True)
        model_path = shared_models_root / "bbox" / "face.pt"
        model_path.write_text("model")

        monkeypatch.setattr(folder_paths, "models_dir", str(empty_models_dir), raising=False)
        monkeypatch.setattr(folder_paths, "get_folder_paths", lambda kind: [str(shared_models_root)] if kind == "ultralytics" else [])

        assert detailer_models.discover_detector_models() == ["bbox/face.pt"]
        assert detailer_models.resolve_detector_model_path("bbox/face.pt")[1] == model_path

    def test_discovery_supports_registered_bbox_folder_with_case_variation(self, tmp_path, monkeypatch):
        import folder_paths
        import src.bubba_nodes.utils.detailer_models as detailer_models

        bbox_dir = tmp_path / "Models" / "Ultralytics" / "BBOX"
        bbox_dir.mkdir(parents=True)
        model_path = bbox_dir / "face.pt"
        model_path.write_text("model")

        monkeypatch.delattr(folder_paths, "models_dir", raising=False)
        monkeypatch.setattr(folder_paths, "get_folder_paths", lambda kind: [str(bbox_dir)] if kind == "ultralytics_bbox" else [])

        assert detailer_models.discover_detector_models() == ["bbox/face.pt"]
        assert detailer_models.resolve_detector_model_path("bbox/face.pt")[1] == model_path

    def test_discovery_supports_default_comfy_models_registration(self, tmp_path, monkeypatch):
        import folder_paths
        import src.bubba_nodes.utils.detailer_models as detailer_models

        default_models_dir = tmp_path / "ComfyUI" / "models"
        bbox_dir = default_models_dir / "ultralytics" / "bbox"
        bbox_dir.mkdir(parents=True)
        model_path = bbox_dir / "hand.pt"
        model_path.write_text("model")

        monkeypatch.delattr(folder_paths, "models_dir", raising=False)
        monkeypatch.setattr(folder_paths, "get_folder_paths", lambda kind: [str(default_models_dir)] if kind == "models" else [])

        assert detailer_models.discover_detector_models() == ["bbox/hand.pt"]
        assert detailer_models.resolve_detector_model_path("bbox/hand.pt")[1] == model_path

    def test_label_filter_and_bbox_mask(self):
        assert parse_label_filter(" face, HAND ,,") == {"face", "hand"}
        mask = bbox_to_mask((1, 2, 4, 5), 8, 8)
        assert mask.sum().item() == 9
        assert mask[2:5, 1:4].sum().item() == 9

    def test_postprocess_mask_supports_dilation_and_erosion(self):
        import torch

        mask = torch.zeros((9, 9), dtype=torch.float32)
        mask[4, 4] = 1.0

        dilated = postprocess_mask(mask, 1, 0)
        eroded = postprocess_mask(dilated, -1, 0)

        assert dilated.sum().item() == 9
        assert eroded.sum().item() == 1

    def test_plan_crop_clamps_and_aligns_to_multiple(self):
        import torch

        mask = torch.zeros((32, 32), dtype=torch.float32)
        mask[1:5, 1:5] = 1.0

        crop = plan_crop(mask, padding=2, force_square=False)

        assert crop is not None
        assert crop.x1 == 0
        assert crop.y1 == 0
        assert crop.width % 8 == 0
        assert crop.height % 8 == 0


class TestBubbaDetailer:
    def test_metadata(self):
        assert BubbaDetailer.RETURN_TYPES == ("IMAGE", "MASK", "BUBBA_METADATA", "STRING")
        assert BubbaDetailer.FUNCTION == "detail"
        assert BubbaDetailer.CATEGORY == "Bubba Nodes/Generation"

    def test_override_prompts_require_clip(self):
        with pytest.raises(ValueError, match="overrides require"):
            BubbaDetailer._resolve_conditioning("pos", "neg", None, "detail", "")

    def test_missing_conditioning_requires_prompt_text_and_clip(self):
        with pytest.raises(ValueError, match="needs conditioning"):
            BubbaDetailer._resolve_conditioning(None, None, None, "", "")

    def test_prompt_text_can_replace_missing_conditioning(self):
        positive, negative = BubbaDetailer._resolve_conditioning(None, None, _DummyClip(), "face detail", "")

        assert positive[0][0] == "COND:face detail"
        assert negative[0][0] == "COND:"

    def test_input_types_make_conditioning_optional(self):
        input_types = BubbaDetailer.INPUT_TYPES()

        assert "positive" not in input_types["required"]
        assert "negative" not in input_types["required"]
        assert "positive" in input_types["optional"]
        assert "negative" in input_types["optional"]

    def test_detect_sample_converts_bbox_result(self):
        import torch

        class _Boxes:
            xyxy = torch.tensor([[1.0, 2.0, 4.0, 5.0]])
            conf = torch.tensor([0.9])
            cls = torch.tensor([0])

        result = types.SimpleNamespace(boxes=_Boxes(), names={0: "face"})

        class _Detector:
            def __call__(self, image, conf, verbose):
                return [result]

        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        detections, fallbacks = BubbaDetailer._detect_sample(_Detector(), image, "bbox", 0.3, "", "")

        assert fallbacks == 0
        assert len(detections) == 1
        assert isinstance(detections[0], DetailerDetection)
        assert detections[0].label == "face"
        assert detections[0].area == 9

    def test_no_detection_path_returns_original_and_zero_mask(self, monkeypatch):
        import torch
        import src.bubba_nodes.nodes.detailer as detailer_module

        class _Detector:
            pass

        monkeypatch.setattr(detailer_module, "load_detector", lambda name: ("bbox", "face.pt", _Detector()))
        monkeypatch.setattr(
            BubbaDetailer,
            "_detect_sample",
            classmethod(lambda cls, detector, image, mode, confidence, include_labels, exclude_labels: ([], 0)),
        )

        image = torch.ones((1, 8, 8, 3), dtype=torch.float32)
        source_metadata = BubbaMetadata(model_name="nova", seed=9)
        result_image, result_mask, metadata, info = BubbaDetailer().detail(
            image,
            model=object(),
            vae=object(),
            positive=[],
            negative=[],
            detector_model_name="bbox/face.pt",
            confidence=0.3,
            mask_dilation=4,
            mask_blur=4,
            inpaint_padding=32,
            force_square_crop=False,
            guide_size=512,
            guide_size_for=True,
            max_size=1024,
            seed=1,
            steps=1,
            cfg=1.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=0.45,
            max_detections=10,
            inpaint_model=False,
            metadata=source_metadata,
        )

        assert torch.equal(result_image, image)
        assert result_mask.sum().item() == 0
        assert metadata == source_metadata
        assert "Processed: 0" in info

    def test_inpaint_crop_uses_inpaint_model_conditioning(self, monkeypatch):
        import torch
        import nodes

        class _FakeVae:
            def decode(self, samples):
                return samples

        conditioning = nodes.InpaintModelConditioning.return_value
        conditioning.encode.return_value = ("INPAINT_POS", "INPAINT_NEG", {"samples": torch.zeros((1, 4, 2, 2))})
        nodes.common_ksampler.return_value = ({"samples": torch.ones((1, 8, 8, 3))},)

        image = torch.zeros((1, 8, 8, 3), dtype=torch.float32)
        mask = torch.ones((1, 8, 8), dtype=torch.float32)

        refined = BubbaDetailer._inpaint_crop(
            image,
            mask,
            (0, 0, 8, 8),
            model="MODEL",
            vae=_FakeVae(),
            positive="POS",
            negative="NEG",
            seed=1,
            steps=2,
            cfg=3.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=0.45,
            guide_size=512,
            guide_size_for_bbox=True,
            max_size=1024,
            inpaint_model=True,
        )

        conditioning.encode.assert_called_once()
        nodes.common_ksampler.assert_called_once()
        call_args = nodes.common_ksampler.call_args.args
        assert call_args[6] == "INPAINT_POS"
        assert call_args[7] == "INPAINT_NEG"
        assert torch.equal(refined, torch.ones((1, 8, 8, 3)))

    def test_prepare_guided_crop_upscales_small_bbox_to_guide_size(self):
        import torch

        image = torch.zeros((1, 128, 128, 3), dtype=torch.float32)
        mask = torch.ones((1, 128, 128), dtype=torch.float32)

        upscaled_image, upscaled_mask = BubbaDetailer._prepare_guided_crop(
            image,
            mask,
            crop_bbox=(48, 48, 80, 80),
            guide_size=512,
            guide_size_for_bbox=True,
            max_size=1024,
        )

        assert upscaled_image.shape[1:3] == (1024, 1024)
        assert upscaled_mask.shape[-2:] == (1024, 1024)


class TestBubbaOverlayFromMetadata:
    def test_extract_fields_valid_metadata_object(self):
        payload = BubbaMetadata(
            model_name="myModel",
            seed=123,
            sampler_time_seconds=1.0,
            positive_prompt="hero, dramatic lighting",
            negative_prompt="blurry",
        )
        model_text, info_text, positive_text, negative_text = BubbaOverlayFromMetadata._extract_fields(payload)

        assert model_text == "myModel"
        assert "123" in info_text  # Contains seed
        assert "1.000" in info_text  # Contains time
        assert positive_text == "hero, dramatic lighting"
        assert negative_text == "blurry"

    def test_extract_fields_invalid_value_falls_back(self):
        model_text, info_text, positive_text, negative_text = BubbaOverlayFromMetadata._extract_fields(object())

        assert model_text == ""
        assert info_text == ""
        assert positive_text == ""
        assert negative_text == ""

    def test_metadata(self):
        assert BubbaOverlayFromMetadata.RETURN_TYPES == ("IMAGE",)
        assert BubbaOverlayFromMetadata.FUNCTION == "add_metadata_overlay"
        assert BubbaOverlayFromMetadata.CATEGORY == "Bubba Nodes/Image/Overlay"


class TestBubbaWatermark:
    def test_input_types_exposes_optional_mask(self):
        input_types = BubbaWatermark.INPUT_TYPES()

        assert "optional" in input_types
        assert "watermark_mask" in input_types["optional"]

    def test_resolve_anchor_position_center(self):
        x, y = BubbaWatermark._resolve_anchor_position("center", 1000, 600, 200, 100)

        assert x == 400
        assert y == 250

    def test_resolve_anchor_position_bottom_right(self):
        x, y = BubbaWatermark._resolve_anchor_position("bottom_right", 1000, 600, 200, 100)

        assert x == 800
        assert y == 500

    def test_metadata(self):
        assert BubbaWatermark.RETURN_TYPES == ("IMAGE",)
        assert BubbaWatermark.FUNCTION == "add_watermark"
        assert BubbaWatermark.CATEGORY == "Bubba Nodes/Image/Overlay"


class TestBubbaSaveImage:
    def test_input_types_expose_workflow_toggle_and_hidden_metadata(self):
        input_types = BubbaSaveImage.INPUT_TYPES()

        assert BubbaSaveImage.RETURN_TYPES == ("BUBBA_METADATA",)
        assert BubbaSaveImage.RETURN_NAMES == ("metadata",)
        assert "save_workflow_metadata" in input_types["required"]
        assert input_types["required"]["save_workflow_metadata"][1]["default"] is True
        assert "save_a1111_metadata" in input_types["required"]
        assert input_types["required"]["save_a1111_metadata"][1]["default"] is False
        assert input_types["hidden"] == {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}

    def test_save_images_embeds_comfy_workflow_metadata_when_enabled(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)

        image_path = tmp_path / "Hero" / "shot_00001_.png"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(10, 20, 30)).save(image_path)

        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [{"filename": image_path.name, "subfolder": "Hero", "type": "output"}],
        }

        node = BubbaSaveImage()
        prompt = {"12": {"class_type": "KSampler", "inputs": {"seed": 42}}}
        extra_pnginfo = {"workflow": {"version": 1, "nodes": [{"id": 12}]}}

        result = node.save_images(
            images=[object()],
            filepath="Hero/shot",
            preview_only=False,
            save_workflow_metadata=True,
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )

        with Image.open(image_path) as saved:
            assert json.loads(saved.info["prompt"]) == prompt
            assert json.loads(saved.info["workflow"]) == extra_pnginfo["workflow"]

        assert isinstance(result["result"][0], BubbaMetadata)
        assert result["ui"]["images"][0]["filename"] == image_path.name

    def test_save_images_skips_workflow_metadata_when_disabled(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)

        image_path = tmp_path / "Hero" / "shot_00002_.png"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(40, 50, 60)).save(image_path)

        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [{"filename": image_path.name, "subfolder": "Hero", "type": "output"}],
        }

        node = BubbaSaveImage()
        metadata = BubbaMetadata.from_mapping({"model_name": "nova", "seed": 9, "filepath": "Hero/shot"})

        node.save_images(
            images=[object()],
            filepath="Hero/shot",
            preview_only=False,
            save_workflow_metadata=False,
            metadata=metadata,
            prompt={"12": {"class_type": "KSampler"}},
            extra_pnginfo={"workflow": {"version": 1}},
        )

        with Image.open(image_path) as saved:
            assert "prompt" not in saved.info
            assert "workflow" not in saved.info
            assert json.loads(saved.info["bubba_metadata"])["model_name"] == "nova"

    def test_save_images_embeds_a1111_parameters_when_enabled(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

            @staticmethod
            def get_full_path_or_raise(kind, name):
                assert kind == "checkpoints"
                return str(tmp_path / name)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)
        monkeypatch.setattr(save_image_module, "checkpoint_short_hash", lambda path: "51dc941b55")

        image_path = tmp_path / "Hero" / "civitai_00001_.png"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(1, 2, 3)).save(image_path)
        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [{"filename": image_path.name, "subfolder": "Hero", "type": "output"}],
        }

        metadata = BubbaMetadata(
            model_name="NovaFurryAM",
            positive_prompt="masterpiece, lucario",
            negative_prompt="blurry",
            steps=30,
            sampler_name="euler",
            scheduler="normal",
            cfg=5,
            seed=2934057377,
        )
        prompt = {"1": {"class_type": "BubbaCheckpointLoader", "inputs": {"ckpt_name": "models/NovaFurryAM.safetensors"}}}

        BubbaSaveImage().save_images(
            images=[object()],
            filepath="Hero/civitai",
            save_workflow_metadata=False,
            save_a1111_metadata=True,
            metadata=metadata,
            prompt=prompt,
        )

        with Image.open(image_path) as saved:
            assert saved.info["parameters"] == (
                "masterpiece, lucario\n"
                "Negative prompt: blurry\n"
                "Steps: 30, Sampler: euler, CFG scale: 5, Seed: 2934057377, "
                "Model hash: 51dc941b55, Model: NovaFurryAM"
            )

    def test_save_images_warns_when_connected_metadata_is_empty(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)

        image_path = tmp_path / "Hero" / "empty_metadata_00001_.png"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(70, 80, 90)).save(image_path)

        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [{"filename": image_path.name, "subfolder": "Hero", "type": "output"}],
        }

        result = BubbaSaveImage().save_images(
            images=[object()],
            filepath="Hero/empty_metadata",
            preview_only=False,
            save_workflow_metadata=False,
            metadata=BubbaMetadata(),
        )

        assert result["ui"]["metadata_warnings"] == [
            "Bubba metadata input is connected but contains no model, prompt, sampler, seed, or LoRA data."
        ]

    def test_save_images_does_not_warn_when_metadata_is_not_connected(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)

        image_path = tmp_path / "Hero" / "plain_00001_.png"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(90, 80, 70)).save(image_path)

        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [{"filename": image_path.name, "subfolder": "Hero", "type": "output"}],
        }

        result = BubbaSaveImage().save_images(
            images=[object()],
            filepath="Hero/plain",
            preview_only=False,
            save_workflow_metadata=False,
        )

        assert "metadata_warnings" not in result["ui"]

    def test_save_then_load_preserves_bubba_metadata_for_multi_image_batch(self, tmp_path, monkeypatch):
        class _FolderPathsStub:
            @staticmethod
            def get_output_directory():
                return str(tmp_path)

        monkeypatch.setattr(save_image_module, "folder_paths", _FolderPathsStub)

        first_path = tmp_path / "Hero" / "batch_00001_.png"
        second_path = tmp_path / "Hero" / "batch_00002_.png"
        first_path.parent.mkdir(parents=True)
        Image.new("RGB", (8, 8), color=(10, 11, 12)).save(first_path)
        Image.new("RGB", (8, 8), color=(13, 14, 15)).save(second_path)

        UI.ImageSaveHelper.get_save_images_ui.return_value.as_dict.return_value = {
            "images": [
                {"filename": first_path.name, "subfolder": "Hero", "type": "output"},
                {"filename": second_path.name, "subfolder": "Hero", "type": "output"},
            ],
        }

        node = BubbaSaveImage()
        metadata = BubbaMetadata(
            model_name="nova_batch",
            positive_prompt="hero portrait",
            negative_prompt="blurry",
            seed=77,
            save_prefix="Hero/batch",
        )

        node.save_images(
            images=[object(), object()],
            filepath="Hero/batch",
            preview_only=False,
            save_workflow_metadata=False,
            metadata=metadata,
            prompt={"12": {"class_type": "KSampler"}},
            extra_pnginfo={"workflow": {"version": 1}},
        )

        for path in [first_path, second_path]:
            with Image.open(path) as saved:
                loaded, text = BubbaLoadImageWithMetadata._extract_bubba_metadata(saved.info)
            assert loaded.model_name == "nova_batch"
            assert loaded.seed == 77
            assert loaded.positive_prompt == "hero portrait"
            assert "nova_batch" in text


class TestBubbaMetadataDebug:
    def test_debug_metadata_returns_pretty_json(self):
        node = BubbaMetadataDebug()
        metadata = BubbaMetadata(
            model_name="myModel",
            positive_prompt="hero",
            negative_prompt="blurry",
            seed=9,
            save_prefix="Character/Scene",
        )
        result = node.debug_metadata(metadata)
        (metadata_text,) = result["result"]
        payload = json.loads(metadata_text)

        assert payload["model_name"] == "myModel"
        assert payload["seed"] == 9
        assert result["ui"]["metadata_text"] == [metadata_text]

    def test_metadata(self):
        assert BubbaMetadataDebug.RETURN_TYPES == ("STRING",)
        assert BubbaMetadataDebug.FUNCTION == "debug_metadata"
        assert BubbaMetadataDebug.CATEGORY == "Bubba Nodes/Metadata"


class TestBubbaMetadataModel:
    def test_from_json_normalizes_types_and_whitespace(self):
        metadata = BubbaMetadata.from_json(
            '{"model_name":" modelA ","sampler_time_seconds":"0.57","steps":"25","cfg":"7.5","sampler_name":" dpmpp_2m ","scheduler":" karras ","denoise":"1.0","positive_prompt":" pos ","negative_prompt":" neg ","seed":"123","filepath":" folder/file "}'
        )

        assert metadata.model_name == "modelA"
        assert "0.57" in metadata.formatted_sampler_info()  # Contains time
        assert "123" in metadata.formatted_sampler_info()  # Contains seed
        assert "25" in metadata.formatted_sampler_info()  # Contains steps
        assert metadata.sampler_time_seconds == 0.57
        assert metadata.steps == 25
        assert metadata.cfg == 7.5
        assert metadata.sampler_name == "dpmpp_2m"
        assert metadata.scheduler == "karras"
        assert metadata.denoise == 1.0
        assert metadata.positive_prompt == "pos"
        assert metadata.negative_prompt == "neg"
        assert metadata.seed == 123
        assert metadata.save_prefix == "folder/file"
        assert metadata.filepath == "folder/file"

    def test_from_json_invalid_payload_falls_back(self):
        metadata = BubbaMetadata.from_json("not-json")

        assert metadata.model_name == ""
        assert metadata.formatted_sampler_info() == ""
        assert metadata.positive_prompt == ""
        assert metadata.negative_prompt == ""
        assert metadata.seed == 0
        assert metadata.save_prefix == ""

    def test_to_json_round_trip(self):
        metadata = BubbaMetadata(
            model_name="myModel",
            sampler_time_seconds=0.1,
            steps=20,
            cfg=8.0,
            sampler_name="dpmpp_2m",
            scheduler="karras",
            denoise=1.0,
            positive_prompt="hero",
            negative_prompt="blurry",
            seed=7,
            save_prefix="Character/Scene",
        )
        payload = json.loads(metadata.to_json())

        assert payload["model_name"] == "myModel"
        assert payload["sampler_time_seconds"] == 0.1
        assert payload["steps"] == 20
        assert payload["cfg"] == 8.0
        assert payload["sampler_name"] == "dpmpp_2m"
        assert payload["scheduler"] == "karras"
        assert payload["denoise"] == 1.0
        assert payload["positive_prompt"] == "hero"
        assert payload["negative_prompt"] == "blurry"
        assert payload["seed"] == 7
        assert payload["save_prefix"] == "Character/Scene"
        assert "sampler_info" not in payload
        assert "prompt_sections" not in payload

    def test_updated_returns_normalized_copy(self):
        metadata = BubbaMetadata(model_name="old", seed=1)
        updated = metadata.updated(model_name=" new ", seed="9")

        assert updated.model_name == "new"
        assert updated.seed == 9
        assert metadata.model_name == "old"

    def test_loras_default_empty(self):
        metadata = BubbaMetadata()
        assert metadata.loras == []

    def test_loras_coerced_from_list(self):
        metadata = BubbaMetadata(loras=["loraA", "loraB"])
        assert metadata.loras == ["loraA", "loraB"]

    def test_loras_coerced_from_comma_string(self):
        metadata = BubbaMetadata.from_mapping({"loras": "loraA, loraB"})
        assert metadata.loras == ["loraA", "loraB"]

    def test_loras_roundtrip_json(self):
        metadata = BubbaMetadata(loras=["style_v1", "detail_v2"])
        restored = BubbaMetadata.from_json(metadata.to_json())
        assert restored.loras == ["style_v1", "detail_v2"]

    def test_formatted_sampler_info_includes_loras(self):
        metadata = BubbaMetadata(
            steps=20,
            seed=1,
            cfg=7.0,
            sampler_name="euler",
            scheduler="karras",
            denoise=1.0,
            loras=["style_v1", "detail_v2"],
        )
        info = metadata.formatted_sampler_info()
        assert "style_v1" in info
        assert "detail_v2" in info

    def test_formatted_sampler_info_no_loras_suffix_when_empty(self):
        metadata = BubbaMetadata(
            steps=20,
            seed=1,
            cfg=7.0,
            sampler_name="euler",
            scheduler="karras",
            denoise=1.0,
        )
        assert "LoRA" not in metadata.formatted_sampler_info()

    def test_updated_appends_loras(self):
        metadata = BubbaMetadata(loras=["base_lora"])
        updated = metadata.updated(loras=list(metadata.loras) + ["new_lora"])
        assert updated.loras == ["base_lora", "new_lora"]
        assert metadata.loras == ["base_lora"]  # original unchanged


class TestBubbaLoraLoader:
    def _make_mock_loader(self, model_out="MODEL_OUT", clip_out="CLIP_OUT"):
        """Patch LoraLoader.load_lora to avoid actual file I/O."""
        mock = MagicMock()
        mock.load_lora.return_value = (model_out, clip_out)
        return mock

    def test_load_lora_no_metadata(self):
        node = BubbaLoraLoader()
        node._loader = self._make_mock_loader()

        model_out, clip_out, lora_name, metadata = node.load_lora("MODEL", "CLIP", "styles/my_style_v1.safetensors", 0.8, 0.6)

        assert model_out == "MODEL_OUT"
        assert clip_out == "CLIP_OUT"
        assert lora_name == "my_style_v1"
        assert isinstance(metadata, BubbaMetadata)
        assert metadata.loras == ["my_style_v1"]

    def test_load_lora_appends_to_existing_metadata(self):
        node = BubbaLoraLoader()
        node._loader = self._make_mock_loader()
        existing = BubbaMetadata(model_name="model", loras=["first_lora"])

        _, _, lora_name, metadata = node.load_lora(
            "MODEL",
            "CLIP",
            "second_lora.safetensors",
            1.0,
            1.0,
            metadata=existing,
        )

        assert lora_name == "second_lora"
        assert metadata.loras == ["first_lora", "second_lora"]
        assert existing.loras == ["first_lora"]  # original unchanged

    def test_load_lora_preserves_other_metadata_fields(self):
        node = BubbaLoraLoader()
        node._loader = self._make_mock_loader()
        existing = BubbaMetadata(model_name="myModel", seed=42, save_prefix="hero/shot")

        _, _, _, metadata = node.load_lora(
            "MODEL",
            "CLIP",
            "detail.safetensors",
            1.0,
            1.0,
            metadata=existing,
        )

        assert metadata.model_name == "myModel"
        assert metadata.seed == 42
        assert metadata.save_prefix == "hero/shot"
        assert metadata.loras == ["detail"]

    def test_class_attributes(self):
        assert BubbaLoraLoader.RETURN_TYPES == ("MODEL", "CLIP", "STRING", "BUBBA_METADATA")
        assert BubbaLoraLoader.RETURN_NAMES == ("model", "clip", "lora_name", "metadata")
        assert BubbaLoraLoader.FUNCTION == "load_lora"
        assert BubbaLoraLoader.CATEGORY == "Bubba Nodes/Generation"

    def test_registered_in_node_mappings(self):
        assert "BubbaLoraLoader" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["BubbaLoraLoader"] is BubbaLoraLoader
        assert "BubbaLoraLoader" in NODE_DISPLAY_NAME_MAPPINGS


class TestBubbaComboLoader:
    def test_applies_clip_skip_and_updates_metadata(self):
        import src.bubba_nodes.nodes.combo_loader as combo_module

        node = BubbaComboLoader()

        clip_clone = MagicMock()
        clip_original = MagicMock()
        clip_original.clone.return_value = clip_clone

        mock_ckpt = MagicMock()
        mock_ckpt.load_checkpoint.return_value = ("MODEL", clip_original, "VAE")
        combo_module.CheckpointLoaderSimple = MagicMock(return_value=mock_ckpt)

        model, clip, vae, ckpt_name, metadata = node.load(
            "models/example.safetensors",
            combo_module._NONE_SENTINEL,
            combo_module._NONE_SENTINEL,
            combo_module._CLIP_TYPES[0],
            2,
            None,
        )

        assert model == "MODEL"
        assert vae == "VAE"
        assert ckpt_name == "models/example.safetensors"
        assert clip is clip_clone
        clip_clone.clip_layer.assert_called_once_with(-2)
        assert metadata.clip_skip == 2

    def test_clip_skip_zero_leaves_clip_unmodified(self):
        import src.bubba_nodes.nodes.combo_loader as combo_module

        node = BubbaComboLoader()

        clip_original = MagicMock()
        mock_ckpt = MagicMock()
        mock_ckpt.load_checkpoint.return_value = ("MODEL", clip_original, "VAE")
        combo_module.CheckpointLoaderSimple = MagicMock(return_value=mock_ckpt)

        _, clip, _, _, metadata = node.load(
            "models/example.safetensors",
            combo_module._NONE_SENTINEL,
            combo_module._NONE_SENTINEL,
            combo_module._CLIP_TYPES[0],
            0,
            None,
        )

        assert clip is clip_original
        clip_original.clone.assert_not_called()
        assert metadata.clip_skip == 0

    def test_external_clip_loader_receives_device_option(self):
        import src.bubba_nodes.nodes.combo_loader as combo_module

        node = BubbaComboLoader()

        mock_ckpt = MagicMock()
        mock_ckpt.load_checkpoint.return_value = ("MODEL", "CHECKPOINT_CLIP", "VAE")
        combo_module.CheckpointLoaderSimple = MagicMock(return_value=mock_ckpt)

        mock_clip_loader = MagicMock()
        mock_clip_loader.load_clip.return_value = ("EXTERNAL_CLIP",)
        combo_module.CLIPLoader = MagicMock(return_value=mock_clip_loader)

        _, clip, _, _, _ = node.load(
            "models/example.safetensors",
            combo_module._NONE_SENTINEL,
            "AnimaTEModel.safetensors",
            combo_module._CLIP_TYPES[0],
            0,
            None,
            "cpu",
        )

        assert clip == "EXTERNAL_CLIP"
        mock_clip_loader.load_clip.assert_called_once_with(
            "AnimaTEModel.safetensors",
            type=combo_module._CLIP_TYPES[0],
            device="cpu",
        )

    def test_prompt_builders_no_longer_expose_clip_skip_option(self):
        assert "clip_skip" not in BubbaCharacterPromptBuilder.INPUT_TYPES().get("optional", {})


class TestBubbaUpscaler:
    """Tests for BubbaUpscaler (pixel-space ESRGAN upscaling)."""

    def _make_fake_image(self, h=64, w=64):
        """Create a minimal (B, H, W, C) float32 tensor-like mock."""
        import torch

        return torch.zeros(1, h, w, 3)

    def _patch_upscale_nodes(self, mocker, scale_factor=4):
        """Patch UpscaleModelLoader and ImageUpscaleWithModel to avoid I/O."""
        import src.bubba_nodes.nodes.upscaler as upscaler_module
        import torch

        fake_model = MagicMock()
        mock_loader = MagicMock()
        mock_loader.execute.return_value = MagicMock(__getitem__=lambda self, i: fake_model)

        def fake_upscale_execute(upscale_model, image):
            # Simulate ESRGAN 4x output
            b, h, w, c = image.shape
            upscaled = torch.zeros(b, h * scale_factor, w * scale_factor, c)
            result = MagicMock()
            result.__getitem__ = lambda self, i: upscaled
            return result

        upscaler_module.UpscaleModelLoader = mock_loader
        upscaler_module.ImageUpscaleWithModel = MagicMock()
        upscaler_module.ImageUpscaleWithModel.execute = fake_upscale_execute
        return mock_loader

    def test_upscale_no_resize_returns_esrgan_output(self):
        image = self._make_fake_image(64, 64)
        self._patch_upscale_nodes(None, scale_factor=4)

        node = BubbaUpscaler()
        result_image, result_metadata = node.upscale(image, "4x_model.pth", scale_by=1.0, resize_method="lanczos")

        # With scale_by=1.0, should be unchanged from ESRGAN output (256x256)
        assert result_image.shape[1] == 256  # H
        assert result_image.shape[2] == 256  # W
        assert isinstance(result_metadata, BubbaMetadata)

    def test_upscale_with_scale_by_resizes(self):
        image = self._make_fake_image(64, 64)
        self._patch_upscale_nodes(None, scale_factor=4)

        # common_upscale is mocked in conftest to return its input unchanged;
        # just verify it is called when scale_by != 1.0
        node = BubbaUpscaler()
        result_image, result_metadata = node.upscale(image, "4x_model.pth", scale_by=0.5, resize_method="lanczos")
        # comfy.utils.common_upscale mock returns tensor unchanged, so result still exists
        assert result_image is not None
        assert isinstance(result_metadata, BubbaMetadata)

    def test_upscale_passes_through_metadata(self):
        image = self._make_fake_image()
        self._patch_upscale_nodes(None)
        existing = BubbaMetadata(model_name="myModel", seed=42, loras=["style"])

        node = BubbaUpscaler()
        _, metadata = node.upscale(
            image,
            "4x_model.pth",
            scale_by=1.0,
            resize_method="lanczos",
            metadata=existing,
        )

        assert metadata.model_name == "myModel"
        assert metadata.seed == 42
        assert metadata.loras == ["style"]

    def test_upscale_no_metadata_returns_empty(self):
        image = self._make_fake_image()
        self._patch_upscale_nodes(None)

        node = BubbaUpscaler()
        _, metadata = node.upscale(image, "4x_model.pth", scale_by=1.0, resize_method="lanczos")

        assert isinstance(metadata, BubbaMetadata)
        assert metadata.model_name == ""

    def test_class_attributes(self):
        assert BubbaUpscaler.RETURN_TYPES == ("IMAGE", "BUBBA_METADATA")
        assert BubbaUpscaler.RETURN_NAMES == ("image", "metadata")
        assert BubbaUpscaler.FUNCTION == "upscale"
        assert BubbaUpscaler.CATEGORY == "Bubba Nodes/Image"

    def test_registered_in_node_mappings(self):
        assert "BubbaUpscaler" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["BubbaUpscaler"] is BubbaUpscaler
        assert "BubbaUpscaler" in NODE_DISPLAY_NAME_MAPPINGS


class TestBubbaImageCompare:
    """Tests for BubbaImageCompare UI payload node (draggable A/B splitter in frontend)."""

    def _img(self, h=32, w=32, fill=0.0):
        import torch

        return torch.full((1, h, w, 3), fill)

    def test_compare_returns_ui_payload(self):
        node = BubbaImageCompare()
        a = self._img(32, 40, fill=1.0)
        b = self._img(32, 40, fill=0.0)
        result = node.compare(a, b)

        assert isinstance(result, dict)
        assert "ui" in result
        assert "b64_a" in result["ui"]
        assert "b64_b" in result["ui"]

    def test_compare_returns_non_empty_base64_chunks(self):
        node = BubbaImageCompare()
        a = self._img(16, 16, fill=1.0)
        b = self._img(16, 16, fill=0.0)
        result = node.compare(a, b)

        chunks_a = result["ui"]["b64_a"]
        chunks_b = result["ui"]["b64_b"]
        assert isinstance(chunks_a, list)
        assert isinstance(chunks_b, list)
        assert len(chunks_a) > 0
        assert len(chunks_b) > 0
        assert all(isinstance(x, str) for x in chunks_a)
        assert all(isinstance(x, str) for x in chunks_b)

    def test_empty_input_returns_empty_ui_payload(self):
        import torch

        node = BubbaImageCompare()
        empty = torch.zeros((0, 16, 16, 3))
        result = node.compare(empty, empty)
        assert result["ui"]["b64_a"] == []
        assert result["ui"]["b64_b"] == []

    def test_class_attributes(self):
        assert BubbaImageCompare.RETURN_TYPES == ()
        assert BubbaImageCompare.RETURN_NAMES == ()
        assert BubbaImageCompare.FUNCTION == "compare"
        assert BubbaImageCompare.CATEGORY == "Bubba Nodes/Image"
        assert BubbaImageCompare.OUTPUT_NODE is True

    def test_registered_in_node_mappings(self):
        assert "BubbaImageCompare" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["BubbaImageCompare"] is BubbaImageCompare
        assert "BubbaImageCompare" in NODE_DISPLAY_NAME_MAPPINGS


class TestBubbaCharacterPromptBuilder:
    def test_hybrid_prompt_build(self):
        node = BubbaCharacterPromptBuilder()
        positive, negative, positive_cond, negative_cond, metadata = node.build_prompt(
            _DummyClip(),
            "silver hair, green eyes",
            "athletic",
            "jacket",
            "standing",
            "smile",
            "city rooftop",
            "anime, dramatic lighting",
            "masterpiece, best quality",
            "blurry, lowres",
            "hybrid",
            True,
            True,
        )
        assert "|" in positive
        assert negative == "blurry, lowres"
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")

    def test_dedupe_case_insensitive(self):
        node = BubbaCharacterPromptBuilder()
        positive, negative, _, _, _ = node.build_prompt(
            _DummyClip(),
            "smile, Smile",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "badhandv4, badhandv4, BadHandV4",
            "booru",
            True,
            True,
        )
        assert positive == "smile"
        assert negative == "badhandv4"

    def test_prose_mode(self):
        node = BubbaCharacterPromptBuilder()
        positive, _, _, _, _ = node.build_prompt(
            _DummyClip(),
            "red scarf",
            "",
            "",
            "running",
            "",
            "sunset street",
            "",
            "",
            "",
            "prose",
            True,
            True,
        )
        assert " and " in positive

    def test_metadata(self):
        assert BubbaCharacterPromptBuilder.RETURN_TYPES == ("STRING", "STRING", "CONDITIONING", "CONDITIONING", "BUBBA_METADATA")
        assert BubbaCharacterPromptBuilder.FUNCTION == "build_prompt"
        assert BubbaCharacterPromptBuilder.CATEGORY == "Bubba Nodes/Prompt"


class TestBubbaSimplePromptBuilder:
    def test_basic_build(self):
        node = BubbaSimplePromptBuilder()
        positive, negative, positive_cond, negative_cond, metadata = node.build_prompt(
            _DummyClip(),
            "1girl, silver hair",
            "blurry, lowres",
            True,
            True,
        )
        assert positive == "1girl, silver hair"
        assert negative == "blurry, lowres"
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")
        assert isinstance(metadata, BubbaMetadata)
        assert metadata.positive_prompt == positive
        assert metadata.negative_prompt == negative

    def test_dedupe(self):
        node = BubbaSimplePromptBuilder()
        positive, negative, _, _, _ = node.build_prompt(_DummyClip(), "smile, Smile, hero", "blurry, Blurry", True, True)
        assert positive == "smile, hero"
        assert negative == "blurry"

    def test_metadata_node_attrs(self):
        assert BubbaSimplePromptBuilder.RETURN_TYPES == ("STRING", "STRING", "CONDITIONING", "CONDITIONING", "BUBBA_METADATA")
        assert BubbaSimplePromptBuilder.FUNCTION == "build_prompt"
        assert BubbaSimplePromptBuilder.CATEGORY == "Bubba Nodes/Prompt"

    def test_registered_in_node_mappings(self):
        assert "BubbaSimplePromptBuilder" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["BubbaSimplePromptBuilder"] is BubbaSimplePromptBuilder
        assert "BubbaSimplePromptBuilder" in NODE_DISPLAY_NAME_MAPPINGS


class TestBubbaPromptRandomizer:
    def test_load_categories_from_json_files(self, tmp_path):
        (tmp_path / "background.json").write_text(json.dumps(["library", "forest trail", "library", "", "random"]), encoding="utf-8")
        (tmp_path / "camera-angle.json").write_text(json.dumps(["front view"]), encoding="utf-8")
        (tmp_path / "invalid.json").write_text("{", encoding="utf-8")
        (tmp_path / "empty.json").write_text(json.dumps([]), encoding="utf-8")

        categories = prompt_randomizer_module.load_prompt_randomizer_categories(tmp_path)

        assert categories == {
            "background": ["library", "forest trail"],
            "camera_angle": ["front view"],
        }

    def test_input_types_adds_dropdown_for_each_json_category(self, monkeypatch, tmp_path):
        (tmp_path / "background.json").write_text(json.dumps(["library"]), encoding="utf-8")
        (tmp_path / "clothing.json").write_text(json.dumps(["hoodie"]), encoding="utf-8")
        monkeypatch.setattr(prompt_randomizer_module, "_DATA_DIR", tmp_path)

        required = BubbaPromptRandomizer.INPUT_TYPES()["required"]

        assert required["background"][0] == ["disabled", "random", "library"]
        assert required["clothing"][0] == ["disabled", "random", "hoodie"]

    def test_randomize_prompt_uses_seeded_json_categories(self, monkeypatch, tmp_path):
        (tmp_path / "background.json").write_text(json.dumps(["library", "forest trail"]), encoding="utf-8")
        (tmp_path / "subject.json").write_text(json.dumps(["1girl", "moth_girl"]), encoding="utf-8")
        monkeypatch.setattr(prompt_randomizer_module, "_DATA_DIR", tmp_path)

        first = BubbaPromptRandomizer().randomize_prompt(
            seed=11,
            prefix_text="masterpiece, best quality",
            extra_positive="cinematic lighting",
            negative_prompt="blurry, blurry",
            cleanup=True,
            dedupe=True,
            background="random",
            subject="random",
            clip=_DummyClip(),
        )
        second = BubbaPromptRandomizer().randomize_prompt(
            seed=11,
            prefix_text="masterpiece, best quality",
            extra_positive="cinematic lighting",
            negative_prompt="blurry, blurry",
            cleanup=True,
            dedupe=True,
            background="random",
            subject="random",
            clip=_DummyClip(),
        )

        positive, negative, positive_cond, negative_cond, chosen_values, metadata = first
        assert first[:2] == second[:2]
        assert "masterpiece, best quality" in positive
        assert "cinematic lighting" in positive
        assert negative == "blurry"
        assert "background:" in chosen_values
        assert "subject:" in chosen_values
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")
        assert metadata.positive_prompt == positive
        assert metadata.negative_prompt == negative

    def test_randomize_prompt_supports_disabled_and_explicit_values_without_clip(self, monkeypatch, tmp_path):
        (tmp_path / "background.json").write_text(json.dumps(["library"]), encoding="utf-8")
        (tmp_path / "subject.json").write_text(json.dumps(["1girl"]), encoding="utf-8")
        monkeypatch.setattr(prompt_randomizer_module, "_DATA_DIR", tmp_path)

        positive, negative, positive_cond, negative_cond, chosen_values, _ = BubbaPromptRandomizer().randomize_prompt(
            seed=0,
            prefix_text="hero",
            extra_positive="hero, smile",
            negative_prompt="lowres",
            cleanup=True,
            dedupe=True,
            background="library",
            subject="disabled",
        )

        assert positive == "hero, library, smile"
        assert negative == "lowres"
        assert positive_cond == [[None, {}]]
        assert negative_cond == [[None, {}]]
        assert chosen_values == "background: library"

    def test_remove_category_underscores_does_not_change_prefix_or_negative(self, monkeypatch, tmp_path):
        (tmp_path / "face_features.json").write_text(json.dumps(["blue_eyes"]), encoding="utf-8")
        monkeypatch.setattr(prompt_randomizer_module, "_DATA_DIR", tmp_path)

        positive, negative, _, _, chosen_values, _ = BubbaPromptRandomizer().randomize_prompt(
            seed=0,
            prefix_text="masterpiece, best quality, score_9, score_8, score_7",
            extra_positive="",
            negative_prompt="bad_hands, low_quality",
            cleanup=True,
            dedupe=True,
            remove_category_underscores=True,
            face_features="blue_eyes",
        )

        assert positive == "masterpiece, best quality, score_9, score_8, score_7, blue eyes"
        assert negative == "bad_hands, low_quality"
        assert chosen_values == "face_features: blue eyes"

    def test_metadata_node_attrs(self):
        assert BubbaPromptRandomizer.RETURN_TYPES == ("STRING", "STRING", "CONDITIONING", "CONDITIONING", "STRING", "BUBBA_METADATA")
        assert BubbaPromptRandomizer.FUNCTION == "randomize_prompt"
        assert BubbaPromptRandomizer.CATEGORY == "Bubba Nodes/Prompt"

    def test_registered_in_node_mappings(self):
        assert "BubbaPromptRandomizer" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["BubbaPromptRandomizer"] is BubbaPromptRandomizer
        assert "BubbaPromptRandomizer" in NODE_DISPLAY_NAME_MAPPINGS


class TestBubbaPromptCleaner:
    def test_clean_prompt_cleanup_and_dedupe(self):
        node = BubbaPromptCleaner()
        clean_pos, clean_neg, positive_cond, negative_cond = node.clean_prompt(
            " hero ,  smile,smile , cinematic lighting ",
            "blurry, blurry, lowres",
            True,
            True,
        )
        assert clean_pos == "hero, smile, cinematic lighting"
        assert clean_neg == "blurry, lowres"
        assert positive_cond == [[None, {}]]
        assert negative_cond == [[None, {}]]

    def test_clean_prompt_with_clip_outputs_conditioning(self):
        node = BubbaPromptCleaner()
        clean_pos, clean_neg, positive_cond, negative_cond = node.clean_prompt(
            "hero, smile",
            "blurry",
            True,
            True,
            _DummyClip(),
        )
        assert clean_pos == "hero, smile"
        assert clean_neg == "blurry"
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")

    def test_metadata(self):
        assert BubbaPromptCleaner.RETURN_TYPES == ("STRING", "STRING", "CONDITIONING", "CONDITIONING")
        assert BubbaPromptCleaner.FUNCTION == "clean_prompt"
        assert BubbaPromptCleaner.CATEGORY == "Bubba Nodes/Prompt"


class TestBubbaPromptInspector:
    def test_inspect_prompt_reports_counts_duplicates_and_preview(self):
        node = BubbaPromptInspector()
        token_count, duplicate_tags, conflict_warnings, formatted_preview = node.inspect_prompt(
            "hero, smile, smile, day, indoors",
            "blurry, hero, night",
        )

        assert token_count == 8
        assert "positive: smile" in duplicate_tags
        assert "present in both positive and negative: hero" in conflict_warnings
        assert "Positive: hero, smile, day, indoors" in formatted_preview
        assert "Negative: blurry, hero, night" in formatted_preview

    def test_metadata(self):
        assert BubbaPromptInspector.RETURN_TYPES == ("INT", "STRING", "STRING", "STRING")
        assert BubbaPromptInspector.FUNCTION == "inspect_prompt"
        assert BubbaPromptInspector.CATEGORY == "Bubba Nodes/Prompt"


class TestMappings:
    def test_all_nodes_registered(self):
        assert "BubbaFilename" in NODE_CLASS_MAPPINGS
        assert "BubbaEmptyLatentBySize" in NODE_CLASS_MAPPINGS
        assert "BubbaLoadImageWithMetadata" in NODE_CLASS_MAPPINGS
        assert "BubbaCheckpointLoader" in NODE_CLASS_MAPPINGS
        assert "BubbaKSampler" in NODE_CLASS_MAPPINGS
        assert "BubbaDetailer" in NODE_CLASS_MAPPINGS
        assert "BubbaSaveImage" in NODE_CLASS_MAPPINGS
        assert "BubbaOverlayFromMetadata" in NODE_CLASS_MAPPINGS
        assert "BubbaWatermark" in NODE_CLASS_MAPPINGS
        assert "BubbaMetadataDebug" in NODE_CLASS_MAPPINGS
        assert "BubbaCharacterPromptBuilder" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptRandomizer" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptCleaner" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptInspector" in NODE_CLASS_MAPPINGS

    def test_display_names_match_keys(self):
        assert NODE_CLASS_MAPPINGS.keys() == NODE_DISPLAY_NAME_MAPPINGS.keys()

    def test_class_mappings_point_to_classes(self):
        assert NODE_CLASS_MAPPINGS["BubbaFilename"] is BubbaFilename
        assert NODE_CLASS_MAPPINGS["BubbaEmptyLatentBySize"] is BubbaEmptyLatentBySize
        assert NODE_CLASS_MAPPINGS["BubbaLoadImageWithMetadata"] is BubbaLoadImageWithMetadata
        assert NODE_CLASS_MAPPINGS["BubbaCheckpointLoader"] is BubbaCheckpointLoader
        assert NODE_CLASS_MAPPINGS["BubbaDetailer"] is BubbaDetailer
        assert NODE_CLASS_MAPPINGS["BubbaOverlayFromMetadata"] is BubbaOverlayFromMetadata
        assert NODE_CLASS_MAPPINGS["BubbaMetadataDebug"] is BubbaMetadataDebug
        assert NODE_CLASS_MAPPINGS["BubbaCharacterPromptBuilder"] is BubbaCharacterPromptBuilder
        assert NODE_CLASS_MAPPINGS["BubbaPromptRandomizer"] is BubbaPromptRandomizer
        assert NODE_CLASS_MAPPINGS["BubbaPromptCleaner"] is BubbaPromptCleaner
        assert NODE_CLASS_MAPPINGS["BubbaPromptInspector"] is BubbaPromptInspector


class TestAutocompleteServerRoutes:
    def test_upstream_url_uses_env_override(self, monkeypatch):
        monkeypatch.setenv("BUBBA_UPSTREAM_CSV_URL", "https://example.invalid/cache.csv")
        assert autocomplete_server._upstream_csv_url() == "https://example.invalid/cache.csv"

    def test_tag_source_url_uses_env_override(self, monkeypatch):
        source = autocomplete_server.TagSource(
            "example",
            "example.csv",
            "BUBBA_EXAMPLE_CSV_URL",
            "https://example.invalid/default.csv",
        )
        monkeypatch.setenv("BUBBA_EXAMPLE_CSV_URL", "https://example.invalid/override.csv")
        assert autocomplete_server._tag_source_url(source) == "https://example.invalid/override.csv"

    def test_save_bytes_atomic_writes_file(self, tmp_path):
        target = tmp_path / "nested" / "cache.csv"
        autocomplete_server._save_bytes_atomic(target, b"tag,count\nfoo,1\n")
        assert target.read_bytes() == b"tag,count\nfoo,1\n"

    def test_register_routes_and_handlers_work(self, monkeypatch, tmp_path):
        class _FakeRoutes:
            def __init__(self):
                self.get_handlers = {}
                self.post_handlers = {}

            def get(self, path):
                def _decorator(func):
                    self.get_handlers[path] = func
                    return func

                return _decorator

            def post(self, path):
                def _decorator(func):
                    self.post_handlers[path] = func
                    return func

                return _decorator

        class _FakeWeb:
            @staticmethod
            def json_response(payload, status=200):
                return {"payload": payload, "status": status}

        fake_routes = _FakeRoutes()
        fake_prompt_server = types.SimpleNamespace(instance=types.SimpleNamespace(routes=fake_routes))

        monkeypatch.setitem(sys.modules, "aiohttp", types.SimpleNamespace(web=_FakeWeb))
        monkeypatch.setitem(sys.modules, "server", types.SimpleNamespace(PromptServer=fake_prompt_server))
        monkeypatch.setitem(
            sys.modules,
            "folder_paths",
            types.SimpleNamespace(get_filename_list=lambda kind: ["foo.pt", "bar.safetensors"]),
        )

        monkeypatch.setattr(autocomplete_server, "_route_registered", False)
        monkeypatch.setattr(autocomplete_server, "_local_tags_dir", lambda: tmp_path / "tags")
        monkeypatch.setattr(
            autocomplete_server,
            "_tag_sources",
            lambda: [
                autocomplete_server.TagSource("danbooru", "danbooru.csv", "BUBBA_DANBOORU_CSV_URL", "https://example.invalid/danbooru.csv"),
                autocomplete_server.TagSource("e621", "e621.csv", "BUBBA_E621_CSV_URL", "https://example.invalid/e621.csv"),
            ],
        )
        monkeypatch.setattr(autocomplete_server, "_download_upstream_csv", lambda url: f"tag,count\n{url},1\n".encode())

        autocomplete_server.register_autocomplete_routes()

        assert "/bubba/autocomplete/embeddings" in fake_routes.get_handlers
        assert "/bubba/sync_upstream_cache" in fake_routes.post_handlers

        embeddings_result = asyncio.run(fake_routes.get_handlers["/bubba/autocomplete/embeddings"](None))
        assert embeddings_result["status"] == 200
        assert embeddings_result["payload"]["count"] == 2

        sync_result = asyncio.run(fake_routes.post_handlers["/bubba/sync_upstream_cache"](None))
        assert sync_result["status"] == 200
        assert sync_result["payload"]["status"] == "ok"
        assert len(sync_result["payload"]["sources"]) == 2
        assert (tmp_path / "tags" / "danbooru.csv").exists()
        assert (tmp_path / "tags" / "e621.csv").exists()
        assert sync_result["payload"]["bytes"] == sum(source["bytes"] for source in sync_result["payload"]["sources"])
