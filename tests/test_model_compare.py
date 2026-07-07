import pytest
import torch

import src.bubba_nodes.nodes.model_components_override as components_module
import src.bubba_nodes.nodes.model_compare_loader as loader_module
from src.bubba_nodes.models import BubbaMetadata, BubbaPipe
from src.bubba_nodes.nodes.model_components_override import BubbaModelComponentsOverride
from src.bubba_nodes.nodes.model_compare_loader import BubbaModelCompareLoader
from src.bubba_nodes.nodes.model_compare_sheet import BubbaModelCompareSheet


def _image(width, height, value=0.5):
    return torch.full((1, height, width, 3), value, dtype=torch.float32)


def test_compare_loader_loads_four_independent_pipes(monkeypatch):
    loads = []

    def load_checkpoint(name):
        loads.append(name)
        return f"model:{name}", f"clip:{name}", f"vae:{name}"

    monkeypatch.setattr(loader_module, "load_checkpoint", load_checkpoint)
    result = BubbaModelCompareLoader.execute("one.safetensors", "two.ckpt", "folder/three.safetensors", "four.safetensors")

    pipes = result.result[:4]
    assert loads == ["one.safetensors", "two.ckpt", "folder/three.safetensors", "four.safetensors"]
    assert [pipe.metadata.model_name for pipe in pipes] == ["one", "two", "three", "four"]
    assert pipes[2].model == "model:folder/three.safetensors"
    assert pipes[2].clip == "clip:folder/three.safetensors"
    assert pipes[2].vae == "vae:folder/three.safetensors"


def test_compare_loader_skips_none_slots_and_keeps_stable_outputs(monkeypatch):
    loads = []
    monkeypatch.setattr(
        loader_module,
        "load_checkpoint",
        lambda name: loads.append(name) or (f"model:{name}", f"clip:{name}", f"vae:{name}"),
    )
    source = BubbaPipe(latent={"samples": torch.zeros((1, 4, 8, 8))}, metadata=BubbaMetadata(seed=5))

    result = BubbaModelCompareLoader.execute("one.safetensors", "None", "three.safetensors", "None", pipe=source)
    pipes = result.result[:4]

    assert loads == ["one.safetensors", "three.safetensors"]
    assert [item.model for item in pipes] == ["model:one.safetensors", None, "model:three.safetensors", None]
    assert [item.metadata.model_name for item in pipes] == ["one", "", "three", ""]
    assert all(item.metadata.seed == 5 for item in pipes)
    assert "one | three" in result.result[4]


def test_compare_loader_requires_one_selected_model(monkeypatch):
    monkeypatch.setattr(loader_module, "load_checkpoint", lambda _name: pytest.fail("No model should load"))
    with pytest.raises(ValueError, match="at least one selected model"):
        BubbaModelCompareLoader.execute("None", "None", "None", "None")


def test_compare_loader_schema_has_stable_four_model_contract():
    schema = BubbaModelCompareLoader.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "pipe",
        "model_1",
        "model_2",
        "model_3",
        "model_4",
        "replace_clip",
        "replace_vae",
    ]
    assert schema.inputs[0].optional is True
    model_inputs = schema.inputs[1:5]
    assert all(item.options[0] == "None" for item in model_inputs)
    assert [item.default for item in model_inputs[1:]] == ["None", "None", "None"]
    assert [item.id for item in schema.outputs] == ["pipe_1", "pipe_2", "pipe_3", "pipe_4", "info"]


def test_compare_loader_forks_source_pipe_state_and_resets_conditioning(monkeypatch):
    monkeypatch.setattr(loader_module, "load_checkpoint", lambda name: (f"model:{name}", f"clip:{name}", f"vae:{name}"))
    latent_samples = torch.zeros((1, 4, 8, 8))
    source = BubbaPipe(
        positive="old-positive",
        negative="old-negative",
        positive_prompt="same prompt",
        negative_prompt="same negative",
        image=_image(8, 8),
        mask=torch.ones((1, 8, 8)),
        latent={"samples": latent_samples, "batch_index": [0]},
        metadata=BubbaMetadata(seed=42, steps=20, model_name="old"),
    )

    result = BubbaModelCompareLoader.execute("one", "two", "three", "four", pipe=source)
    pipes = result.result[:4]

    assert [item.metadata.model_name for item in pipes] == ["one", "two", "three", "four"]
    assert all(item.metadata.seed == 42 and item.metadata.steps == 20 for item in pipes)
    assert all(item.positive_prompt == "same prompt" and item.negative_prompt == "same negative" for item in pipes)
    assert all(item.image is source.image and item.mask is source.mask for item in pipes)
    assert all(item.positive is None and item.negative is None for item in pipes)
    assert all(item.latent is not source.latent for item in pipes)
    assert all(item.latent["samples"] is not latent_samples for item in pipes)
    assert pipes[0].latent["samples"] is not pipes[1].latent["samples"]


