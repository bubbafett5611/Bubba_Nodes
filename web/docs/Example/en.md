# Bubba Nodes

Bubba Nodes provides ComfyUI nodes for prompt building, prompt inspection, metadata management, overlays, and save/load workflows.

## Node Index

- Bubba Character Prompt Builder
- Bubba Metadata Prompt Builder
- Bubba Prompt Cleaner
- Bubba Prompt Inspector
- Bubba Checkpoint Loader
- Bubba KSampler
- Bubba Empty Latent (Preset Sizes)
- Bubba Filename Builder
- Bubba Metadata Bundle
- Bubba Metadata Debug
- Bubba Metadata Update
- Bubba Add Text Overlay
- Bubba Add Text Overlay (Metadata)
- Bubba Save Image
- Bubba Load Image (With Metadata)

## Bubba Character Prompt Builder

Builds positive and negative prompts from structured sections and emits conditioning.

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
| format_mode | COMBO | booru, prose, or hybrid. |
| cleanup | BOOLEAN | Normalize spacing/separators. |
| dedupe | BOOLEAN | Remove duplicate tags case-insensitively. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| positive_prompt | STRING | Final positive prompt text. |
| negative_prompt | STRING | Final negative prompt text. |
| sections | STRING | Section block text suitable for metadata persistence. |
| positive_conditioning | CONDITIONING | Encoded from positive_prompt. |
| negative_conditioning | CONDITIONING | Encoded from negative_prompt. |

## Bubba Metadata Prompt Builder

Builds prompts from sections and writes results back into metadata.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| metadata | BUBBA_METADATA | Metadata object to update. |
| clip | CLIP | CLIP used to encode prompt conditioning. |
| appearance, body, clothing, pose, expression, scene | STRING | Section text inputs. |
| style_tags | STRING | Style tags. |
| quality_tags | STRING | Quality tags. |
| negative_tags | STRING | Negative tags. |
| format_mode | COMBO | booru, prose, or hybrid. |
| cleanup | BOOLEAN | Normalize spacing/separators. |
| dedupe | BOOLEAN | Remove duplicate tags. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata | BUBBA_METADATA | Updated metadata with positive_prompt, negative_prompt, prompt_sections. |
| positive_prompt | STRING | Final positive prompt text. |
| negative_prompt | STRING | Final negative prompt text. |
| sections | STRING | Section block text saved into metadata.prompt_sections. |
| positive_conditioning | CONDITIONING | Encoded from positive_prompt. |
| negative_conditioning | CONDITIONING | Encoded from negative_prompt. |

## Bubba Prompt Cleaner

Normalizes and deduplicates existing prompts.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| positive_prompt | STRING | Positive prompt to clean. |
| negative_prompt | STRING | Negative prompt to clean. |
| cleanup | BOOLEAN | Normalize separators and whitespace. |
| dedupe | BOOLEAN | Remove duplicate tags. |
| clip | CLIP | Optional. When present, emits conditioning. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| clean_positive | STRING | Cleaned positive prompt. |
| clean_negative | STRING | Cleaned negative prompt. |
| positive_conditioning | CONDITIONING | Empty when clip is not connected. |
| negative_conditioning | CONDITIONING | Empty when clip is not connected. |

## Bubba Prompt Inspector

Inspects prompts to surface quality issues before sampling.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| positive_prompt | STRING | Positive prompt to inspect. |
| negative_prompt | STRING | Negative prompt to inspect. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| token_count | INT | Total token count from cleaned positive + negative tags. |
| duplicate_tags | STRING | Duplicate tags grouped by positive/negative, or none. |
| conflict_warnings | STRING | Shared tags across positive/negative and simple pair conflicts. |
| formatted_preview | STRING | Cleaned + deduped positive/negative preview text. |

### Conflict Checks

- Appears in both positive and negative prompts.
- Pair conflicts in the same prompt:
  - solo and multiple people
  - male and female
  - day and night
  - indoors and outdoors
  - safe and nsfw

## Bubba Checkpoint Loader

Loads a checkpoint and also returns checkpoint name text.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| ckpt_name | COMBO | Checkpoint filename to load. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Loaded model. |
| clip | CLIP | Loaded CLIP. |
| vae | VAE | Loaded VAE. |
| checkpoint_name | STRING | Selected checkpoint filename. |

## Bubba KSampler

Runs denoising and emits an INFO summary string plus updated metadata.

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
| metadata | BUBBA_METADATA | Optional metadata to update with sampler info and seed. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Sampled latent result. |
| info | STRING | Time/seed/settings summary text. |
| metadata | BUBBA_METADATA | Updated metadata object. |

## Bubba Empty Latent (Preset Sizes)

Builds empty latent tensors from preset dimensions.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Empty latent tensor batch. |
| width | INT | Final width. |
| height | INT | Final height. |

## Bubba Filename Builder

Builds a sanitized relative filepath from character and scene names.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| filepath | STRING | Relative path like Character/Scene. |

## Bubba Metadata Bundle

Collects metadata fields into one typed object.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| model_name | STRING | Model/checkpoint name. |
| sampler_info | STRING | Sampler/settings summary string. |
| positive_prompt | STRING | Positive prompt text. |
| negative_prompt | STRING | Negative prompt text. |
| seed | INT | Generation seed. |
| filepath | STRING | Relative output filepath prefix. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata | BUBBA_METADATA | Typed metadata object. |

## Bubba Metadata Debug

Converts metadata to pretty JSON text.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata_text | STRING | Pretty JSON metadata output. |

## Bubba Metadata Update

Updates selected metadata fields and optionally emits conditioning.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| metadata | BUBBA_METADATA | Updated metadata object. |
| seed | INT | Final seed value after updates. |
| positive_conditioning | CONDITIONING | Encoded from metadata positive prompt when clip is connected. |
| negative_conditioning | CONDITIONING | Encoded from metadata negative prompt when clip is connected. |

## Bubba Add Text Overlay

Renders prompt/model/info text bars directly from explicit text inputs.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Image batch with overlay/underlay text bars. |

## Bubba Add Text Overlay (Metadata)

Renders overlay text by reading fields from metadata.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Image batch with metadata-driven overlay text. |

## Bubba Save Image

Saves images via ComfyUI UI helper and embeds Bubba metadata into PNG text when metadata is connected.

### Notes

- Uses metadata.filepath when filepath input is blank.
- Supports preview_only mode.
- Embeds metadata JSON under PNG text key bubba_metadata.

## Bubba Load Image (With Metadata)

Loads image and mask while decoding Bubba metadata from PNG text key bubba_metadata.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| image | IMAGE | Loaded image tensor. |
| mask | MASK | Alpha-derived mask. |
| metadata | BUBBA_METADATA | Parsed metadata object. |
| metadata_text | STRING | Pretty JSON metadata string. |

## Suggested Flow

1. Build prompts with Bubba Character Prompt Builder or Bubba Metadata Prompt Builder.
2. Optionally clean and inspect prompt quality with Bubba Prompt Cleaner and Bubba Prompt Inspector.
3. Build/update metadata and sample with Bubba KSampler.
4. Decode latent to image.
5. Overlay metadata text if desired.
6. Save image with embedded metadata.
7. Reload image metadata downstream when needed.
