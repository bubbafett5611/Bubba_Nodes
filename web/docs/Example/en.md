# Bubba Nodes

Bubba Nodes provides ComfyUI nodes for prompt authoring, prompt cleanup, preset management, image metadata overlays, and image saving workflow helpers.

## Node Index

- Bubba Character Prompt Builder
- Bubba Prompt Cleaner
- Bubba Prompt Preset Save
- Bubba Prompt Preset
- Bubba Checkpoint Loader
- Bubba KSampler
- Bubba Filename Builder
- Bubba Add Text Overlay
- Bubba Add Text Overlay (Metadata)
- Bubba Metadata Bundle
- Bubba Metadata Debug
- Bubba Metadata Update
- Bubba Save Image

## Bubba Character Prompt Builder

Builds positive and negative prompts from structured prompt sections.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `clip` | CLIP | CLIP model used to encode positive and negative conditioning outputs. |
| `character_name` | STRING | Character identity/name tags. |
| `appearance` | STRING | Visual traits (face/hair/features). |
| `body` | STRING | Physique/anatomy tags. |
| `clothing` | STRING | Outfit/accessory tags. |
| `pose` | STRING | Pose/camera orientation tags. |
| `expression` | STRING | Emotion/facial expression tags. |
| `scene` | STRING | Environment/composition tags. |
| `style_tags` | STRING | Rendering/style tags. |
| `quality_tags` | STRING | Quality/detail tags. |
| `negative_tags` | STRING | Negative prompt tags. |
| `format_mode` | COMBO | One of `booru`, `prose`, `hybrid`. |
| `cleanup` | BOOLEAN | Normalizes whitespace and separators. |
| `dedupe` | BOOLEAN | Removes duplicates while preserving first occurrence order. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `positive_prompt` | STRING | Formatted positive prompt. |
| `negative_prompt` | STRING | Cleaned/deduped negative prompt. |
| `sections` | STRING | Section block text (`key: value`) for preset save/load workflows. |
| `positive_conditioning` | CONDITIONING | Positive conditioning encoded from `positive_prompt`. |
| `negative_conditioning` | CONDITIONING | Negative conditioning encoded from `negative_prompt`. |

### Notes

- `booru`: comma-separated tag list.
- `prose`: phrase-style output with final `and` join.
- `hybrid`: first tags emphasized before `|`, remainder after it.

## Bubba Prompt Cleaner

Cleans existing positive and negative prompts.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `positive_prompt` | STRING | Positive prompt to normalize. |
| `negative_prompt` | STRING | Negative prompt to normalize. |
| `cleanup` | BOOLEAN | Normalizes spacing and separators. |
| `dedupe` | BOOLEAN | Removes duplicate tags (case-insensitive). |
| `clip` | CLIP | Optional. When connected, cleaned prompts are also encoded to conditioning. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `clean_positive` | STRING | Cleaned positive prompt. |
| `clean_negative` | STRING | Cleaned negative prompt. |
| `positive_conditioning` | CONDITIONING | Positive conditioning when `clip` is connected. |
| `negative_conditioning` | CONDITIONING | Negative conditioning when `clip` is connected. |

## Bubba Prompt Preset Save

Saves prompt sections into `prompt_presets.json`.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `preset_name` | STRING | Preset key name. Defaults to `CharacterPreset` when empty. |
| `sections` | STRING | Section text from Bubba Character Prompt Builder. |
| `overwrite` | BOOLEAN | Optional input. If disabled and preset exists, save is skipped. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `status` | STRING | Save/skip status message. |
| `saved_name` | STRING | Effective preset name used. |

## Bubba Prompt Preset