def test_compare_loader_can_preserve_pipe_clip_vae_and_conditioning(monkeypatch):
    monkeypatch.setattr(loader_module, "load_checkpoint", lambda name: (f"model:{name}", f"clip:{name}", f"vae:{name}"))
    source = BubbaPipe(model="old-model", clip="external-clip", vae="external-vae", positive="positive", negative="negative")

    result = BubbaModelCompareLoader.execute(
        "one",
        "two",
        "three",
        "four",
        replace_clip=False,
        replace_vae=False,
        pipe=source,
    )

    for index, item in enumerate(result.result[:4], start=1):
        assert item.model == f"model:{['one', 'two', 'three', 'four'][index - 1]}"
        assert item.clip == "external-clip"
        assert item.vae == "external-vae"
        assert item.positive == "positive" and item.negative == "negative"


@pytest.mark.parametrize(
    ("source", "kwargs", "message"),
    [
        (BubbaPipe(vae="vae"), {"replace_clip": False}, "incoming pipe has no CLIP"),
        (BubbaPipe(clip="clip"), {"replace_vae": False}, "incoming pipe has no VAE"),
    ],
)
def test_compare_loader_requires_preserved_components(monkeypatch, source, kwargs, message):
    monkeypatch.setattr(loader_module, "load_checkpoint", lambda name: (f"model:{name}", f"clip:{name}", f"vae:{name}"))
    with pytest.raises(ValueError, match=message):
        BubbaModelCompareLoader.execute("one", "two", "three", "four", pipe=source, **kwargs)


class _Clip:
    def __init__(self, name):
        self.name = name
        self.layer = None

    def clone(self):
        return _Clip(f"{self.name}:clone")

    def clip_layer(self, layer):
        self.layer = layer


def test_component_override_can_keep_pipe_components():
    clip = _Clip("checkpoint")
    source = BubbaPipe(
        model="model",
        clip=clip,
        vae="checkpoint-vae",
        positive="stale-positive",
        negative="stale-negative",
        metadata=BubbaMetadata(model_name="Anima", seed=9),
    )

    result = BubbaModelComponentsOverride.execute(source)
    pipe, metadata, model, result_clip, vae, info = result.result

    assert model == "model"
    assert result_clip is clip
    assert vae == "checkpoint-vae"
    assert pipe.positive is None and pipe.negative is None
    assert metadata.model_name == "Anima" and metadata.seed == 9
    assert "pipe CLIP" in info and "pipe VAE" in info


def test_component_override_replaces_clip_and_vae_and_applies_skip(monkeypatch):
    loaded_clip = _Clip("qwen")
    calls = {}
    monkeypatch.setattr(
        components_module,
        "load_clip",
        lambda name, clip_type, device: calls.update(clip=(name, clip_type, device)) or loaded_clip,
    )
    monkeypatch.setattr(components_module, "load_vae", lambda name: calls.update(vae=name) or "external-vae")
    source = BubbaPipe(model="model", clip=_Clip("old"), vae="old-vae", metadata=BubbaMetadata(model_name="Anima"))

    result = BubbaModelComponentsOverride.execute(
        source,
        clip_name="qwen_3_06b_base.safetensors",
        vae_name="qwen_image_vae.safetensors",
        clip_type="qwen_image",
        clip_skip=2,
        clip_device="cpu",
    )
    pipe, metadata, _model, clip, vae, _info = result.result

    assert calls == {
        "clip": ("qwen_3_06b_base.safetensors", "qwen_image", "cpu"),
        "vae": "qwen_image_vae.safetensors",
    }
    assert clip is not loaded_clip
    assert clip.name == "qwen:clone" and clip.layer == -2
    assert vae == "external-vae"
    assert pipe.clip is clip and pipe.vae == "external-vae"
    assert metadata.clip_skip == 2


