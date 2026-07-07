import json
import re
from pathlib import Path

from src.bubba_nodes.models import BubbaMetadata, BubbaPipe
from src.bubba_nodes.nodes import (
    V3_NODE_CLASSES,
    BubbaConditioningMultiply,
    BubbaKSampler,
    BubbaLoraLoader,
    BubbaLoraStack,
    BubbaSaveImage,
)
from src.bubba_nodes.utils.progress import ProgressReporter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "node_schema_compat.json"
LEGACY_WORKFLOW_PATH = PROJECT_ROOT / "tests" / "fixtures" / "legacy_workflow_all_nodes.json"
PRIVATE_COMFY_IMPORT_RE = re.compile(r"comfy_api\.(?:latest|v\d+_\d+_\d+)\._")
INTERNAL_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(nodes|folder_paths|server|node_helpers|comfy(?:\.[\w.]+)?|comfy_extras(?:\.[\w.]+)?)|"
    r"import\s+(nodes|folder_paths|server|node_helpers|comfy(?:\.[\w.]+)?|comfy_extras(?:\.[\w.]+)?))\b"
)
INTERNAL_IMPORT_ALLOWLIST = {
    "src/bubba_nodes/compat/checkpoint_io.py",
    "src/bubba_nodes/compat/core_nodes.py",
    "src/bubba_nodes/compat/paths.py",
    "src/bubba_nodes/compat/routes.py",
    "src/bubba_nodes/compat/runtime.py",
    "src/bubba_nodes/compat/sampling.py",
}


def _schema_snapshot():
    snapshot = {}
    for node_class in V3_NODE_CLASSES:
        schema = node_class.GET_SCHEMA()
        node_id = schema.node_id
        inputs = [{"name": item.id, "type": item.io_type, "optional": item.optional} for item in schema.inputs]
        outputs = [{"name": item.id, "type": item.io_type} for item in schema.outputs]
        snapshot[node_id] = {
            "display_name": schema.display_name,
            "category": schema.category,
            "inputs": inputs,
            "outputs": outputs,
        }
    return snapshot


def test_node_schema_matches_golden_fixture():
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert _schema_snapshot() == expected


def test_manifest_declares_minimum_supported_comfyui_version():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-comfyui = ">=0.27.0"' in pyproject


