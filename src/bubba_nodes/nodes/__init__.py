# TODO(new-feature): Add optional auto-discovery registration so new node modules can be added without manual map edits.
# TODO(new-node): Keep this mapping in sync when introducing new nodes (metadata merge, preset manager, manifest saver).

from .filename import BubbaFilename
from .empty_latent import BubbaEmptyLatentBySize
from .load_image import BubbaLoadImageWithMetadata
from .checkpoint import BubbaCheckpointLoader
from .combo_loader import BubbaComboLoader
from .sampler import BubbaKSampler
from .save_image import BubbaSaveImage
from .overlay import BubbaOverlay
from .overlay_from_metadata import BubbaOverlayFromMetadata
from .watermark import BubbaWatermark
from .metadata import BubbaMetadataUpdate
from .metadata_bundle import BubbaMetadataBundle
from .metadata_debug import BubbaMetadataDebug
from .prompt import (
    BubbaCharacterPromptBuilder,
)
from .prompt_cleaner import BubbaPromptCleaner
from .prompt_inspector import BubbaPromptInspector
from .prompt_metadata import BubbaMetadataPromptBuilder

NODE_CLASS_MAPPINGS = {
    # Workflow
    "BubbaFilename": BubbaFilename,
    # Generation
    "BubbaEmptyLatentBySize": BubbaEmptyLatentBySize,
    "BubbaCheckpointLoader": BubbaCheckpointLoader,
    "BubbaComboLoader": BubbaComboLoader,
    "BubbaKSampler": BubbaKSampler,
    # Prompt
    "BubbaCharacterPromptBuilder": BubbaCharacterPromptBuilder,
    "BubbaMetadataPromptBuilder": BubbaMetadataPromptBuilder,
    "BubbaPromptCleaner": BubbaPromptCleaner,
    "BubbaPromptInspector": BubbaPromptInspector,
    # Metadata
    "BubbaMetadataBundle": BubbaMetadataBundle,
    "BubbaMetadataDebug": BubbaMetadataDebug,
    "BubbaMetadataUpdate": BubbaMetadataUpdate,
    # Image IO + overlays
    "BubbaLoadImageWithMetadata": BubbaLoadImageWithMetadata,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaOverlay": BubbaOverlay,
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
    "BubbaKSampler": "Bubba KSampler",
    # Prompt
    "BubbaCharacterPromptBuilder": "Bubba Character Prompt Builder",
    "BubbaMetadataPromptBuilder": "Bubba Metadata Prompt Builder",
    "BubbaPromptCleaner": "Bubba Prompt Cleaner",
    "BubbaPromptInspector": "Bubba Prompt Inspector",
    # Metadata
    "BubbaMetadataBundle": "Bubba Metadata Bundle",
    "BubbaMetadataDebug": "Bubba Metadata Debug",
    "BubbaMetadataUpdate": "Bubba Metadata Update",
    # Image IO + overlays
    "BubbaLoadImageWithMetadata": "Bubba Load Image (With Metadata)",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaOverlay": "Bubba Add Text Overlay",
    "BubbaOverlayFromMetadata": "Bubba Add Text Overlay (Metadata)",
    "BubbaWatermark": "Bubba Watermark Overlay",
}
