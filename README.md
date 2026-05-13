# Bubba Nodes

Custom ComfyUI nodes for prompt authoring, checkpoint/LoRA loading, metadata-first image workflows, overlays, upscaling, and save/load helpers.

## What Is Included

This extension registers 17 nodes:

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

## Features

- Build clean relative file paths from character and scene names.
- Generate empty latents from preset dimensions with optional orientation swap.
- Load images and extract embedded Bubba metadata from PNG text.
- Load checkpoints while recording the selected checkpoint name in metadata.
- Load checkpoint, optional external VAE, optional external CLIP/text encoder, and optional CLIP skip in one node.
- Apply LoRAs while appending each LoRA name to metadata.
- Build positive and negative prompts from simple text inputs or structured character sections.
- Normalize and dedupe prompt tags while preserving first occurrence order.
- Inspect prompts for token count, duplicate tags, shared positive/negative tags, and simple conflicts.
- Run KSampler, measure sampling time, update metadata, and optionally decode an image when a VAE is connected.
- Upscale with ESRGAN/spandrel models and optionally resize the upscaled result.
- Compare two image batches in the frontend with an A/B splitter.
- Add text overlays from metadata fields.
- Add watermark overlays with anchor, scale, opacity, offsets, and optional mask support.
- Save images normally or as previews, with optional ComfyUI workflow metadata and Bubba PNG metadata.
- Use in-node autocomplete for Bubba multiline prompt fields, backed by local CSV tag data and embedding names.

## Installation

### Option 1: ComfyUI-Manager