def test_component_override_can_prepare_partial_pipe_before_compare_loader(monkeypatch):
    external_clip = _Clip("external")
    monkeypatch.setattr(components_module, "load_clip", lambda *_args: external_clip)
    monkeypatch.setattr(components_module, "load_vae", lambda _name: "external-vae")
    source = BubbaPipe(latent={"samples": torch.zeros((1, 4, 8, 8))}, metadata=BubbaMetadata(seed=77))

    prepared = BubbaModelComponentsOverride.execute(
        source,
        clip_name="qwen.safetensors",
        vae_name="qwen-vae.safetensors",
        clip_type="qwen_image",
    ).result[0]

    assert prepared.model is None
    assert prepared.clip is external_clip
    assert prepared.vae == "external-vae"
    assert prepared.latent is source.latent

    monkeypatch.setattr(loader_module, "load_checkpoint", lambda name: (f"model:{name}", f"bundled-clip:{name}", f"bundled-vae:{name}"))
    compared = BubbaModelCompareLoader.execute(
        "one",
        "two",
        "three",
        "four",
        replace_clip=False,
        replace_vae=False,
        pipe=prepared,
    ).result[:4]

    assert [item.model for item in compared] == ["model:one", "model:two", "model:three", "model:four"]
    assert all(item.clip is external_clip and item.vae == "external-vae" for item in compared)
    assert all(item.metadata.seed == 77 for item in compared)


def test_component_override_schema_matches_pipe_transform_contract():
    schema = BubbaModelComponentsOverride.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "pipe",
        "clip_name",
        "vae_name",
        "clip_type",
        "clip_skip",
        "clip_device",
    ]
    assert [item.id for item in schema.outputs] == ["pipe", "metadata", "model", "clip", "vae", "info"]


def test_compare_sheet_auto_layout_labels_and_updates_pipe():
    pipe_1 = BubbaPipe(image=_image(16, 10, 0.1), metadata=BubbaMetadata(model_name="Alpha", seed=7))
    pipe_2 = BubbaPipe(image=_image(12, 8, 0.8), metadata=BubbaMetadata(model_name="Beta", seed=7))

    result = BubbaModelCompareSheet.execute(pipe_1=pipe_1, pipe_2=pipe_2, gap=4, font_size=8)
    pipe, image, metadata, info = result.result

    assert tuple(image.shape) == (1, 10, 36, 3)
    assert pipe.image is image
    assert metadata.model_name == "Alpha vs Beta"
    assert metadata.seed == 7
    assert "Compared 2 models in 1x2" in info
    assert not torch.allclose(image[:, :, :16], pipe_1.image)


def test_compare_sheet_grid_uses_explicit_image_override():
    pipes = [BubbaPipe(image=_image(8, 8, index / 10), metadata=BubbaMetadata(model_name=f"M{index}")) for index in range(1, 5)]
    override = _image(10, 6, 0.9)

    result = BubbaModelCompareSheet.execute(
        pipe_1=pipes[0],
        pipe_2=pipes[1],
        pipe_3=pipes[2],
        pipe_4=pipes[3],
        image_1=override,
        layout="2x2 Grid",
        gap=2,
        font_size=8,
    )

    assert tuple(result.result[1].shape) == (1, 18, 22, 3)
    assert result.result[2].model_name == "M1 vs M2 vs M3 vs M4"


def test_compare_sheet_vertical_and_preserve_size():
    result = BubbaModelCompareSheet.execute(
        pipe_1=BubbaPipe(image=_image(6, 4), metadata=BubbaMetadata(model_name="A")),
        image_2=_image(10, 8),
        layout="Vertical",
        fit_mode="Preserve size",
        gap=3,
        background="White",
        font_size=8,
    )

    assert tuple(result.result[1].shape) == (1, 19, 10, 3)
    assert result.result[2].model_name == "A vs Model 2"


def test_compare_sheet_requires_at_least_one_image():
    with pytest.raises(ValueError, match="at least one"):
        BubbaModelCompareSheet.execute()


def test_compare_sheet_schema_is_save_ready_output_node():
    schema = BubbaModelCompareSheet.GET_SCHEMA()
    assert [item.id for item in schema.inputs[:8]] == [
        "pipe_1",
        "pipe_2",
        "pipe_3",
        "pipe_4",
        "image_1",
        "image_2",
        "image_3",
        "image_4",
    ]
    assert [item.id for item in schema.outputs] == ["pipe", "image", "metadata", "info"]
    assert schema.is_output_node is True
