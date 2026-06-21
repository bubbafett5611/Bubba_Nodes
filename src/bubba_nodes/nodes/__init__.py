from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger("bubba_nodes")


@dataclass(frozen=True)
class NodeSpec:
    module_name: str
    class_name: str
    display_name: str


_NODE_SPECS = (
    # Workflow
    NodeSpec("pipe_in", "BubbaPipeIn", "Bubba Pipe In"),
    NodeSpec("pipe_out", "BubbaPipeOut", "Bubba Pipe Out"),
    NodeSpec("filename", "BubbaFilename", "Bubba Filename Builder"),
    # Generation
    NodeSpec("empty_latent_by_size", "BubbaEmptyLatentBySize", "Bubba Empty Latent (Preset Sizes)"),
    NodeSpec("checkpoint_loader", "BubbaCheckpointLoader", "Bubba Checkpoint Loader"),
    NodeSpec("combo_loader", "BubbaComboLoader", "Bubba Combo Loader"),
    NodeSpec("checkpoint_merge", "BubbaCheckpointMerge", "Bubba Checkpoint Merge"),
    NodeSpec("checkpoint_merge", "BubbaTripleCheckpointMerge", "Bubba Triple Checkpoint Merge"),
    NodeSpec("checkpoint_save", "BubbaSaveCheckpoint", "Bubba Save Checkpoint"),
    NodeSpec("checkpoint_save", "BubbaMergeNamingHelper", "Bubba Merge Naming Helper"),
    NodeSpec("checkpoint_merge", "BubbaCheckpointFingerprint", "Bubba Checkpoint Fingerprint"),
    NodeSpec("merge_preview_prompt_runner", "BubbaMergePreviewPromptRunner", "Bubba Merge Preview Prompt Runner"),
    NodeSpec("lora_loader", "BubbaLoraLoader", "Bubba LoRA Loader"),
    NodeSpec("lora_stack", "BubbaLoraStack", "Bubba LoRA Stack"),
    NodeSpec("k_sampler", "BubbaKSampler", "Bubba KSampler"),
    NodeSpec("detailer", "BubbaDetailer", "Bubba Detailer"),
    # Prompt
    NodeSpec("character_prompt_builder", "BubbaCharacterPromptBuilder", "Bubba Character Prompt Builder"),
    NodeSpec("simple_prompt_builder", "BubbaSimplePromptBuilder", "Bubba Simple Prompt Builder"),
    NodeSpec("prompt_randomizer", "BubbaPromptRandomizer", "Bubba Prompt Randomizer"),
    NodeSpec("prompt_cleaner", "BubbaPromptCleaner", "Bubba Prompt Cleaner"),
    NodeSpec("prompt_inspector", "BubbaPromptInspector", "Bubba Prompt Inspector"),
    # Metadata
    NodeSpec("metadata_debug", "BubbaMetadataDebug", "Bubba Metadata Debug"),
    # Utilities
    NodeSpec("view_text", "BubbaViewText", "Bubba View Text"),
    # Image IO + overlays
    NodeSpec("upscaler", "BubbaUpscaler", "Bubba Upscaler (ESRGAN)"),
    NodeSpec("image_compare", "BubbaImageCompare", "Bubba Image Compare"),
    NodeSpec("load_image_with_metadata", "BubbaLoadImageWithMetadata", "Bubba Load Image (With Metadata)"),
    NodeSpec("save_image", "BubbaSaveImage", "Bubba Save Image"),
    NodeSpec("overlay_from_metadata", "BubbaOverlayFromMetadata", "Bubba Add Text Overlay (Metadata)"),
    NodeSpec("watermark", "BubbaWatermark", "Bubba Watermark Overlay"),
)


NODE_CLASS_MAPPINGS: dict[str, type[Any]] = {}
NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}
UNAVAILABLE_NODE_MAPPINGS: dict[str, str] = {}


def _register_node(spec: NodeSpec) -> None:
    try:
        module = importlib.import_module(f".{spec.module_name}", __name__)
        node_class = getattr(module, spec.class_name)
    except Exception as error:
        UNAVAILABLE_NODE_MAPPINGS[spec.class_name] = str(error)
        logger.warning("Bubba node %s unavailable: %s", spec.class_name, error)
        return

    globals()[spec.class_name] = node_class
    NODE_CLASS_MAPPINGS[spec.class_name] = node_class
    NODE_DISPLAY_NAME_MAPPINGS[spec.class_name] = spec.display_name


for _spec in _NODE_SPECS:
    _register_node(_spec)


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "UNAVAILABLE_NODE_MAPPINGS",
    *(spec.class_name for spec in _NODE_SPECS if spec.class_name in globals()),
]
