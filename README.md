# Bubba Nodes

Custom ComfyUI nodes for prompt authoring, prompt inspection, metadata-first workflows, overlays, and save/load helpers.

## What Is Included

This extension currently registers 15 nodes:

- Bubba Filename Builder
- Bubba Empty Latent (Preset Sizes)
- Bubba Load Image (With Metadata)
- Bubba Checkpoint Loader
- Bubba KSampler
- Bubba Save Image
- Bubba Add Text Overlay
- Bubba Add Text Overlay (Metadata)
- Bubba Metadata Bundle
- Bubba Metadata Debug
- Bubba Metadata Update
- Bubba Character Prompt Builder
- Bubba Metadata Prompt Builder
- Bubba Prompt Cleaner
- Bubba Prompt Inspector

## Features

- Build clean relative file paths from character + scene names.
- Generate empty latents from preset dimensions with optional orientation swap.
- Load images and extract embedded Bubba metadata from PNG text.
- Load checkpoint model/clip/vae while also outputting the selected checkpoint name for metadata/overlay nodes.
- Run KSampler and output a formatted INFO string (time, seed, steps, CFG, sampler, scheduler, denoise).
- Run KSampler and update a metadata object with sampler info and seed.
- Add top/bottom metadata bars to generated images in overlay mode or underlay mode.
- Add overlays directly from a bundled metadata object (without wiring prompt/model/info fields separately).
- Bundle core generation metadata into a typed metadata object for downstream nodes.
- Convert metadata objects to pretty JSON text for preview/debug nodes.
- Update selected fields on an existing metadata object without rebuilding it from scratch.
- Build structured positive/negative prompts from sections (appearance, body, clothing, pose, expression, scene, style, quality).
- Build prompt sections directly into metadata with prompt section persistence.
- Normalize and dedupe prompt tags.
- Inspect prompts for token count, duplicates, and conflict warnings.
- Use in-node prompt autocomplete for Bubba multiline prompt fields (appearance/body/style/negative/etc.) with keyboard navigation.
- Save images normally or preview-only through ComfyUI UI helpers, with optional filepath pulled from metadata.
- Open a standalone Asset Viewer web page to browse image assets in Comfy input/output folders and inspect embedded metadata outside the main ComfyUI canvas.

## Standalone Asset Viewer

- Open ComfyUI settings and use `Bubba: Asset Viewer -> Open Standalone Page`.
- The viewer loads roots from Comfy image input and output folders and scans files recursively.
- Metadata fields are parsed from `.png` text chunks where available.
- You can also open directly by URL: `/extensions/bubba_nodes/comfyui/asset_viewer.html`

Backend endpoints exposed by this extension:

- `GET /bubba/assets/roots`
- `GET /bubba/assets/list?root=<path-or-key>&q=<search>&ext=.png&limit=1200&include_metadata=true`

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

1. Use Bubba Character Prompt Builder to produce positive/negative prompts and conditioning.
2. Optionally run Bubba Prompt Cleaner and Bubba Prompt Inspector for quality checks.
3. Build metadata with Bubba Metadata Bundle, or use Bubba Metadata Prompt Builder to create prompts and metadata together.
4. Load checkpoint and sample with Bubba KSampler so sampler info/seed are written back into metadata.
5. Decode latent to image in your normal pipeline.
6. Use Bubba Add Text Overlay (Metadata) to render model/info/prompt text from metadata.
7. Use Bubba Filename Builder when you want an explicit path string outside metadata.
8. Save with Bubba Save Image and optionally reload with Bubba Load Image (With Metadata).

## Metadata Notes

- Metadata is represented by the typed BUBBA_METADATA object.
- Metadata includes model_name, sampler_info, positive_prompt, negative_prompt, seed, filepath, and prompt_sections.
- Bubba Save Image embeds metadata into PNG text under bubba_metadata.
- Bubba Load Image (With Metadata) reads bubba_metadata from PNG text and reconstructs BUBBA_METADATA.

## Prompt Notes

- Supported format_mode values are booru, prose, and hybrid.
- Prompt Inspector outputs:
  - token_count (INT)
  - duplicate_tags (STRING)
  - conflict_warnings (STRING)
  - formatted_preview (STRING)
- Prompt conflict warnings currently include:
  - tags that appear in both positive and negative prompts
  - simple pair checks such as solo/multiple people, male/female, day/night, indoors/outdoors, and safe/nsfw

## Autocomplete Notes

- The frontend extension is loaded from [web/comfyui/autocomplete.js](web/comfyui/autocomplete.js).
- Autocomplete is active on Bubba multiline prompt inputs (for example: appearance, style_tags, quality_tags, negative_tags).
- Type part of a tag to open suggestions.
- Use arrow keys to select, then press Tab or Enter to insert.
- Add your own words from ComfyUI settings using: `Bubba: Edit Autocomplete Words`.
- You can fetch Danbooru tags with usage counts from the API and cache them locally from settings using `Bubba: Danbooru Tag Cache`.
- Enable or disable Danbooru-backed suggestions with `Bubba: Include Danbooru Tags`.
- Danbooru suggestions are ranked by post count so common tags appear first.
- A bundled cache file is supported at [web/comfyui/danbooru_cache.csv](web/comfyui/danbooru_cache.csv) and is used automatically when local cache is empty.
- Use `Full Sync (All >= Min Count)` in settings to fetch all Danbooru tags above your minimum post count (for example, all tags with 50+ uses).
- Use `Export Cache CSV` after syncing to download a prebuilt cache file you can commit back into [web/comfyui/danbooru_cache.csv](web/comfyui/danbooru_cache.csv) for future releases.

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

## Project Layout

- Nodes: [src/bubba_nodes/nodes](src/bubba_nodes/nodes)
- Models: [src/bubba_nodes/models](src/bubba_nodes/models)
- Utilities: [src/bubba_nodes/utils](src/bubba_nodes/utils)
- Tests: [tests](tests)
- Web docs: [web/docs](web/docs)

## Publishing

Package metadata and Comfy registry fields live in [pyproject.toml](pyproject.toml).

If publishing to the Comfy Registry:

1. Verify publisher and metadata under tool.comfy.
2. Create a registry API key.
3. Add the token to repository secrets as REGISTRY_ACCESS_TOKEN.
4. Trigger your release workflow.

Registry docs: https://docs.comfy.org/registry/publishing