1. Install [ComfyUI](https://docs.comfy.org/get_started).
2. Install [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager).
3. Search for Bubba Nodes in ComfyUI-Manager and install.
4. Restart ComfyUI.

### Option 2: Manual Install

1. Clone this repo into your ComfyUI custom nodes directory:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/bubbafett5611/bubba_nodes.git
```

2. Restart ComfyUI.

3. If dependencies are missing in your ComfyUI Python environment, install them using the same interpreter ComfyUI runs with:

```bash
python -m pip install -r requirements.txt
```

If you use a dedicated ComfyUI venv/conda env, run that command from inside the active ComfyUI environment.

## Quick Workflow Example

1. Use Bubba Combo Loader or Bubba Checkpoint Loader to load the model stack.
2. Apply one or more Bubba LoRA Loader nodes if needed.
3. Use Bubba Simple Prompt Builder or Bubba Character Prompt Builder to create prompts, conditioning, and metadata.
4. Optionally run Bubba Prompt Cleaner and Bubba Prompt Inspector before sampling.
5. Generate a latent with Bubba Empty Latent (Preset Sizes).
6. Sample with Bubba KSampler so sampler settings, seed, and timing are written to metadata.
7. Decode through the KSampler VAE input or your usual VAE Decode node.
8. Optionally use Bubba Upscaler, Bubba Add Text Overlay (Metadata), or Bubba Watermark Overlay.
9. Save with Bubba Save Image and reload later with Bubba Load Image (With Metadata).

## Metadata Notes

- Metadata is represented by the typed `BUBBA_METADATA` object.
- Metadata currently includes `model_name`, `clip_skip`, `sampler_time_seconds`, `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `seed`, `positive_prompt`, `negative_prompt`, `loras`, and `filepath`.
- Bubba Metadata Debug displays pretty JSON directly on the node and still outputs the same text for wiring.
- Bubba Save Image embeds metadata into PNG text under `bubba_metadata`.
- Bubba Save Image can also embed ComfyUI `prompt` and `workflow` metadata when `save_workflow_metadata` is enabled.
- The Save Image node shows a frontend metadata warning when connected Bubba metadata is empty/default, or when PNG metadata embedding fails for one or more saved files.
- Bubba Load Image (With Metadata) reads `bubba_metadata` from PNG text and reconstructs `BUBBA_METADATA`.

## Prompt Notes

- Supported `format_mode` values are `booru`, `prose`, and `hybrid`.
- `cleanup` normalizes whitespace and separators before prompt output.
- `dedupe` removes duplicate tags case-insensitively while preserving the first spelling/order.
- Prompt Inspector outputs:
  - `token_count`
  - `duplicate_tags`
  - `conflict_warnings`
  - `formatted_preview`
- Prompt conflict warnings currently include:
  - tags that appear in both positive and negative prompts
  - simple pair checks such as solo/multiple people, male/female, day/night, indoors/outdoors, and safe/nsfw
- Bubba multiline prompt fields show lightweight tag chips and hints while typing.
- The prompt helper shows exact tag count plus a lightweight estimated token count, such as `8 tags · ~42 tokens`.
- Duplicate tags are marked in amber.
- Tags shared between positive and negative fields on the same node are marked in red.
- Simple local conflicts such as day/night and indoors/outdoors are surfaced as red hint chips.

## Autocomplete Notes

- The frontend extension is loaded from [web/comfyui/autocomplete.js](web/comfyui/autocomplete.js).
- Autocomplete is active on Bubba multiline prompt inputs such as positive, negative, appearance, style tags, quality tags, and negative tags.
- Type part of a tag to open suggestions.
- Use arrow keys to select, then press Tab or Enter to insert.
- Add custom words from ComfyUI settings using local storage.
- Enable or disable local-tag suggestions with `Bubba: Include Local CSV Tags`.
- Tag data is read from source-specific CSV files in `web/comfyui/tags/` when available, currently `danbooru.csv` and `e621.csv`.
- If source-specific CSV files are unavailable, autocomplete falls back to the bundled legacy `web/comfyui/danbooru_e621_merged.csv`.
- Use `Bubba: Local CSV Source` to open the current local CSV.
- Use `Bubba: Local CSV Sync + Cache` and `Download Sources + Rebuild Cache` to download the newest configured source CSVs and rebuild browser cache from local files.
- Suggestions are ranked by canonical and alias prefix match, then post count.
- `Bubba: Prompt Tag Chips + Hints` toggles the inline prompt assistant independently from autocomplete.

## Preview Routes

Bubba Nodes registers optional local ComfyUI routes for checkpoint and LoRA previews:

- `/bubba/checkpoint_preview`
- `/bubba/checkpoint_civitai_link`
- `/bubba/lora_preview`
- `/bubba/lora_civitai_link`

Preview lookup checks for sidecar images next to the model file, using `.preview.jpg/.png/.webp` first, then `.jpg/.png/.webp`.

## Node Documentation

Detailed node input/output docs are in [web/docs/Example/en.md](web/docs/Example/en.md).

## Development

Install in editable mode with dev tools:

```bash
cd bubba_nodes
pip install -e .[dev]
pre-commit install
```

Useful commands:

```bash
ruff check .
mypy .
pytest
```

## Tests

Unit tests are located in [tests/test_bubba_nodes.py](tests/test_bubba_nodes.py).

Run tests with:

```bash
pytest
```

On some Windows sandboxed environments, pytest's default temp-folder permissions can block `tmp_path`. The test suite provides a local temp fixture under `.test_tmp/`, which is ignored by git.

## Project Layout

- Nodes: [src/bubba_nodes/nodes](src/bubba_nodes/nodes)
- Models: [src/bubba_nodes/models](src/bubba_nodes/models)
- Utilities: [src/bubba_nodes/utils](src/bubba_nodes/utils)
- Server routes: [src/bubba_nodes/server](src/bubba_nodes/server)
- Tests: [tests](tests)
- Frontend extension: [web/comfyui](web/comfyui)
- Web docs: [web/docs](web/docs)

## Publishing

Package metadata and Comfy registry fields live in [pyproject.toml](pyproject.toml).

If publishing to the Comfy Registry:

1. Verify publisher and metadata under `tool.comfy`.
2. Create a registry API key.
3. Add the token to repository secrets as `REGISTRY_ACCESS_TOKEN`.
4. Trigger your release workflow.

Registry docs: https://docs.comfy.org/registry/publishing
