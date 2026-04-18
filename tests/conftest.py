import os
import sys
import types
from unittest.mock import MagicMock


def _install_runtime_mocks():
    # Mock ComfyUI nodes module used by checkpoint/sampler nodes.
    mock_nodes = MagicMock()
    mock_nodes.CheckpointLoaderSimple = MagicMock()
    mock_nodes.common_ksampler = MagicMock()
    sys.modules["nodes"] = mock_nodes

    # Mock comfy.samplers for sampler INPUT_TYPES class constants.
    comfy_module = types.ModuleType("comfy")
    comfy_samplers = types.ModuleType("comfy.samplers")

    class _MockKSampler:
        SAMPLERS = ["euler", "dpmpp_2m"]
        SCHEDULERS = ["normal", "karras"]

    comfy_samplers.KSampler = _MockKSampler
    comfy_module.samplers = comfy_samplers

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

    comfy_api_latest.UI = ui
    comfy_api_module.latest = comfy_api_latest

    sys.modules["comfy_api"] = comfy_api_module
    sys.modules["comfy_api.latest"] = comfy_api_latest


_install_runtime_mocks()

# Add the project root directory to Python path
# This allows the tests to import the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def pytest_sessionstart(session):
    """Ensure runtime mocks are in place at the start of the session."""
    _install_runtime_mocks()