Loads a saved preset and optionally overrides individual sections.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `clip` | CLIP | CLIP model used to encode positive and negative conditioning outputs. |
| `preset_name` | COMBO | Preset loaded from `prompt_presets.json`. |
| `character_name` | STRING | Optional override for character section. |
| `appearance` | STRING | Optional override for appearance section. |
| `body` | STRING | Optional override for body section. |
| `clothing` | STRING | Optional override for clothing section. |
| `pose` | STRING | Optional override for pose section. |
| `expression` | STRING | Optional override for expression section. |
| `scene` | STRING | Optional override for scene section. |
| `style_tags` | STRING | Optional override for style section. |
| `quality_tags` | STRING | Optional override for quality section. |
| `negative_tags` | STRING | Optional override for negative section. |
| `format_mode` | COMBO | Override value (`booru`, `prose`, `hybrid`) when enabled. |
| `override_format_mode` | BOOLEAN | Uses the `format_mode` input instead of preset mode. |
| `cleanup` | BOOLEAN | Normalizes spacing and separators. |
| `dedupe` | BOOLEAN | Removes duplicate tags while preserving order. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `positive_prompt` | STRING | Formatted positive prompt from preset + overrides. |
| `negative_prompt` | STRING | Negative prompt from preset + overrides. |
| `sections` | STRING | Resolved section block after overrides. |
| `loaded_name` | STRING | Loaded preset name. |
| `positive_conditioning` | CONDITIONING | Positive conditioning encoded from `positive_prompt`. |
| `negative_conditioning` | CONDITIONING | Negative conditioning encoded from `negative_prompt`. |

## Bubba KSampler

Runs generation like standard KSampler and also returns a formatted info string.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | MODEL | Model used for denoising. |
| `seed` | INT | Random seed for noise generation. |
| `steps` | INT | Number of denoising steps. |
| `cfg` | FLOAT | Classifier-Free Guidance scale. |
| `sampler_name` | COMBO | Sampling algorithm. |
| `scheduler` | COMBO | Scheduler used during sampling. |
| `positive` | CONDITIONING | Positive conditioning input. |
| `negative` | CONDITIONING | Negative conditioning input. |
| `latent_image` | LATENT | Input latent to denoise. |
| `denoise` | FLOAT | Denoise strength. |
| `metadata` | BUBBA_METADATA | Optional metadata object to update with sampler info and seed. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `LATENT` | LATENT | Generated latent result. |
| `INFO` | STRING | Summary with time, seed, steps, cfg, sampler, scheduler, and denoise. |
| `metadata` | BUBBA_METADATA | Updated metadata object with sampler info and seed. |

## Bubba Checkpoint Loader

Loads a checkpoint and also outputs the selected checkpoint name for downstream metadata and overlay flows.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `ckpt_name` | COMBO | Checkpoint filename to load. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `model` | MODEL | Loaded model object. |
| `clip` | CLIP | Loaded CLIP object. |
| `vae` | VAE | Loaded VAE object. |
| `checkpoint_name` | STRING | Selected checkpoint filename as text. |

## Bubba Filename Builder

Builds a relative save path in the format `character_name/scene_name`.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `character_name` | STRING | Folder portion. Spaces become underscores; invalid path chars are removed. |
| `scene_name` | STRING | File prefix portion. Spaces become underscores; invalid path chars are removed. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `filepath` | STRING | Relative path like `Random/Batch2`. |

## Bubba Add Text Overlay

Adds top/bottom metadata bars to an image in overlay or underlay mode.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | IMAGE | Source image batch. |
| `model_text` | STRING | Optional model label text. |
| `info_text` | STRING | Optional generation info text. |
| `positive_text` | STRING | Optional positive prompt text (multiline). |
| `negative_text` | STRING | Optional negative prompt text (multiline). |
| `show_model` | BOOLEAN | Includes model section when enabled. |
| `model_position` | COMBO | `top` or `bottom` placement for model section. |
| `show_info` | BOOLEAN | Includes info section when enabled. |
| `info_position` | COMBO | `top` or `bottom` placement for info section. |
| `show_positive` | BOOLEAN | Includes positive section when enabled. |
| `positive_position` | COMBO | `top` or `bottom` placement for positive section. |
| `show_negative` | BOOLEAN | Includes negative section when enabled. |
| `negative_position` | COMBO | `top` or `bottom` placement for negative section. |
| `background_color` | STRING | `#RRGGBB` or `#RRGGBBAA` color. Invalid values fallback to semi-transparent black. |
| `font_size` | INT | Text size for rendered bars. |
| `overlay_mode` | BOOLEAN | `True` overlays bars on image. `False` appends bars to canvas. |

