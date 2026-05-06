# TODO(new-feature): Add optional auto-discovery registration so new node modules can be added without manual map edits.
# TODO(new-node): Keep this mapping in sync when introducing new nodes (metadata merge, preset manager, manifest saver).

from .filename import BubbaFilename
from .empty_latent_by_size import BubbaEmptyLatentBySize
from .load_image_with_metadata import BubbaLoadImageWithMetadata
from .checkpoint_loader import BubbaCheckpointLoader
from .combo_loader import BubbaComboLoader
from .lora_loader import BubbaLoraLoader
from .upscaler import BubbaUpscaler
from .image_compare import BubbaImageCompare
from .k_sampler import BubbaKSampler
from .save_image import BubbaSaveImage
from .overlay_from_metadata import BubbaOverlayFromMetadata
from .watermark import BubbaWatermark
from .metadata_debug import BubbaMetadataDebug
from .character_prompt_builder import (
    BubbaCharacterPromptBuilder,
)
from .simple_prompt_builder import BubbaSimplePromptBuilder
from .prompt_cleaner import BubbaPromptCleaner
from .prompt_inspector import BubbaPromptInspector

NODE_CLASS_MAPPINGS = {
    # Workflow
    "BubbaFilename": BubbaFilename,
    # Generation
    "BubbaEmptyLatentBySize": BubbaEmptyLatentBySize,
    "BubbaCheckpointLoader": BubbaCheckpointLoader,
    "BubbaComboLoader": BubbaComboLoader,
    "BubbaLoraLoader": BubbaLoraLoader,
    "BubbaKSampler": BubbaKSampler,
    # Prompt
    "BubbaCharacterPromptBuilder": BubbaCharacterPromptBuilder,
    "BubbaSimplePromptBuilder": BubbaSimplePromptBuilder,
    "BubbaPromptCleaner": BubbaPromptCleaner,
    "BubbaPromptInspector": BubbaPromptInspector,
    # Metadata
    "BubbaMetadataDebug": BubbaMetadataDebug,
    # Image IO + overlays
    "BubbaUpscaler": BubbaUpscaler,
    "BubbaImageCompare": BubbaImageCompare,
    "BubbaLoadImageWithMetadata": BubbaLoadImageWithMetadata,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaOverlayFromMetadata": BubbaOverlayFromMetadata,
    "BubbaWatermark": BubbaWatermark,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Workflow
    "BubbaFilename": "Bubba Filename Builder",
    # Generation
    "BubbaEmptyLatentBySize": "Bubba Empty Latent (Preset Sizes)",
    "BubbaCheckpointLoader": "Bubba Checkpoint Loader",
    "BubbaComboLoader": "Bubba Combo Loader",
    "BubbaLoraLoader": "Bubba LoRA Loader",
    "BubbaKSampler": "Bubba KSampler",
    # Prompt
    "BubbaCharacterPromptBuilder": "Bubba Character Prompt Builder",
    "BubbaSimplePromptBuilder": "Bubba Simple Prompt Builder",
    "BubbaPromptCleaner": "Bubba Prompt Cleaner",
    "BubbaPromptInspector": "Bubba Prompt Inspector",
    # Metadata
    "BubbaMetadataDebug": "Bubba Metadata Debug",
    # Image IO + overlays
    "BubbaUpscaler": "Bubba Upscaler (ESRGAN)",
    "BubbaImageCompare": "Bubba Image Compare",
    "BubbaLoadImageWithMetadata": "Bubba Load Image (With Metadata)",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaOverlayFromMetadata": "Bubba Add Text Overlay (Metadata)",
    "BubbaWatermark": "Bubba Watermark Overlay",
}
