# Bubba Nodes

Custom ComfyUI nodes focused on prompt building, metadata overlays, filename/path generation, and image saving workflows.

## What Is Included

This extension currently registers 13 nodes:

- Bubba Filename Builder
- Bubba Checkpoint Loader
- Bubba KSampler
- Bubba Save Image
- Bubba Add Text Overlay
- Bubba Add Text Overlay (Metadata)
- Bubba Metadata Bundle
- Bubba Metadata Debug
- Bubba Metadata Update
- Bubba Character Prompt Builder
- Bubba Prompt Cleaner
- Bubba Prompt Preset
- Bubba Prompt Preset Save

## Features

- Build clean relative file paths from character + scene names.
- Load checkpoint model/clip/vae while also outputting the selected checkpoint name for metadata/overlay nodes.
- Run KSampler and output a formatted INFO string (time, seed, steps, CFG, sampler, scheduler, denoise).
- Run KSampler and update a metadata object with sampler info and seed.
- Add top/bottom metadata bars to generated images in overlay mode or underlay mode.
- Add overlays directly from a bundled metadata object (without wiring prompt/model/info fields separately).
- Bundle core generation metadata into a typed metadata object for downstream nodes.
- Convert metadata objects to pretty JSON text for preview/debug nodes.
- Update selected fields on an existing metadata object without rebuilding it from scratch.
- Build structured positive/negative prompts from sections (character, appearance, scene, style, quality, etc.).
- Emit positive/negative conditioning directly from the prompt builder and prompt preset nodes.
- Normalize and dedupe prompt tags.
- Save and load reusable prompt presets from JSON.
- Save images normally or preview-only through ComfyUI UI helpers, with optional filepath pulled from metadata.

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

## Quick Workflow Example

1. Use Bubba Character Prompt Builder (or Bubba Prompt Preset) to produce prompts and conditioning.
2. Build or update metadata with checkpoint, prompt, and filepath information.
3. Use Bubba KSampler for generation and let it update sampler info in metadata.
4. Decode latent to image in your normal pipeline.
5. Use Bubba Add Text Overlay (Metadata) to embed model/info/prompt text.
6. Use Bubba Filename Builder when you want a filepath string outside metadata.
7. Use Bubba Save Image to write to output or preview temp storage.

## Prompt Presets

Preset data is stored in [prompt_presets.json](prompt_presets.json).

- Bubba Prompt Preset Save writes sections to JSON by preset name.
- Bubba Prompt Preset loads a saved preset and allows per-section overrides.
- Supported format modes are booru, prose, and hybrid.

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
- Tests: [tests](tests)
- Web docs: [web/docs](web/docs)
- Prompt presets: [prompt_presets.json](prompt_presets.json)

## Publishing

Package metadata and Comfy registry fields live in [pyproject.toml](pyproject.toml).

If publishing to the Comfy Registry:

1. Verify publisher and metadata under tool.comfy.
2. Create a registry API key.
3. Add the token to repository secrets as REGISTRY_ACCESS_TOKEN.
4. Trigger your release workflow.

Registry docs: https://docs.comfy.org/registry/publishing

