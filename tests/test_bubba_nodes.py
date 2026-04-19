#!/usr/bin/env python

"""Tests for `bubba_nodes` package."""

# TODO(optimize): Add parametrized performance-focused tests for prompt cleaning and overlay text wrapping hot paths.
# TODO(new-feature): Add integration tests that validate metadata persistence across save -> load for multi-image batches.

import json

import pytest

from src.bubba_nodes.nodes import (
    BubbaFilename,
    BubbaEmptyLatentBySize,
    BubbaLoadImageWithMetadata,
    BubbaCheckpointLoader,
    BubbaKSampler,
    BubbaSaveImage,
    BubbaOverlay,
    BubbaOverlayFromMetadata,
    BubbaWatermark,
    BubbaMetadataBundle,
    BubbaMetadataDebug,
    BubbaMetadataUpdate,
    BubbaCharacterPromptBuilder,
    BubbaMetadataPromptBuilder,
    BubbaPromptCleaner,
    BubbaPromptInspector,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from src.bubba_nodes.models import BubbaMetadata


class _DummyClip:
    def tokenize(self, text):
        return text

    def encode_from_tokens_scheduled(self, tokens):
        return [[f"COND:{tokens}", {}]]


class TestBubbaFilename:
    def test_basic_path(self):
        node = BubbaFilename()
        result, = node.build_path("My Character", "Battle Scene")
        assert result == "My_Character/Battle_Scene"

    def test_invalid_chars_stripped(self):
        node = BubbaFilename()
        result, = node.build_path("Hero<>:", "Scene?*")
        assert result == "Hero/Scene"

    def test_empty_character_falls_back(self):
        node = BubbaFilename()
        result, = node.build_path("", "Scene")
        assert result == "Character/Scene"

    def test_empty_scene_falls_back(self):
        node = BubbaFilename()
        result, = node.build_path("Hero", "")
        assert result == "Hero/Scene"

    def test_only_invalid_chars_falls_back(self):
        node = BubbaFilename()
        result, = node.build_path("<>:/\\", "?*|")
        assert result == "Character/Scene"

    def test_metadata(self):
        assert BubbaFilename.RETURN_TYPES == ("STRING",)
        assert BubbaFilename.FUNCTION == "build_path"
        assert BubbaFilename.CATEGORY == "Bubba Nodes/Workflow"


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

    def test_metadata(self):
        assert BubbaLoadImageWithMetadata.RETURN_TYPES == ("IMAGE", "MASK", "BUBBA_METADATA", "STRING")
        assert BubbaLoadImageWithMetadata.FUNCTION == "load_image"
        assert BubbaLoadImageWithMetadata.CATEGORY == "Bubba Nodes/Image/Load"


class TestBubbaCheckpointLoader:
    def test_metadata(self):
        assert BubbaCheckpointLoader.RETURN_TYPES == ("MODEL", "CLIP", "VAE", "STRING")
        assert BubbaCheckpointLoader.FUNCTION == "load_checkpoint_with_name"
        assert BubbaCheckpointLoader.CATEGORY == "Bubba Nodes/Generation"


class TestBubbaKSampler:
    def test_metadata(self):
        assert BubbaKSampler.RETURN_TYPES == ("LATENT", "STRING", "BUBBA_METADATA")
        assert BubbaKSampler.FUNCTION == "sample"
        assert BubbaKSampler.CATEGORY == "Bubba Nodes/Generation"


class TestBubbaOverlay:
    def test_parse_rgba_six_chars(self):
        assert BubbaOverlay._parse_rgba("#FF8800") == (255, 136, 0, 255)

    def test_parse_rgba_eight_chars(self):
        assert BubbaOverlay._parse_rgba("#000000AA") == (0, 0, 0, 170)

    def test_parse_rgba_invalid_falls_back(self):
        assert BubbaOverlay._parse_rgba("#ZZZZZZ") == (0, 0, 0, 170)

    def test_parse_rgba_empty_falls_back(self):
        assert BubbaOverlay._parse_rgba("") == (0, 0, 0, 170)

    def test_parse_rgba_garbage_falls_back(self):
        assert BubbaOverlay._parse_rgba("not-a-color") == (0, 0, 0, 170)

    def test_metadata(self):
        assert BubbaOverlay.RETURN_TYPES == ("IMAGE",)
        assert BubbaOverlay.FUNCTION == "add_text_overlay"
        assert BubbaOverlay.CATEGORY == "Bubba Nodes/Image/Overlay"


class TestBubbaOverlayFromMetadata:
    def test_extract_fields_valid_metadata_object(self):
        payload = BubbaMetadata(
            model_name="myModel",
            sampler_info="Time: 1.0s Seed: 123",
            positive_prompt="hero, dramatic lighting",
            negative_prompt="blurry",
        )
        model_text, info_text, positive_text, negative_text = BubbaOverlayFromMetadata._extract_fields(payload)

        assert model_text == "myModel"
        assert info_text == "Time: 1.0s Seed: 123"
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


class TestBubbaMetadataBundle:
    def test_build_metadata_object(self):
        node = BubbaMetadataBundle()
        metadata, = node.build_metadata(
            "novaFurryXL_ilV160",
            "Time: 1.23s Seed: 42",
            "1girl, hoodie",
            "blurry",
            42,
            "Character/Scene",
        )
        assert isinstance(metadata, BubbaMetadata)
        assert metadata.model_name == "novaFurryXL_ilV160"
        assert metadata.sampler_info == "Time: 1.23s Seed: 42"
        assert metadata.positive_prompt == "1girl, hoodie"
        assert metadata.negative_prompt == "blurry"
        assert metadata.seed == 42
        assert metadata.filepath == "Character/Scene"

    def test_metadata(self):
        assert BubbaMetadataBundle.RETURN_TYPES == ("BUBBA_METADATA",)
        assert BubbaMetadataBundle.FUNCTION == "build_metadata"
        assert BubbaMetadataBundle.CATEGORY == "Bubba Nodes/Metadata"


class TestBubbaMetadataDebug:
    def test_debug_metadata_returns_pretty_json(self):
        node = BubbaMetadataDebug()
        metadata = BubbaMetadata(
            model_name="myModel",
            sampler_info="Time: 0.2s",
            positive_prompt="hero",
            negative_prompt="blurry",
            seed=9,
            filepath="Character/Scene",
        )
        metadata_text, = node.debug_metadata(metadata)
        payload = json.loads(metadata_text)

        assert payload["model_name"] == "myModel"
        assert payload["seed"] == 9

    def test_metadata(self):
        assert BubbaMetadataDebug.RETURN_TYPES == ("STRING",)
        assert BubbaMetadataDebug.FUNCTION == "debug_metadata"
        assert BubbaMetadataDebug.CATEGORY == "Bubba Nodes/Metadata"


class TestBubbaMetadataUpdate:
    def test_update_selected_fields(self):
        node = BubbaMetadataUpdate()
        original = BubbaMetadata(model_name="old", seed=1, filepath="old/path")
        updated, seed_value, positive_cond, negative_cond = node.update_metadata(
            original,
            model_name="new",
            sampler_info="Time: 1.2s",
            set_seed=True,
            seed=42,
            filepath="new/path",
        )

        assert updated.model_name == "new"
        assert updated.sampler_info == "Time: 1.2s"
        assert updated.seed == 42
        assert updated.filepath == "new/path"
        assert seed_value == 42
        assert positive_cond == [[None, {}]]
        assert negative_cond == [[None, {}]]

    def test_update_outputs_conditioning_with_clip(self):
        node = BubbaMetadataUpdate()
        original = BubbaMetadata(positive_prompt="hero", negative_prompt="blurry", seed=9)

        updated, seed_value, positive_cond, negative_cond = node.update_metadata(
            original,
            clip=_DummyClip(),
        )

        assert updated.seed == 9
        assert seed_value == 9
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")

    def test_metadata(self):
        assert BubbaMetadataUpdate.RETURN_TYPES == ("BUBBA_METADATA", "INT", "CONDITIONING", "CONDITIONING")
        assert BubbaMetadataUpdate.FUNCTION == "update_metadata"
        assert BubbaMetadataUpdate.CATEGORY == "Bubba Nodes/Metadata"


class TestBubbaMetadataModel:
    def test_from_json_normalizes_types_and_whitespace(self):
        metadata = BubbaMetadata.from_json(
            '{"model_name":" modelA ","sampler_info":" info ","sampler_time_seconds":"0.57","steps":"25","cfg":"7.5","sampler_name":" dpmpp_2m ","scheduler":" karras ","denoise":"1.0","positive_prompt":" pos ","negative_prompt":" neg ","seed":"123","filepath":" folder/file ","prompt_sections":" appearance: silver hair "}'
        )

        assert metadata.model_name == "modelA"
        assert metadata.sampler_info == "info"
        assert metadata.sampler_time_seconds == 0.57
        assert metadata.steps == 25
        assert metadata.cfg == 7.5
        assert metadata.sampler_name == "dpmpp_2m"
        assert metadata.scheduler == "karras"
        assert metadata.denoise == 1.0
        assert metadata.positive_prompt == "pos"
        assert metadata.negative_prompt == "neg"
        assert metadata.seed == 123
        assert metadata.filepath == "folder/file"
        assert metadata.prompt_sections == "appearance: silver hair"

    def test_from_json_invalid_payload_falls_back(self):
        metadata = BubbaMetadata.from_json("not-json")

        assert metadata.model_name == ""
        assert metadata.sampler_info == ""
        assert metadata.positive_prompt == ""
        assert metadata.negative_prompt == ""
        assert metadata.seed == 0
        assert metadata.filepath == ""

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
            filepath="Character/Scene",
            prompt_sections="appearance: silver hair",
        )
        payload = json.loads(metadata.to_json())

        assert payload["model_name"] == "myModel"
        assert payload["sampler_info"] == "Time: 0.100s  Seed: 7  Steps: 20  CFG: 8.0  Sampler: dpmpp_2m  Scheduler: karras  Denoise: 1.0"
        assert payload["sampler_time_seconds"] == 0.1
        assert payload["steps"] == 20
        assert payload["cfg"] == 8.0
        assert payload["sampler_name"] == "dpmpp_2m"
        assert payload["scheduler"] == "karras"
        assert payload["denoise"] == 1.0
        assert payload["positive_prompt"] == "hero"
        assert payload["negative_prompt"] == "blurry"
        assert payload["seed"] == 7
        assert payload["filepath"] == "Character/Scene"
        assert payload["prompt_sections"] == "appearance: silver hair"

    def test_updated_returns_normalized_copy(self):
        metadata = BubbaMetadata(model_name="old", seed=1)
        updated = metadata.updated(model_name=" new ", seed="9")

        assert updated.model_name == "new"
        assert updated.seed == 9
        assert metadata.model_name == "old"


