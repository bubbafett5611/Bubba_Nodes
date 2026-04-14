# Bubba Nodes

These nodes simplify the post-generation part of a ComfyUI workflow: building a clean filename, adding an overlay bar, and saving either to the output folder or preview temp storage.

## Bubba KSampler

Runs image generation like a standard KSampler and also returns a formatted info string for overlays or downstream text handling.

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

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `LATENT` | LATENT | Generated latent result. |
| `INFO` | STRING | Multiline generation summary containing time, seed, steps, cfg, sampler, scheduler, and denoise. |

## Bubba Filename Builder

Builds a relative save path in the format `character_name/scene_name`.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `character_name` | STRING | Folder portion of the path. Spaces are converted to underscores and invalid path characters are removed. |
| `scene_name` | STRING | Filename prefix portion of the path. Spaces are converted to underscores and invalid path characters are removed. |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `filepath` | STRING | Combined relative path such as `Random/Batch2`. |

## Bubba Add Text Overlay

Adds an iTools-style text bar to the image. The bar can be drawn over the bottom of the image or appended underneath it.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | IMAGE | Source image batch. |
| `model_text` | STRING | Optional model label text. |
| `info_text` | STRING | Optional generation info text. |
| `positive_text` | STRING | Optional positive prompt text. Supports multiline input. |
| `negative_text` | STRING | Optional negative prompt text. Supports multiline input. |
| `show_model` | BOOLEAN | When enabled, includes the model section. |
| `show_info` | BOOLEAN | When enabled, includes the image info section. |
| `show_positive` | BOOLEAN | When enabled, includes the positive prompt section. |
| `show_negative` | BOOLEAN | When enabled, includes the negative prompt section. |
| `background_color` | STRING | Bar color in `#RRGGBB` or `#RRGGBBAA` format. Default is `#000000AA`. |
| `font_size` | INT | Text size for the bar. |
| `overlay_mode` | BOOLEAN | `True` draws the bar over the image. `False` adds the bar underneath the image. |

### Behavior

- Each enabled section is rendered on its own line.
- Empty sections are skipped.
- If every enabled section is empty, the node returns the original image unchanged.

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | Image batch with overlay text applied. |

## Bubba Save Image

Saves an image batch using ComfyUI's built-in save helpers.

### Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `images` | IMAGE | Image batch to save. |
| `filepath` | STRING | Relative output path prefix such as `Character/Scene`. |
| `preview_only` | BOOLEAN | When `True`, images are sent through ComfyUI preview/temp storage instead of normal output saving. |

### Behavior

- `preview_only = False`: saves through ComfyUI's normal image save UI helper.
- `preview_only = True`: uses ComfyUI preview behavior and writes to temp storage.

### Outputs

This is an output node. It does not return a normal graph value, but it publishes saved image entries to the ComfyUI UI.

## Suggested Flow

1. Use `Bubba Filename Builder` to create a save path.
2. Use `Bubba KSampler` to generate the latent and capture a formatted `INFO` string.
3. Decode your latent to image as usual.
4. Use `Bubba Add Text Overlay` to add model, prompt, or `INFO` metadata to the image.
5. Use `Bubba Save Image` to either preview or write the final image batch.