### Behavior

- Empty/disabled sections are skipped.
- If all sections are empty, the original image is returned unchanged.
- Text is wrapped to fit image width.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | Image batch with text bars applied. |

## Bubba Metadata Bundle

Collects generation metadata fields into one typed metadata object for easier downstream wiring.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_name` | STRING | Model/checkpoint name. |
| `sampler_info` | STRING | Sampler/settings summary text. |
| `positive_prompt` | STRING | Final positive prompt. |
| `negative_prompt` | STRING | Final negative prompt. |
| `seed` | INT | Generation seed. |
| `filepath` | STRING | Relative output filepath prefix. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `metadata` | BUBBA_METADATA | Typed metadata object containing all fields as one bundle. |

## Bubba Add Text Overlay (Metadata)

Adds top/bottom metadata bars by reading fields from a typed `metadata` object instead of separate text inputs.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | IMAGE | Source image batch. |
| `metadata` | BUBBA_METADATA | Metadata object from Bubba Metadata Bundle. Uses `model_name`, `sampler_info`, `positive_prompt`, and `negative_prompt`. |
| `show_model` | BOOLEAN | Includes model section when enabled. |
| `model_position` | COMBO | `top` or `bottom` placement for model section. |
| `show_info` | BOOLEAN | Includes info section when enabled. |
| `info_position` | COMBO | `top` or `bottom` placement for info section. |
| `show_positive` | BOOLEAN | Includes positive section when enabled. |
| `positive_position` | COMBO | `top` or `bottom` placement for positive section. |
| `show_negative` | BOOLEAN | Includes negative section when enabled. |
| `negative_position` | COMBO | `top` or `bottom` placement for negative section. |
| `background_color` | STRING | `#RRGGBB` or `#RRGGBBAA` color. |
| `font_size` | INT | Text size for rendered bars. |
| `overlay_mode` | BOOLEAN | `True` overlays bars on image. `False` appends bars to canvas. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | Image batch with text bars applied. |

## Bubba Metadata Debug

Converts `BUBBA_METADATA` into pretty JSON text so you can inspect metadata with Comfy text preview nodes.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `metadata` | BUBBA_METADATA | Typed metadata object to inspect. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `metadata_text` | STRING | Pretty JSON representation of metadata. |

## Bubba Metadata Update

Updates selected fields on an existing `BUBBA_METADATA` object.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `metadata` | BUBBA_METADATA | Base metadata object to modify. |
| `model_name` | STRING | Optional override when not empty. |
| `sampler_info` | STRING | Optional override when not empty. |
| `positive_prompt` | STRING | Optional override when not empty. |
| `negative_prompt` | STRING | Optional override when not empty. |
| `seed` | INT | Optional seed override when `set_seed` is enabled. |
| `set_seed` | BOOLEAN | Enables overwriting the seed field. |
| `filepath` | STRING | Optional filepath override when not empty. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `metadata` | BUBBA_METADATA | Updated metadata object. |

## Bubba Save Image

Saves an image batch using ComfyUI save helpers.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `images` | IMAGE | Image batch to save. |
| `filepath` | STRING | Relative output path prefix. Leave blank to use `metadata.filepath`. |
| `preview_only` | BOOLEAN | When `True`, output goes to preview/temp storage only. |
| `metadata` | BUBBA_METADATA | Optional metadata object. Used to resolve filepath when the direct filepath input is blank. |

### Outputs

This is an output node. It does not emit a graph value and instead publishes image save/preview UI entries.

## Suggested Flow

1. Build prompts with Bubba Character Prompt Builder or Bubba Prompt Preset.
2. Optionally run Bubba Prompt Cleaner.
3. Generate with Bubba KSampler and capture `INFO`.
4. Decode latent to image.
5. Add metadata bars with Bubba Add Text Overlay.
6. Build a path with Bubba Filename Builder.
7. Save with Bubba Save Image.
