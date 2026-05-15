import os
import re
import shutil
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _install_runtime_mocks():
    # Mock ComfyUI nodes module used by checkpoint/sampler nodes.
    mock_nodes = MagicMock()
    mock_nodes.CheckpointLoaderSimple = MagicMock()
    mock_nodes.common_ksampler = MagicMock()
    mock_nodes.InpaintModelConditioning = MagicMock()
    sys.modules["nodes"] = mock_nodes

    # Mock comfy.samplers for sampler INPUT_TYPES class constants.
    comfy_module = types.ModuleType("comfy")
    comfy_samplers = types.ModuleType("comfy.samplers")

    class _MockKSampler:
        SAMPLERS = ["euler", "dpmpp_2m"]
        SCHEDULERS = ["normal", "karras"]

    comfy_samplers.KSampler = _MockKSampler  # type: ignore[attr-defined]
    comfy_module.samplers = comfy_samplers  # type: ignore[attr-defined]

    sys.modules["comfy"] = comfy_module
    sys.modules["comfy.samplers"] = comfy_samplers

    # Mock comfy_api.latest.UI for save image node imports.
    comfy_api_module = types.ModuleType("comfy_api")
    comfy_api_latest = types.ModuleType("comfy_api.latest")

    ui = MagicMock()
    preview_result = MagicMock()
    preview_result.as_dict.return_value = {"images": []}
    ui.PreviewImage.return_value = preview_result

    save_result = MagicMock()
    save_result.as_dict.return_value = {"images": []}
    ui.ImageSaveHelper.get_save_images_ui.return_value = save_result

    comfy_api_latest.UI = ui  # type: ignore[attr-defined]
    comfy_api_module.latest = comfy_api_latest  # type: ignore[attr-defined]

    sys.modules["comfy_api"] = comfy_api_module
    sys.modules["comfy_api.latest"] = comfy_api_latest

    # Mock folder_paths used by combo loader and server routes.
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda kind: []  # type: ignore[attr-defined]
    folder_paths.get_folder_paths = lambda kind: []  # type: ignore[attr-defined]
    folder_paths.get_full_path = lambda kind, name: None  # type: ignore[attr-defined]
    sys.modules["folder_paths"] = folder_paths

    # Mock comfy_extras.nodes_upscale_model used by BubbaUpscaler.
    comfy_extras_module = types.ModuleType("comfy_extras")
    nodes_upscale_model = types.ModuleType("comfy_extras.nodes_upscale_model")
    nodes_upscale_model.UpscaleModelLoader = MagicMock()  # type: ignore[attr-defined]
    nodes_upscale_model.ImageUpscaleWithModel = MagicMock()  # type: ignore[attr-defined]
    comfy_extras_module.nodes_upscale_model = nodes_upscale_model  # type: ignore[attr-defined]
    sys.modules["comfy_extras"] = comfy_extras_module
    sys.modules["comfy_extras.nodes_upscale_model"] = nodes_upscale_model

    # Mock comfy.utils used by BubbaUpscaler for common_upscale.
    comfy_utils = types.ModuleType("comfy.utils")
    comfy_utils.common_upscale = MagicMock(side_effect=lambda t, w, h, m, c: t)  # type: ignore[attr-defined]
    comfy_module.utils = comfy_utils  # type: ignore[attr-defined]
    sys.modules["comfy.utils"] = comfy_utils


_install_runtime_mocks()

# Add the project root directory to Python path
# This allows the tests to import the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def pytest_sessionstart(session):
    """Ensure runtime mocks are in place at the start of the session."""
    _install_runtime_mocks()


@pytest.fixture
def tmp_path(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name).strip("_") or "test"
    temp_root = Path(__file__).resolve().parents[1] / ".test_tmp" / "tmp_path"
    temp_path = temp_root / safe_name
    shutil.rmtree(temp_path, ignore_errors=True)
    temp_path.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)
