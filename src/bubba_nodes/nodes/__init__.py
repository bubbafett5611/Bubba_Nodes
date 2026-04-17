from .filename import BubbaFilename
from .checkpoint import BubbaCheckpointLoader
from .sampler import BubbaKSampler
from .save_image import BubbaSaveImage
from .overlay import BubbaOverlay, BubbaOverlayFromMetadata
from .metadata import BubbaMetadataBundle, BubbaMetadataDebug, BubbaMetadataUpdate
from .prompt import (
    BubbaCharacterPromptBuilder,
    BubbaPromptCleaner,
    BubbaPromptPreset,
    BubbaPromptPresetSave,
)

NODE_CLASS_MAPPINGS = {
    "BubbaFilename": BubbaFilename,
    "BubbaCheckpointLoader": BubbaCheckpointLoader,
    "BubbaKSampler": BubbaKSampler,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaOverlay": BubbaOverlay,
    "BubbaOverlayFromMetadata": BubbaOverlayFromMetadata,
    "BubbaMetadataBundle": BubbaMetadataBundle,
    "BubbaMetadataDebug": BubbaMetadataDebug,
    "BubbaMetadataUpdate": BubbaMetadataUpdate,
    "BubbaCharacterPromptBuilder": BubbaCharacterPromptBuilder,
    "BubbaPromptCleaner": BubbaPromptCleaner,
    "BubbaPromptPreset": BubbaPromptPreset,
    "BubbaPromptPresetSave": BubbaPromptPresetSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BubbaFilename": "Bubba Filename Builder",
    "BubbaCheckpointLoader": "Bubba Checkpoint Loader",
    "BubbaKSampler": "Bubba KSampler",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaOverlay": "Bubba Add Text Overlay",
    "BubbaOverlayFromMetadata": "Bubba Add Text Overlay (Metadata)",
    "BubbaMetadataBundle": "Bubba Metadata Bundle",
    "BubbaMetadataDebug": "Bubba Metadata Debug",
    "BubbaMetadataUpdate": "Bubba Metadata Update",
    "BubbaCharacterPromptBuilder": "Bubba Character Prompt Builder",
    "BubbaPromptCleaner": "Bubba Prompt Cleaner",
    "BubbaPromptPreset": "Bubba Prompt Preset",
    "BubbaPromptPresetSave": "Bubba Prompt Preset Save",
}
