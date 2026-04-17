import os
import sys
from unittest.mock import MagicMock

# Mock ComfyUI's nodes module IMMEDIATELY before any local imports
# This must happen before adding to sys.path or importing anything
mock_nodes = MagicMock()
mock_nodes.CheckpointLoaderSimple = MagicMock()
mock_nodes.common_ksampler = MagicMock()
sys.modules['nodes'] = mock_nodes

# Add the project root directory to Python path
# This allows the tests to import the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def pytest_sessionstart(session):
    """Ensure mocks are in place at the start of the session."""
    # Re-apply mocks in case they got cleared
    if 'nodes' not in sys.modules or not isinstance(sys.modules['nodes'], MagicMock):
        mock_nodes = MagicMock()
        mock_nodes.CheckpointLoaderSimple = MagicMock()
        mock_nodes.common_ksampler = MagicMock()
        sys.modules['nodes'] = mock_nodes
