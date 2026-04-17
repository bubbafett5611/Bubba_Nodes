from .filename import BubbaFilename
from .empty_latent import BubbaEmptyLatentBySize
from .load_image import BubbaLoadImageWithMetadata
from .checkpoint import BubbaCheckpointLoader
from .sampler import BubbaKSampler
from .save_image import BubbaSaveImage
from .overlay import BubbaOverlay, BubbaOverlayFromMetadata
from .metadata import BubbaMetadataBundle, BubbaMetadataDebug, BubbaMetadataUpdate
from .prompt import (
    BubbaCharacterPromptBuilder,
    BubbaPromptCleaner,
)
from .prompt_metadata import BubbaMetadataPromptBuilder

NODE_CLASS_MAPPINGS = {
    "BubbaFilename": BubbaFilename,
    "BubbaEmptyLatentBySize": BubbaEmptyLatentBySize,
    "BubbaLoadImageWithMetadata": BubbaLoadImageWithMetadata,
    "BubbaCheckpointLoader": BubbaCheckpointLoader,
    "BubbaKSampler": BubbaKSampler,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaOverlay": BubbaOverlay,
    "BubbaOverlayFromMetadata": BubbaOverlayFromMetadata,
    "BubbaMetadataBundle": BubbaMetadataBundle,
    "BubbaMetadataDebug": BubbaMetadataDebug,
    "BubbaMetadataUpdate": BubbaMetadataUpdate,
    "BubbaCharacterPromptBuilder": BubbaCharacterPromptBuilder,
    "BubbaMetadataPromptBuilder": BubbaMetadataPromptBuilder,
    "BubbaPromptCleaner": BubbaPromptCleaner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BubbaFilename": "Bubba Filename Builder",
    "BubbaEmptyLatentBySize": "Bubba Empty Latent (Preset Sizes)",
    "BubbaLoadImageWithMetadata": "Bubba Load Image (With Metadata)",
    "BubbaCheckpointLoader": "Bubba Checkpoint Loader",
    "BubbaKSampler": "Bubba KSampler",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaOverlay": "Bubba Add Text Overlay",
    "BubbaOverlayFromMetadata": "Bubba Add Text Overlay (Metadata)",
    "BubbaMetadataBundle": "Bubba Metadata Bundle",
    "BubbaMetadataDebug": "Bubba Metadata Debug",
    "BubbaMetadataUpdate": "Bubba Metadata Update",
    "BubbaCharacterPromptBuilder": "Bubba Character Prompt Builder",
    "BubbaMetadataPromptBuilder": "Bubba Metadata Prompt Builder",
    "BubbaPromptCleaner": "Bubba Prompt Cleaner",
}
