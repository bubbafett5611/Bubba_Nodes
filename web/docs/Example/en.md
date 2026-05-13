# Bubba Nodes

Bubba Nodes provides ComfyUI nodes for prompt building, prompt inspection, model loading, metadata management, overlays, comparison, upscaling, and save/load workflows.

## Node Index

- Bubba Filename Builder
- Bubba Empty Latent (Preset Sizes)
- Bubba Load Image (With Metadata)
- Bubba Checkpoint Loader
- Bubba Combo Loader
- Bubba LoRA Loader
- Bubba KSampler
- Bubba Simple Prompt Builder
- Bubba Character Prompt Builder
- Bubba Prompt Cleaner
- Bubba Prompt Inspector
- Bubba Metadata Debug
- Bubba Upscaler (ESRGAN)
- Bubba Image Compare
- Bubba Add Text Overlay (Metadata)
- Bubba Watermark Overlay
- Bubba Save Image

## Bubba Filename Builder

Builds a sanitized relative path from character and scene names.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| filepath | STRING | Relative path like `Character/Scene`. |

## Bubba Empty Latent (Preset Sizes)

Builds empty latent tensors from preset dimensions.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| size | COMBO | Preset size selection. |
| swap_width_height | BOOLEAN | Swaps orientation for the selected preset. |
| batch_size | INT | Number of latent images to create. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Empty latent tensor batch. |
| width | INT | Final width. |
| height | INT | Final height. |

## Bubba Load Image (With Metadata)

Loads an image and mask while decoding Bubba metadata from PNG text key `bubba_metadata`.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Loaded image tensor. |
| mask | MASK | Alpha-derived mask. |
| metadata | BUBBA_METADATA | Parsed metadata object. |
| metadata_text | STRING | Pretty JSON metadata string. |

## Bubba Checkpoint Loader

Loads a checkpoint, returns the checkpoint name, and updates metadata with the display model name.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Loaded model. |
| clip | CLIP | Loaded CLIP. |
| vae | VAE | Loaded VAE. |
| checkpoint_name | STRING | Selected checkpoint filename. |
| metadata | BUBBA_METADATA | Updated metadata object. |

## Bubba Combo Loader

Loads a checkpoint plus optional external VAE and CLIP/text-encoder overrides in one node.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| ckpt_name | COMBO | Checkpoint filename to load. |
| vae_name | COMBO | VAE override, or `None` to use the checkpoint VAE. |
| clip_name | COMBO | CLIP/text encoder override, or `None` to use the checkpoint CLIP. |
| clip_type | COMBO | CLIP loader type used when `clip_name` is selected. |
| clip_skip | INT | Number of CLIP layers to skip. `0` disables CLIP skip. |
| metadata | BUBBA_METADATA | Optional metadata object to update. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Loaded model. |
| clip | CLIP | Loaded or overridden CLIP. |
| vae | VAE | Loaded or overridden VAE. |
| checkpoint_name | STRING | Selected checkpoint filename. |
| metadata | BUBBA_METADATA | Updated metadata with model name and CLIP skip. |

## Bubba LoRA Loader

Loads a LoRA, applies it to MODEL and CLIP, and appends the LoRA display name to metadata.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Model after LoRA application. |
| clip | CLIP | CLIP after LoRA application. |
| lora_name | STRING | LoRA display name without extension. |
| metadata | BUBBA_METADATA | Updated metadata with LoRA history. |

## Bubba KSampler

Runs denoising, emits an INFO summary string, updates metadata, and can optionally decode an image when a VAE is connected.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| model | MODEL | Model used for denoising. |
| seed | INT | Seed value. |
| steps | INT | Denoising steps. |
| cfg | FLOAT | CFG scale. |
| sampler_name | COMBO | Sampler algorithm. |
| scheduler | COMBO | Scheduler. |
| positive | CONDITIONING | Positive conditioning. |
| negative | CONDITIONING | Negative conditioning. |
| latent_image | LATENT | Input latent. |
| denoise | FLOAT | Denoise strength. |
| metadata | BUBBA_METADATA | Optional metadata to update. |
| vae | VAE | Optional VAE used to decode the latent image output. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Sampled latent result. |
| info | STRING | Time/seed/settings summary text. |
| metadata | BUBBA_METADATA | Updated metadata object. |
| image | IMAGE | Decoded image when VAE is connected. |

## Bubba Simple Prompt Builder

Builds positive and negative prompts from single multiline text inputs and emits conditioning.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| clip | CLIP | CLIP used to encode outputs. |
| positive | STRING | Positive prompt tags. |
| negative | STRING | Negative prompt tags. |
| cleanup | BOOLEAN | Normalize spacing and trim separators. |
| dedupe | BOOLEAN | Remove duplicate tags case-insensitively. |
| metadata | BUBBA_METADATA | Optional metadata object to update. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| positive_prompt | STRING | Final positive prompt text. |
| negative_prompt | STRING | Final negative prompt text. |
| positive_conditioning | CONDITIONING | Encoded from positive prompt. |
| negative_conditioning | CONDITIONING | Encoded from negative prompt. |
| metadata | BUBBA_METADATA | Updated metadata with prompts. |

## Bubba Character Prompt Builder

