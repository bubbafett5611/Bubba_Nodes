#!/usr/bin/env python

"""Tests for `bubba_nodes` package."""

import pytest
from src.bubba_nodes.nodes import BubbaExample

@pytest.fixture
def example_node():
    """Fixture to create an Example node instance."""
    return BubbaExample()

def test_example_node_initialization(example_node):
    """Test that the node can be instantiated."""
    assert isinstance(example_node, BubbaExample)

def test_return_types():
    """Test the node's metadata."""
    assert BubbaExample.RETURN_TYPES == ("IMAGE",)
    assert BubbaExample.FUNCTION == "test"
    assert BubbaExample.CATEGORY == "Example"
