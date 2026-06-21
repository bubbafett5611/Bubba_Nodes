from src.bubba_nodes.models import BubbaMetadata, BubbaPipe
from src.bubba_nodes.nodes import BubbaSimplePromptBuilder
from src.bubba_nodes.utils.prompt_expansion import DEFAULT_WILDCARD_DIR, expand_prompt_text


class _DummyClip:
    def tokenize(self, text):
        return text

    def encode_from_tokens_scheduled(self, tokens):
        return [[f"COND:{tokens}", {}]]


def test_inline_choices_are_deterministic_and_field_specific():
    text = "a {red|blue|green} dress, {day|night}"

    first = expand_prompt_text(text, seed=42, field_name="positive")
    second = expand_prompt_text(text, seed=42, field_name="positive")
    negative_field = expand_prompt_text(text, seed=42, field_name="negative")

    assert first.resolved_text == second.resolved_text
    assert first.selections == second.selections
    assert len(first.selections) == 2
    assert first.resolved_text in {f"a {color} dress, {time}" for color in ("red", "blue", "green") for time in ("day", "night")}
    assert first.selections != negative_field.selections


def test_file_wildcard_selects_non_comment_line_deterministically(tmp_path):
    (tmp_path / "lighting.txt").write_text("# comment\n\nsoft light\nneon light\n", encoding="utf-8")

    first = expand_prompt_text("__lighting__", seed=9, wildcard_roots=[tmp_path])
    second = expand_prompt_text("__lighting__", seed=9, wildcard_roots=[tmp_path])

    assert first.resolved_text in {"soft light", "neon light"}
    assert first.resolved_text == second.resolved_text
    assert first.selections[0].kind == "wildcard"
    assert first.selections[0].source == "lighting"


def test_nested_wildcards_and_choices_expand_recursively(tmp_path):
    (tmp_path / "scene.txt").write_text("__lighting__, a {quiet|busy} street\n", encoding="utf-8")
    (tmp_path / "lighting.txt").write_text("golden light\n", encoding="utf-8")

    result = expand_prompt_text("__scene__", seed=12, wildcard_roots=[tmp_path])

    assert result.resolved_text in {"golden light, a quiet street", "golden light, a busy street"}
    assert [selection.kind for selection in result.selections] == ["wildcard", "choice", "wildcard"]
    assert not result.warnings


def test_missing_wildcard_remains_visible_and_reports_warning(tmp_path):
    result = expand_prompt_text("portrait, __missing__", seed=0, wildcard_roots=[tmp_path])

    assert result.resolved_text == "portrait, __missing__"
    assert result.warnings == ("Wildcard __missing__ was not found.",)


def test_recursive_wildcards_stop_safely(tmp_path):
    (tmp_path / "a.txt").write_text("__b__\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("__a__\n", encoding="utf-8")

    result = expand_prompt_text("__a__", seed=0, wildcard_roots=[tmp_path], max_depth=10)

    assert result.resolved_text in {"__a__", "__b__"}
    assert any("recursive cycle" in warning for warning in result.warnings)
    assert len(result.selections) == 2


def test_escaped_syntax_is_returned_as_literal_text(tmp_path):
    result = expand_prompt_text(
        r"\{red|blue\}, \__lighting__, {cat|dog}",
        seed=3,
        wildcard_roots=[tmp_path],
    )

    assert result.resolved_text.startswith("{red|blue}, __lighting__, ")
    assert result.resolved_text.endswith(("cat", "dog"))
    assert len(result.selections) == 1
    assert not result.warnings


def test_simple_prompt_builder_expands_before_cleanup_and_dedupe(tmp_path, monkeypatch):
    import src.bubba_nodes.utils.prompt_expansion as expansion_module

    (tmp_path / "quality.txt").write_text("hero, HERO\n", encoding="utf-8")
    monkeypatch.setattr(expansion_module, "DEFAULT_WILDCARD_DIR", tmp_path)

    node = BubbaSimplePromptBuilder()
    pipe, metadata, positive, negative, positive_text, negative_text, report = node.build_prompt(
        "__quality__, {smile|grin}, smile",
        "blurry, BLURRY",
        True,
        True,
        prompt_seed=4,
        clip=_DummyClip(),
    )

    assert positive_text in {"hero, smile", "hero, grin, smile"}
    assert negative_text == "blurry"
    assert positive[0][0] == f"COND:{positive_text}"
    assert negative[0][0] == "COND:blurry"
    assert metadata.positive_prompt == positive_text
    assert pipe.positive_prompt == positive_text
    assert "Positive raw:" in report
    assert "Positive resolved:" in report
    assert "Positive final:" in report


def test_simple_prompt_builder_inherits_metadata_seed():
    pipe = BubbaPipe(clip=_DummyClip(), metadata=BubbaMetadata(seed=123))
    node = BubbaSimplePromptBuilder()

    first = node.build_prompt("{red|blue|green}", "", True, True, prompt_seed=-1, pipe=pipe)
    second = node.build_prompt("{red|blue|green}", "", True, True, prompt_seed=123, pipe=pipe)

    assert first[4] == second[4]
    assert "expansion seed: 123" in first[6]


def test_simple_prompt_builder_prompt_seed_has_after_generate_control():
    prompt_seed = BubbaSimplePromptBuilder.INPUT_TYPES()["required"]["prompt_seed"]

    assert prompt_seed[0] == "INT"
    assert prompt_seed[1]["control_after_generate"] is True
    assert prompt_seed[1]["min"] == -1


def test_bundled_sample_wildcards_are_available():
    assert (DEFAULT_WILDCARD_DIR / "lighting.txt").is_file()
    assert (DEFAULT_WILDCARD_DIR / "outfits.txt").is_file()
    assert (DEFAULT_WILDCARD_DIR / "locations" / "nightclub.txt").is_file()
