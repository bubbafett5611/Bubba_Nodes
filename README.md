# Bubba Nodes

Custom ComfyUI nodes for prompt authoring, checkpoint/LoRA loading, pipe-based generation workflows, metadata-aware overlays, upscaling, and save/load helpers.

## What Is Included

This extension registers 29 nodes:

- Bubba Pipe In
- Bubba Pipe Out
- Bubba Filename Builder
- Bubba Empty Latent (Preset Sizes)
- Bubba Load Image (With Metadata)
- Bubba Checkpoint Loader
- Bubba Combo Loader
- Bubba Checkpoint Merge
- Bubba Triple Checkpoint Merge
- Bubba Save Checkpoint
- Bubba Merge Naming Helper
- Bubba Checkpoint Fingerprint
- Bubba Merge Preview Prompt Runner
- Bubba LoRA Loader
- Bubba LoRA Stack
- Bubba KSampler
- Bubba Detailer
- Bubba Simple Prompt Builder
- Bubba Character Prompt Builder
- Bubba Prompt Randomizer
- Bubba Prompt Cleaner
- Bubba Prompt Inspector
- Bubba Metadata Debug
- Bubba View Text
- Bubba Upscaler (ESRGAN)
- Bubba Image Compare
- Bubba Add Text Overlay (Metadata)
- Bubba Watermark Overlay
- Bubba Save Image

## Features

- Build clean relative file paths from character and scene names.
- Build and unpack `BUBBA_PIPE` objects for advanced graph wiring.
- Generate empty latents from preset dimensions with optional orientation swap, and store them in the pipe.
- Carry generation state through a `BUBBA_PIPE` object for cleaner graphs.
- Load images and extract embedded Bubba metadata from PNG text into a pipe.
- Load checkpoints while recording the selected checkpoint name in pipe metadata.
- Load checkpoint, optional external VAE, optional external CLIP/text encoder, and optional CLIP skip in one node.
- Merge checkpoint files with weighted or A + (B - C) recipes, fingerprint source checkpoints, name merge outputs, save merged safetensors files, and preview merges with repeatable prompt cases.
- Apply one LoRA or a six-slot LoRA stack while appending each applied LoRA name to pipe metadata.
- Build positive and negative prompts from simple text inputs, structured character sections, or JSON-backed randomizer categories.
- Normalize and dedupe prompt tags while preserving first occurrence order.
- Inspect prompts for token count, duplicate tags, shared positive/negative tags, and simple conflicts.
- Run KSampler, measure sampling time, update pipe metadata, and optionally decode an image into the pipe when a VAE is available.
- Upscale with ESRGAN/spandrel models and optionally resize the upscaled result.
- Compare two image batches in the frontend with an A/B splitter.
- Add text overlays from metadata fields.
- Add watermark overlays with anchor, scale, opacity, offsets, and optional mask support.
- Save images normally or as previews, with optional ComfyUI workflow metadata, optional A1111/Civitai-compatible `parameters` metadata, and Bubba PNG metadata.
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

### Optional Detailer Dependency

Bubba Detailer uses Ultralytics detector models from `models/ultralytics/bbox` or `models/ultralytics/segm`.
If the Detailer node reports that `ultralytics` is missing, install it into the same Python environment that runs ComfyUI:

```bash
python -m pip install "ultralytics>=8.0,<9"
```

Then restart ComfyUI.

## Quick Workflow Example

1. Use Bubba Combo Loader or Bubba Checkpoint Loader to create a pipe with the model stack.
2. Apply one or more Bubba LoRA Loader nodes, or use Bubba LoRA Stack for a compact multi-LoRA setup.
3. Use Bubba Simple Prompt Builder, Bubba Character Prompt Builder, or Bubba Prompt Randomizer to update pipe prompts and conditioning.
4. Optionally run Bubba Prompt Cleaner and Bubba Prompt Inspector before sampling.
5. Generate a latent with Bubba Empty Latent (Preset Sizes), which writes the latent back to the pipe.
6. Sample with Bubba KSampler using the pipe latent, so sampler settings, seed, timing, and optional decoded image are written back to the pipe.
7. Optionally use Bubba Detailer, Bubba Upscaler, Bubba Add Text Overlay (Metadata), or Bubba Watermark Overlay.
8. Save with Bubba Save Image using the pipe image and embedded metadata.
9. Reload later with Bubba Load Image (With Metadata), which recreates a pipe from embedded metadata.

## Metadata Notes

- Workflow state is represented by the typed `BUBBA_PIPE` object.
- Serialized provenance is represented by the typed `BUBBA_METADATA` object inside the pipe.
- Pipe-aware nodes use explicit socket overrides first, then pipe values, then node defaults or clear errors.
- Pipe inputs are optional on nodes that can create a fresh pipe or use explicit overrides. Bubba Pipe Out requires a pipe because its only job is unpacking one.
- Metadata currently includes `schema_version`, `model_name`, `clip_skip`, `sampler_time_seconds`, `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `seed`, `positive_prompt`, `negative_prompt`, `loras`, and `save_prefix`.
- Older saved metadata that uses `filepath` is still accepted and migrated to `save_prefix`.
- Bubba Metadata Debug displays pretty JSON directly on the node and still outputs the same text for wiring.
- Bubba View Text displays connected multiline strings directly on the node and passes the text through unchanged.
- Bubba Save Image embeds metadata into PNG text under `bubba_metadata`.
- Bubba Save Image can also embed ComfyUI `prompt` and `workflow` metadata when `save_workflow_metadata` is enabled.
- Bubba Save Image can also embed an A1111/Civitai-compatible `parameters` text block when `save_a1111_metadata` is enabled.
- The Save Image node shows a frontend metadata warning when connected Bubba metadata is empty/default, or when PNG metadata embedding fails for one or more saved files.
- Bubba Load Image (With Metadata) reads `bubba_metadata` from PNG text and reconstructs `BUBBA_METADATA`.

## Prompt Notes

- Supported `format_mode` values are `booru`, `prose`, and `hybrid`.
- Bubba Simple Prompt Builder supports deterministic inline choices such as `{red|blue|green}`.
- It also expands file wildcards such as `__lighting__` and `__locations/nightclub__` from `src/bubba_nodes/data/wildcards`.
- Wildcard files contain one choice per line; blank lines and lines beginning with `#` are ignored.
- A `prompt_seed` of `-1` inherits `metadata.seed`, then falls back to `0`. Non-negative values explicitly control prompt expansion, and the after-generate control can keep, increment, decrement, or randomize it.
- Escape prompt syntax with a backslash, for example `\{red|blue\}` or `\__lighting__`.
- Wildcards and inline choices can expand recursively up to a safe depth. Missing files and recursive cycles are reported without executing arbitrary code.
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
- Type `__` to browse wildcard files recursively; continuing to type filters the list, and selection inserts the complete token such as `__locations/nightclub__`.
- Type part of a tag to open suggestions.
- Use arrow keys to select, then press Tab or Enter to insert.
- Add custom words from ComfyUI settings using local storage.
- Enable or disable local-tag suggestions with `Bubba: Include Local CSV Tags`.
- Tune checkpoint, empty latent size, and LoRA menus separately with hover preview, dense rows, font scale, icon scale, and max recent-count settings.
- Tag data is read from source-specific CSV files in `web/comfyui/tags/` when available, currently `danbooru.csv` and `e621.csv`.
- If source-specific CSV files are unavailable, autocomplete falls back to the bundled legacy `web/comfyui/danbooru_e621_merged.csv`.
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