class TestBubbaCharacterPromptBuilder:
    def test_hybrid_prompt_build(self):
        node = BubbaCharacterPromptBuilder()
        positive, negative, sections, positive_cond, negative_cond = node.build_prompt(
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
        assert "character: " in sections
        assert "negative: blurry, lowres" in sections
        assert "format_mode: hybrid" in sections
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
        assert BubbaCharacterPromptBuilder.RETURN_TYPES == ("STRING", "STRING", "STRING", "CONDITIONING", "CONDITIONING")
        assert BubbaCharacterPromptBuilder.FUNCTION == "build_prompt"
        assert BubbaCharacterPromptBuilder.CATEGORY == "Bubba Nodes/Prompt"


class TestBubbaMetadataPromptBuilder:
    def test_build_prompt_updates_metadata(self):
        node = BubbaMetadataPromptBuilder()
        metadata_in = BubbaMetadata(model_name="modelA", filepath="Character/Scene")

        metadata_out, positive, negative, sections, positive_cond, negative_cond = node.build_prompt(
            metadata_in,
            _DummyClip(),
            "silver hair",
            "athletic",
            "jacket",
            "standing",
            "smile",
            "city rooftop",
            "anime",
            "best quality",
            "blurry",
            "hybrid",
            True,
            True,
        )

        assert isinstance(metadata_out, BubbaMetadata)
        assert "silver hair" in positive
        assert negative == "blurry"
        assert "appearance: silver hair" in sections
        assert metadata_out.positive_prompt == positive
        assert metadata_out.negative_prompt == negative
        assert metadata_out.prompt_sections == sections
        assert positive_cond[0][0].startswith("COND:")
        assert negative_cond[0][0].startswith("COND:")

    def test_metadata(self):
        assert BubbaMetadataPromptBuilder.RETURN_TYPES == ("BUBBA_METADATA", "STRING", "STRING", "STRING", "CONDITIONING", "CONDITIONING")
        assert BubbaMetadataPromptBuilder.FUNCTION == "build_prompt"
        assert BubbaMetadataPromptBuilder.CATEGORY == "Bubba Nodes/Prompt"


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
        assert "BubbaSaveImage" in NODE_CLASS_MAPPINGS
        assert "BubbaOverlay" in NODE_CLASS_MAPPINGS
        assert "BubbaOverlayFromMetadata" in NODE_CLASS_MAPPINGS
        assert "BubbaWatermark" in NODE_CLASS_MAPPINGS
        assert "BubbaMetadataBundle" in NODE_CLASS_MAPPINGS
        assert "BubbaMetadataDebug" in NODE_CLASS_MAPPINGS
        assert "BubbaMetadataUpdate" in NODE_CLASS_MAPPINGS
        assert "BubbaCharacterPromptBuilder" in NODE_CLASS_MAPPINGS
        assert "BubbaMetadataPromptBuilder" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptCleaner" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptInspector" in NODE_CLASS_MAPPINGS

    def test_display_names_match_keys(self):
        assert NODE_CLASS_MAPPINGS.keys() == NODE_DISPLAY_NAME_MAPPINGS.keys()

    def test_class_mappings_point_to_classes(self):
        assert NODE_CLASS_MAPPINGS["BubbaFilename"] is BubbaFilename
        assert NODE_CLASS_MAPPINGS["BubbaEmptyLatentBySize"] is BubbaEmptyLatentBySize
        assert NODE_CLASS_MAPPINGS["BubbaLoadImageWithMetadata"] is BubbaLoadImageWithMetadata
        assert NODE_CLASS_MAPPINGS["BubbaCheckpointLoader"] is BubbaCheckpointLoader
        assert NODE_CLASS_MAPPINGS["BubbaOverlay"] is BubbaOverlay
        assert NODE_CLASS_MAPPINGS["BubbaOverlayFromMetadata"] is BubbaOverlayFromMetadata
        assert NODE_CLASS_MAPPINGS["BubbaMetadataBundle"] is BubbaMetadataBundle
        assert NODE_CLASS_MAPPINGS["BubbaMetadataDebug"] is BubbaMetadataDebug
        assert NODE_CLASS_MAPPINGS["BubbaMetadataUpdate"] is BubbaMetadataUpdate
        assert NODE_CLASS_MAPPINGS["BubbaCharacterPromptBuilder"] is BubbaCharacterPromptBuilder
        assert NODE_CLASS_MAPPINGS["BubbaMetadataPromptBuilder"] is BubbaMetadataPromptBuilder
        assert NODE_CLASS_MAPPINGS["BubbaPromptCleaner"] is BubbaPromptCleaner
        assert NODE_CLASS_MAPPINGS["BubbaPromptInspector"] is BubbaPromptInspector