def test_no_underscored_comfy_api_imports():
    offenders = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if ".test_tmp" in path.parts or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if PRIVATE_COMFY_IMPORT_RE.search(text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"))
    assert offenders == []


def test_v3_registration_contains_only_native_node_classes():
    assert not (PROJECT_ROOT / "src" / "bubba_nodes" / "compat" / "v3.py").exists()

    registry_text = (PROJECT_ROOT / "src" / "bubba_nodes" / "nodes" / "__init__.py").read_text(encoding="utf-8")
    assert "make_v3_node" not in registry_text
    assert "compat.v3" not in registry_text

    assert len(V3_NODE_CLASSES) == 37
    for node_class in V3_NODE_CLASSES:
        assert "comfy_api.latest" in (PROJECT_ROOT / Path(node_class.__module__.replace(".", "/") + ".py")).read_text(encoding="utf-8")


def test_node_modules_have_one_top_level_public_api_import():
    for node_class in V3_NODE_CLASSES:
        path = PROJECT_ROOT / Path(node_class.__module__.replace(".", "/") + ".py")
        lines = path.read_text(encoding="utf-8").splitlines()
        imports = [index for index, line in enumerate(lines) if line.startswith("from comfy_api.latest import ")]
        class_line = next(index for index, line in enumerate(lines) if line.startswith("class Bubba"))
        assert len(imports) == 1, path.name
        assert imports[0] < class_line, path.name


def test_saved_legacy_workflow_class_ids_still_resolve_without_replacement():
    fixture_by_id = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    legacy_workflow = json.loads(LEGACY_WORKFLOW_PATH.read_text(encoding="utf-8"))
    v3_by_id = {cls.GET_SCHEMA().node_id: cls for cls in V3_NODE_CLASSES if hasattr(cls, "GET_SCHEMA")}

    for node in legacy_workflow["nodes"]:
        assert node["type"] in fixture_by_id
        assert node["type"] in v3_by_id

    assert set(v3_by_id) == set(fixture_by_id)

    assert fixture_by_id["BubbaSaveImage"]["outputs"][-2]["name"] == "saved_paths"
    assert fixture_by_id["BubbaSaveImage"]["outputs"][-1]["name"] == "info"
    if v3_by_id:
        assert v3_by_id["BubbaSaveImage"].GET_SCHEMA().outputs[-2].id == "saved_paths"
        assert v3_by_id["BubbaSaveImage"].GET_SCHEMA().outputs[-1].id == "info"


def test_v3_save_passes_node_class_to_public_ui_helpers(monkeypatch):
    captured = {}

    class _Preview:
        def as_dict(self):
            return {"images": []}

    def _preview_image(images, cls=None):
        captured["preview_cls"] = cls
        return _Preview()

    def _save_images_ui(images, filename_prefix, cls=None):
        captured["save_cls"] = cls
        return _Preview()

    monkeypatch.setattr("src.bubba_nodes.nodes.save_image.UI.PreviewImage", _preview_image)
    monkeypatch.setattr("src.bubba_nodes.nodes.save_image.UI.ImageSaveHelper.get_save_images_ui", _save_images_ui)

    BubbaSaveImage.execute(images=[object()], preview_only=True)
    BubbaSaveImage.execute(images=[object()], preview_only=False)

    assert captured == {"preview_cls": BubbaSaveImage, "save_cls": BubbaSaveImage}


def test_frontend_extensions_reference_current_output_contracts():
    web_root = PROJECT_ROOT / "web" / "comfyui"
    metadata_debug = (web_root / "metadata_debug_node.js").read_text(encoding="utf-8")
    view_text = (web_root / "view_text_node.js").read_text(encoding="utf-8")
    image_compare = (web_root / "image_compare_node.js").read_text(encoding="utf-8")
    checkpoint_menu = (web_root / "checkpoint_menu.js").read_text(encoding="utf-8")
    lora_menu = (web_root / "lora_menu.js").read_text(encoding="utf-8")
    warnings = (web_root / "save_result_warnings.js").read_text(encoding="utf-8")
    seed_button = (web_root / "sampler_seed_button.js").read_text(encoding="utf-8")

    assert "BubbaMetadataDebug" in metadata_debug
    assert "metadata_text" in metadata_debug
    assert "BubbaViewText" in view_text
    assert "output?.text" in view_text
    assert "BubbaImageCompare" in image_compare
    assert "b64_a" in image_compare and "b64_b" in image_compare
    assert "BubbaModelCompareLoader" in checkpoint_menu
    assert "model_[1-4]" in checkpoint_menu
    assert "BubbaLoraLoader" in lora_menu
    assert "metadata_warnings" in warnings
    assert "BubbaSeedControl" in seed_button
    assert "Manual Random Seed" in seed_button
    assert "migrateLegacySeedControlOutputs" in seed_button
    assert "link.origin_slot -= 2" in seed_button


def test_internal_comfy_imports_stay_inside_compat_boundary():
    offenders = []
    for path in PROJECT_ROOT.joinpath("src").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if INTERNAL_IMPORT_RE.search(line) and rel not in INTERNAL_IMPORT_ALLOWLIST:
                offenders.append(f"{rel}:{line_number}:{line.strip()}")
    assert offenders == []


def test_every_compatibility_module_is_documented_and_allowlisted():
    compat_root = PROJECT_ROOT / "src" / "bubba_nodes" / "compat"
    actual = {str(path.relative_to(PROJECT_ROOT)).replace("\\", "/") for path in compat_root.glob("*.py") if path.name != "__init__.py"}
    design = (PROJECT_ROOT / "docs" / "comfyui_modernization_design.md").read_text(encoding="utf-8")

    assert actual == INTERNAL_IMPORT_ALLOWLIST
    for path in actual:
        assert f"`{Path(path).name}`" in design


def test_conditioning_multiply_preserves_pipe_and_delegates(monkeypatch):
    positive = [("positive", {})]
    negative = [("negative", {})]
    metadata = BubbaMetadata(seed=123)
    pipe = BubbaPipe(positive=positive, negative=negative, metadata=metadata)

    calls = []

    def _multiply(conditioning, multiplier):
        calls.append((conditioning, multiplier))
        return [(conditioning[0][0], {"multiplier": multiplier})]

    monkeypatch.setattr("src.bubba_nodes.nodes.conditioning_multiply.multiply_conditioning", _multiply)

    result_pipe, result_metadata, result_positive, result_negative, info = BubbaConditioningMultiply().execute(
        0.5,
        1.25,
        "both",
        pipe=pipe,
    )

    assert calls == [(positive, 0.5), (negative, 1.25)]
    assert result_pipe.positive is result_positive
    assert result_pipe.negative is result_negative
    assert result_pipe.metadata == result_metadata == metadata
    assert "mode=both" in info


def test_sampler_preserves_quantized_or_offloaded_model_identity(monkeypatch):
    model = SimpleQuantizedModel()
    latent_in = {"samples": object()}
    latent_out = {"samples": object()}

    def _sample(passed_model, *args, **kwargs):
        assert passed_model is model
        return (latent_out,)

    monkeypatch.setattr("src.bubba_nodes.nodes.k_sampler.common_ksampler", _sample)

    pipe, image, latent, metadata, _info = BubbaKSampler().execute(
        seed=1,
        steps=2,
        cfg=3.0,
        sampler_name="euler",
        scheduler="normal",
        denoise=0.5,
        model=model,
        positive=[],
        negative=[],
        latent_image=latent_in,
    )

    assert pipe.model is model
    assert image is None
    assert latent is latent_out
    assert metadata.seed == 1


def test_lora_loader_delegates_without_rebuilding_model_or_clip(monkeypatch):
    model = SimpleQuantizedModel()
    clip = object()
    applied_model = SimpleQuantizedModel()
    applied_clip = object()
    node = BubbaLoraLoader()
    loader = SimpleLoraApplier(applied_model, applied_clip)
    monkeypatch.setattr("src.bubba_nodes.nodes.lora_loader.LoraApplier", lambda: loader)

    pipe, metadata, model_out, clip_out, _name = node.execute(
        "style.safetensors",
        0.75,
        0.25,
        model=model,
        clip=clip,
    )

    assert loader.calls == [(model, clip, "style.safetensors", 0.75, 0.25)]
    assert model_out is applied_model
    assert clip_out is applied_clip
    assert pipe.model is applied_model
    assert pipe.clip is applied_clip
    assert metadata.loras == ["style"]


class SimpleQuantizedModel:
    quantization = "int8-convrot"
    offload_state = object()
    fp8_state = object()
    async_loading_state = object()


class SimpleLoraApplier:
    def __init__(self, model_out, clip_out):
        self.model_out = model_out
        self.clip_out = clip_out
        self.calls = []

    def apply(self, model, clip, lora_name, strength_model, strength_clip):
        self.calls.append((model, clip, lora_name, strength_model, strength_clip))
        return self.model_out, self.clip_out


def test_lora_stack_applies_enabled_slots_in_order(monkeypatch):
    calls = []

    class _Recorder:
        def apply(self, model, clip, name, strength_model, strength_clip):
            calls.append((model, clip, name, strength_model, strength_clip))
            return f"{model}>{name}", f"{clip}>{name}"

    monkeypatch.setattr("src.bubba_nodes.nodes.lora_stack.LoraApplier", _Recorder)
    pipe, metadata, model, clip, names, _info = BubbaLoraStack.execute(
        model="model",
        clip="clip",
        lora_1_name="first.safetensors",
        lora_1_strength_model=0.5,
        lora_1_strength_clip=0.25,
        lora_1_enabled=True,
        lora_2_name="skipped.safetensors",
        lora_2_enabled=False,
        lora_3_name="third.safetensors",
        lora_3_strength_model=1.5,
        lora_3_strength_clip=1.25,
        lora_3_enabled=True,
    )

    assert [call[2] for call in calls] == ["first.safetensors", "third.safetensors"]
    assert calls[1][:2] == ("model>first.safetensors", "clip>first.safetensors")
    assert pipe.model == model == "model>first.safetensors>third.safetensors"
    assert pipe.clip == clip == "clip>first.safetensors>third.safetensors"
    assert metadata.loras == ["first", "third"]
    assert names == "first, third"


def test_public_progress_is_safe_without_execution_context(monkeypatch):
    import src.bubba_nodes.utils.progress as progress_module
    from types import SimpleNamespace

    calls = []

    def _set_progress(value, maximum, preview_image=None):
        calls.append((value, maximum, preview_image))

    monkeypatch.setattr(progress_module, "ComfyAPISync", SimpleNamespace(execution=SimpleNamespace(set_progress=_set_progress)))
    reporter = ProgressReporter(2)
    reporter.update(preview_image="preview")
    reporter.update()

    assert calls == [(0, 2, None), (1, 2, "preview"), (2, 2, None)]


def test_register_all_routes_dispatches_each_registration(monkeypatch):
    from src.bubba_nodes import server

    calls = []
    monkeypatch.setattr(server, "register_checkpoint_preview_route", lambda: calls.append("checkpoint"))
    monkeypatch.setattr(server, "register_autocomplete_routes", lambda: calls.append("autocomplete"))
    monkeypatch.setattr(server, "register_discord_webhook_routes", lambda: calls.append("discord"))

    server.register_all_routes()
    server.register_all_routes()

    assert calls == ["checkpoint", "autocomplete", "discord", "checkpoint", "autocomplete", "discord"]
