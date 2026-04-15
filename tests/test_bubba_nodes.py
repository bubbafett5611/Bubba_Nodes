#!/usr/bin/env python

"""Tests for `bubba_nodes` package."""

import tempfile
from pathlib import Path

from src.bubba_nodes.nodes import (
    BubbaFilename,
    BubbaKSampler,
    BubbaSaveImage,
    BubbaOverlay,
    BubbaCharacterPromptBuilder,
    BubbaPromptCleaner,
    BubbaPromptPreset,
    BubbaPromptPresetSave,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from src.bubba_nodes.nodes import prompt as prompt_module


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
        assert BubbaFilename.CATEGORY == "Bubba Nodes"


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
        assert BubbaOverlay.CATEGORY == "Bubba Nodes"


class TestBubbaCharacterPromptBuilder:
    def test_hybrid_prompt_build(self):
        node = BubbaCharacterPromptBuilder()
        positive, negative, sections = node.build_prompt(
            "Lena",
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
        assert "Lena" in positive
        assert "|" in positive
        assert negative == "blurry, lowres"
        assert "character: Lena" in sections
        assert "negative: blurry, lowres" in sections
        assert "format_mode: hybrid" in sections

    def test_dedupe_case_insensitive(self):
        node = BubbaCharacterPromptBuilder()
        positive, negative, _ = node.build_prompt(
            "Hero",
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
        assert positive == "Hero, smile"
        assert negative == "badhandv4"

    def test_prose_mode(self):
        node = BubbaCharacterPromptBuilder()
        positive, _, _ = node.build_prompt(
            "Hero",
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
        assert BubbaCharacterPromptBuilder.RETURN_TYPES == ("STRING", "STRING", "STRING")
        assert BubbaCharacterPromptBuilder.FUNCTION == "build_prompt"
        assert BubbaCharacterPromptBuilder.CATEGORY == "Bubba Nodes"


class TestBubbaPromptCleaner:
    def test_clean_prompt_cleanup_and_dedupe(self):
        node = BubbaPromptCleaner()
        clean_pos, clean_neg = node.clean_prompt(
            " hero ,  smile,smile , cinematic lighting ",
            "blurry, blurry, lowres",
            True,
            True,
        )
        assert clean_pos == "hero, smile, cinematic lighting"
        assert clean_neg == "blurry, lowres"

    def test_metadata(self):
        assert BubbaPromptCleaner.RETURN_TYPES == ("STRING", "STRING")
        assert BubbaPromptCleaner.FUNCTION == "clean_prompt"
        assert BubbaPromptCleaner.CATEGORY == "Bubba Nodes"


class TestBubbaPromptPreset:
    def test_build_from_preset_with_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "prompt_presets.json"
            original = prompt_module._presets_file_path
            prompt_module._presets_file_path = lambda: temp_file
            try:
                saver = BubbaPromptPresetSave()
                saver.save_preset(
                    "HeroPreset",
                    "character: Hero\nappearance: silver hair, green eyes\nbody: athletic\nclothing: jacket\npose: standing\nexpression: focused\nscene: city rooftop\nstyle: anime style\nquality: best quality\nnegative: blurry, lowres\nformat_mode: hybrid",
                    True,
                )

                node = BubbaPromptPreset()
                positive, negative, sections, loaded_name = node.build_from_preset(
                    "HeroPreset",
                    "",
                    "",
                    "",
                    "leather coat",
                    "running",
                    "",
                    "rainy street",
                    "",
                    "",
                    "",
                    "hybrid",
                    False,
                    True,
                    True,
                )
            finally:
                prompt_module._presets_file_path = original

        assert loaded_name == "HeroPreset"
        assert "Hero" in positive
        assert "leather coat" in positive
        assert "running" in positive
        assert "rainy street" in positive
        assert "|" in positive
        assert negative == "blurry, lowres"
        assert "appearance: silver hair, green eyes" in sections
        assert "pose: running" in sections

    def test_metadata(self):
        assert BubbaPromptPreset.RETURN_TYPES == ("STRING", "STRING", "STRING", "STRING")
        assert BubbaPromptPreset.FUNCTION == "build_from_preset"
        assert BubbaPromptPreset.CATEGORY == "Bubba Nodes"


class TestBubbaPromptPresetSave:
    def test_save_preset_writes_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "prompt_presets.json"
            original = prompt_module._presets_file_path
            prompt_module._presets_file_path = lambda: temp_file
            try:
                node = BubbaPromptPresetSave()
                status, saved_name = node.save_preset(
                    "MagePreset",
                    "character: Mage\nappearance: long hair\nbody: slim\nclothing: robe\npose: casting\nexpression: calm\nscene: library\nstyle: fantasy art\nquality: high detail\nnegative: blurry\nformat_mode: booru",
                    True,
                )
            finally:
                prompt_module._presets_file_path = original

        assert "Saved preset" in status
        assert saved_name == "MagePreset"
        assert temp_file.exists()

    def test_metadata(self):
        assert BubbaPromptPresetSave.RETURN_TYPES == ("STRING", "STRING")
        assert BubbaPromptPresetSave.FUNCTION == "save_preset"
        assert BubbaPromptPresetSave.CATEGORY == "Bubba Nodes"


class TestMappings:
    def test_all_nodes_registered(self):
        assert "BubbaFilename" in NODE_CLASS_MAPPINGS
        assert "BubbaKSampler" in NODE_CLASS_MAPPINGS
        assert "BubbaSaveImage" in NODE_CLASS_MAPPINGS
        assert "BubbaOverlay" in NODE_CLASS_MAPPINGS
        assert "BubbaCharacterPromptBuilder" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptCleaner" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptPreset" in NODE_CLASS_MAPPINGS
        assert "BubbaPromptPresetSave" in NODE_CLASS_MAPPINGS

    def test_display_names_match_keys(self):
        assert NODE_CLASS_MAPPINGS.keys() == NODE_DISPLAY_NAME_MAPPINGS.keys()

    def test_class_mappings_point_to_classes(self):
        assert NODE_CLASS_MAPPINGS["BubbaFilename"] is BubbaFilename
        assert NODE_CLASS_MAPPINGS["BubbaOverlay"] is BubbaOverlay
        assert NODE_CLASS_MAPPINGS["BubbaCharacterPromptBuilder"] is BubbaCharacterPromptBuilder
        assert NODE_CLASS_MAPPINGS["BubbaPromptCleaner"] is BubbaPromptCleaner
        assert NODE_CLASS_MAPPINGS["BubbaPromptPreset"] is BubbaPromptPreset
        assert NODE_CLASS_MAPPINGS["BubbaPromptPresetSave"] is BubbaPromptPresetSave