Builds positive and negative prompts from structured character sections and emits conditioning.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| clip | CLIP | CLIP used to encode positive and negative outputs. |
| appearance | STRING | Face, hair, age, and identifying visual traits. |
| body | STRING | Physique and anatomy descriptors. |
| clothing | STRING | Outfit, accessories, and materials. |
| pose | STRING | Body pose and camera orientation. |
| expression | STRING | Facial expression and emotion. |
| scene | STRING | Environment, lighting, and composition context. |
| style_tags | STRING | Style/rendering tags. |
| quality_tags | STRING | Quality/detail tags. |
| negative_tags | STRING | Negative prompt tags. |
| format_mode | COMBO | `booru`, `prose`, or `hybrid`. |
| cleanup | BOOLEAN | Normalize spacing and trim separators. |
| dedupe | BOOLEAN | Remove duplicate tags case-insensitively. |
| metadata | BUBBA_METADATA | Optional metadata object to update. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| positive_prompt | STRING | Final positive prompt text. |
| negative_prompt | STRING | Final negative prompt text. |
| positive_conditioning | CONDITIONING | Encoded from positive prompt. |
| negative_conditioning | CONDITIONING | Encoded from negative prompt. |
| metadata | BUBBA_METADATA | Updated metadata with prompts. |

## Bubba Prompt Cleaner

Normalizes and deduplicates existing prompts. When CLIP is connected, it also emits conditioning.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| clean_positive | STRING | Cleaned positive prompt. |
| clean_negative | STRING | Cleaned negative prompt. |
| positive_conditioning | CONDITIONING | Empty when CLIP is not connected. |
| negative_conditioning | CONDITIONING | Empty when CLIP is not connected. |

## Prompt Field UX

Bubba multiline prompt fields include fast autocomplete plus an inline prompt assistant.

- Tag chips show the parsed prompt tags under the field.
- The summary line shows exact tag count plus a lightweight estimated token count.
- Amber chips mark duplicate tags in the same field.
- Red chips mark tags that also appear in the opposite positive/negative field on the same node.
- Red hint chips also surface simple local conflicts such as day/night, indoors/outdoors, and safe/nsfw.
- The `Bubba: Prompt Tag Chips + Hints` setting can disable the prompt assistant without disabling autocomplete.

## Bubba Prompt Inspector

Inspects prompts to surface quality issues before sampling.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| token_count | INT | Total token count from cleaned positive and negative tags. |
| duplicate_tags | STRING | Duplicate tags grouped by positive/negative, or none. |
| conflict_warnings | STRING | Shared tags across positive/negative and simple pair conflicts. |
| formatted_preview | STRING | Cleaned and deduped positive/negative preview text. |

### Conflict Checks

- Appears in both positive and negative prompts.
- Pair conflicts in the same prompt:
  - solo and multiple people
  - male and female
  - day and night
  - indoors and outdoors
  - safe and nsfw

## Bubba Metadata Debug

Converts metadata to pretty JSON text and displays it directly on the node after execution.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata_text | STRING | Pretty JSON metadata output. |

## Bubba Upscaler (ESRGAN)

Upscales an image with an ESRGAN/spandrel model and optionally resizes the upscaled result.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| image | IMAGE | Image to upscale. |
| upscale_model_name | COMBO | Upscale model filename. |
| scale_by | FLOAT | Scale applied after the model upscale. `1.0` keeps the model output size. |
| resize_method | COMBO | Interpolation method for the post-upscale resize. |
| metadata | BUBBA_METADATA | Optional metadata to pass through unchanged. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Upscaled image. |
| metadata | BUBBA_METADATA | Passed-through metadata. |

## Bubba Image Compare

Displays two image batches in a frontend A/B comparison view.

### Outputs

This node is a UI output node. It does not emit downstream values.

## Bubba Add Text Overlay (Metadata)

Renders overlay text by reading fields from metadata.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| image | IMAGE | Source image batch. |
| metadata | BUBBA_METADATA | Metadata fields used for overlay text. |
| show_model/show_info/show_positive/show_negative | BOOLEAN | Toggles for each text section. |
| model_position/info_position/positive_position/negative_position | COMBO | Top or bottom placement for each section. |
| background_color | STRING | Hex background color, including optional alpha. |
| font_size | INT | Overlay text size. |
| overlay_mode | BOOLEAN | Draw over the image when enabled; add bars outside the image when disabled. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Image batch with metadata-driven overlay text. |

## Bubba Watermark Overlay

Adds a watermark image using anchor position, scale, opacity, offsets, and optional mask support.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Image batch with watermark applied. |

## Bubba Save Image

Saves images via ComfyUI UI helpers and embeds metadata into PNG text when metadata is connected.

### Notes

- Uses `metadata.filepath` when `filepath` input is blank.
- Falls back to `Character/Scene` when no filepath is provided.
- Supports `preview_only` mode.
- Embeds Bubba metadata JSON under PNG text key `bubba_metadata`.
- Embeds ComfyUI prompt/workflow metadata when `save_workflow_metadata` is enabled.
- Shows a frontend metadata warning on the node when connected Bubba metadata is empty/default, or when PNG metadata embedding fails.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata | BUBBA_METADATA | Final metadata with resolved filepath. |

## Suggested Flow

1. Load a model with Bubba Combo Loader or Bubba Checkpoint Loader.
2. Apply LoRAs with Bubba LoRA Loader when needed.
3. Build prompts with Bubba Simple Prompt Builder or Bubba Character Prompt Builder.
4. Optionally clean and inspect prompt quality.
5. Create a latent with Bubba Empty Latent (Preset Sizes).
6. Sample with Bubba KSampler.
7. Optionally upscale, compare, overlay, or watermark the result.
8. Save with embedded metadata.
9. Reload image metadata downstream when needed.
