# Bubba Nodes Agent Guide

Guidance for future contributors and coding agents working in this repository.

## Project Shape

Bubba Nodes is a ComfyUI custom node pack focused on practical generation workflows:

- prompt building, cleaning, randomizing, and inspection
- checkpoint, VAE, CLIP, and LoRA loading helpers
- metadata/provenance capture and PNG embedding
- image comparison, overlays, watermarking, upscaling, and save/load helpers
- compact workflow glue that stays compatible with normal ComfyUI sockets

Prefer small, explicit nodes that improve daily graph building. Avoid turning the pack into a broad model manager, asset browser, cloud service bridge, or giant preset database.

## Socket Ordering

Keep input and output socket order consistent across all nodes. The goal is to avoid avoidable wire crossovers in ComfyUI graphs, especially when one node output connects directly into the next node input.

Canonical priority:

1. `pipe`
2. `image`
3. `mask`
4. `latent`
5. `metadata`
6. `model`
7. `clip`
8. `vae`
9. `positive` / positive conditioning
10. `negative` / negative conditioning
11. positive prompt text
12. negative prompt text
13. filename, path, save prefix, or file selector values
14. `seed`
15. `steps`
16. `cfg`
17. `sampler_name`
18. `scheduler`
19. `denoise`
20. `width`
21. `height`
22. `batch_size`
23. model/checkpoint/LoRA/upscale model names
24. strength, scale, weight, opacity, or similar numeric modifiers
25. mode, preset, format, method, or strategy selectors
26. boolean toggles
27. style, layout, placement, anchor, and color options
28. `info`
29. debug text, metadata text, warnings, or diagnostics

### Input Rules

Use this broad input order:

```text
pipe
image
mask
latent
metadata
model
clip
vae
positive
negative
prompt text fields
file/path/save fields
generation controls
node-specific controls
debug/advanced options
```

### Output Rules

Use this broad output order:

```text
pipe
image
mask
latent
metadata
model
clip
vae
positive
negative
prompt strings
filename/path strings
info/debug strings
```

When a node both consumes and emits the same kind of socket, keep that socket in the same relative position on both sides whenever possible. For example, if a node takes `image` then `metadata`, prefer outputs ordered as `image` then `metadata`, not `metadata` then `image`.

## Pipe Direction

If a `BUBBA_PIPE` type is introduced, treat it as the primary workflow/state socket and keep it first on both inputs and outputs.

The pipe should carry generation context, not every possible artifact. A good initial scope is:

- `model`
- `clip`
- `vae`
- positive conditioning
- negative conditioning
- positive prompt text
- negative prompt text
- latest `image`
- latest `mask`
- latest `latent`
- `BubbaMetadata`

Treat `pipe.image`, `pipe.mask`, and `pipe.latent` as convenience state for compact flows such as pipe -> empty latent -> sampler -> overlay -> save. Keep visible image, mask, and latent sockets available so media flow remains understandable in normal ComfyUI graphs.

## Pipe Resolution Rule

For every pipe-aware node, explicit socket inputs override values carried by the pipe. Prefer making the pipe input optional when a node can create a fresh pipe or satisfy its required runtime values from explicit sockets.

Resolution priority:

1. Connected explicit socket input
2. Value from `BUBBA_PIPE`
3. Node default, or a clear error if the value is required

`Bubba Pipe Out` is the natural exception: unpacking a pipe requires a pipe.

Examples:

```text
Save Image:
image input connected -> save that image
else pipe.image exists -> save pipe.image
else error

Overlay:
image input connected -> use that image
else pipe.image exists -> use pipe.image

metadata input connected -> use that metadata
else pipe.metadata exists -> use pipe.metadata

KSampler:
model input connected -> use model input
else pipe.model

positive input connected -> use positive conditioning input
else pipe.positive

negative input connected -> use negative conditioning input
else pipe.negative

vae input connected -> use VAE input
else pipe.vae

Prompt Builder:
clip input connected -> use CLIP input
else pipe.clip
```

When a node resolves a value from either an explicit override or the pipe, write the resolved value back into the outgoing pipe if that value belongs to the pipe schema. This keeps downstream nodes current.

Examples:

```text
explicit image input -> outgoing pipe.image = explicit image
explicit metadata input -> outgoing pipe.metadata = resolved/updated metadata
explicit model input -> outgoing pipe.model = explicit model
explicit positive conditioning -> outgoing pipe.positive = explicit positive conditioning
```

This rule lets users keep graphs compact with pipe-only flows while still allowing any individual value to be overridden locally without breaking downstream pipe behavior.

## Compatibility

Favor backwards-compatible changes:

- Keep existing primitive sockets when adding pipe support.
- Keep `BUBBA_METADATA` usable as an advanced/manual override even if pipe workflows become the primary path.
- Keep `BubbaMetadata` as the compact serialization schema for PNG metadata and reloaded images.

## Implementation Style

- Follow existing node categories and naming conventions.
- Use the repo's helper modules before adding new abstractions.
- Add tests for deterministic behavior, socket order, metadata updates, and serialization.
- Keep optional heavy runtime dependencies lazy-imported so ComfyUI can start without them.
- Use concise comments only where the implementation is not self-explanatory.
