from .filename import BubbaFilename
from .sampler import BubbaKSampler
from .save_image import BubbaSaveImage
from .overlay import BubbaOverlay
from .prompt import (
    BubbaCharacterPromptBuilder,
    BubbaPromptCleaner,
    BubbaPromptPreset,
    BubbaPromptPresetSave,
)

NODE_CLASS_MAPPINGS = {
    "BubbaFilename": BubbaFilename,
    "BubbaKSampler": BubbaKSampler,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaOverlay": BubbaOverlay,
    "BubbaCharacterPromptBuilder": BubbaCharacterPromptBuilder,
    "BubbaPromptCleaner": BubbaPromptCleaner,
    "BubbaPromptPreset": BubbaPromptPreset,
    "BubbaPromptPresetSave": BubbaPromptPresetSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BubbaFilename": "Bubba Filename Builder",
    "BubbaKSampler": "Bubba KSampler",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaOverlay": "Bubba Add Text Overlay",
    "BubbaCharacterPromptBuilder": "Bubba Character Prompt Builder",
    "BubbaPromptCleaner": "Bubba Prompt Cleaner",
    "BubbaPromptPreset": "Bubba Prompt Preset",
    "BubbaPromptPresetSave": "Bubba Prompt Preset Save",
}
