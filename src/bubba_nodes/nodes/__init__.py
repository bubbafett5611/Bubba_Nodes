from __future__ import annotations

import importlib
from dataclasses import dataclass

from comfy_api.latest import ComfyExtension


@dataclass(frozen=True)
class NodeSpec:
    module_name: str
    class_name: str


_NODE_SPECS = (
    NodeSpec("pipe_in", "BubbaPipeIn"),
    NodeSpec("pipe_out", "BubbaPipeOut"),
    NodeSpec("seed_control", "BubbaSeedControl"),
    NodeSpec("sampler_controls", "BubbaSamplerControls"),
    NodeSpec("filename", "BubbaFilename"),
    NodeSpec("empty_latent_by_size", "BubbaEmptyLatentBySize"),
    NodeSpec("checkpoint_loader", "BubbaCheckpointLoader"),
    NodeSpec("combo_loader", "BubbaComboLoader"),
    NodeSpec("model_compare_loader", "BubbaModelCompareLoader"),
    NodeSpec("model_components_override", "BubbaModelComponentsOverride"),
    NodeSpec("checkpoint_merge", "BubbaCheckpointMerge"),
    NodeSpec("checkpoint_merge", "BubbaTripleCheckpointMerge"),
    NodeSpec("checkpoint_save", "BubbaSaveCheckpoint"),
    NodeSpec("checkpoint_save", "BubbaMergeNamingHelper"),
    NodeSpec("checkpoint_merge", "BubbaCheckpointFingerprint"),
    NodeSpec("merge_preview_prompt_runner", "BubbaMergePreviewPromptRunner"),
    NodeSpec("lora_loader", "BubbaLoraLoader"),
    NodeSpec("lora_stack", "BubbaLoraStack"),
    NodeSpec("conditioning_multiply", "BubbaConditioningMultiply"),
    NodeSpec("k_sampler", "BubbaKSampler"),
    NodeSpec("detailer", "BubbaDetailer"),
    NodeSpec("character_prompt_builder", "BubbaCharacterPromptBuilder"),
    NodeSpec("simple_prompt_builder", "BubbaSimplePromptBuilder"),
    NodeSpec("prompt_randomizer", "BubbaPromptRandomizer"),
    NodeSpec("prompt_cleaner", "BubbaPromptCleaner"),
    NodeSpec("prompt_inspector", "BubbaPromptInspector"),
    NodeSpec("metadata_debug", "BubbaMetadataDebug"),
    NodeSpec("view_text", "BubbaViewText"),
    NodeSpec("upscaler", "BubbaUpscaler"),
    NodeSpec("tiled_diffusion_upscaler", "BubbaTiledDiffusionUpscaler"),
    NodeSpec("image_compare", "BubbaImageCompare"),
    NodeSpec("model_compare_sheet", "BubbaModelCompareSheet"),
    NodeSpec("load_image_with_metadata", "BubbaLoadImageWithMetadata"),
    NodeSpec("save_image", "BubbaSaveImage"),
    NodeSpec("discord_webhook", "BubbaDiscordWebhook"),
    NodeSpec("overlay_from_metadata", "BubbaOverlayFromMetadata"),
    NodeSpec("watermark", "BubbaWatermark"),
)


V3_NODE_CLASSES = []
for _spec in _NODE_SPECS:
    _module = importlib.import_module(f".{_spec.module_name}", __name__)
    _node_class = getattr(_module, _spec.class_name)
    globals()[_spec.class_name] = _node_class
    V3_NODE_CLASSES.append(_node_class)


class BubbaNodesExtension(ComfyExtension):
    async def on_load(self) -> None:
        from ..server import register_all_routes

        register_all_routes()

    async def get_node_list(self):
        return V3_NODE_CLASSES


async def comfy_entrypoint():
    return BubbaNodesExtension()


__all__ = ["V3_NODE_CLASSES", *(spec.class_name for spec in _NODE_SPECS)]
