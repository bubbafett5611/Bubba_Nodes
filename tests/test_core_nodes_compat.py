import sys
import types
from unittest.mock import MagicMock

import pytest

from src.bubba_nodes.compat import core_nodes


def test_checkpoint_load_prunes_stale_cache_entry_and_retries(monkeypatch):
    stale = types.SimpleNamespace(model=None)
    live = types.SimpleNamespace(model=object())
    model_management = types.ModuleType("comfy.model_management")
    model_management.current_loaded_models = [stale, live]
    monkeypatch.setitem(sys.modules, "comfy.model_management", model_management)
    monkeypatch.setattr(sys.modules["comfy"], "model_management", model_management, raising=False)

    loader = MagicMock()
    loader.load_checkpoint.side_effect = [
        AttributeError("'NoneType' object has no attribute 'is_dynamic'"),
        ("MODEL", "CLIP", "VAE"),
    ]
    nodes = types.SimpleNamespace(CheckpointLoaderSimple=MagicMock(return_value=loader))
    monkeypatch.setattr(core_nodes, "_nodes", lambda: nodes)

    assert core_nodes.load_checkpoint("example.safetensors") == ("MODEL", "CLIP", "VAE")
    assert model_management.current_loaded_models == [live]
    assert loader.load_checkpoint.call_count == 2


def test_checkpoint_load_does_not_mask_unrelated_attribute_error(monkeypatch):
    loader = MagicMock()
    loader.load_checkpoint.side_effect = AttributeError("unrelated")
    nodes = types.SimpleNamespace(CheckpointLoaderSimple=MagicMock(return_value=loader))
    monkeypatch.setattr(core_nodes, "_nodes", lambda: nodes)

    with pytest.raises(AttributeError, match="unrelated"):
        core_nodes.load_checkpoint("example.safetensors")

    loader.load_checkpoint.assert_called_once_with("example.safetensors")
