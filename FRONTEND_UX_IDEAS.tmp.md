# Frontend UX Ideas

Temporary notes for Bubba Nodes frontend ideas that are worth revisiting later.

## Metadata Preview Widget

A compact view for metadata/debug/save-related nodes that shows the current `BUBBA_METADATA` payload in a readable format:

- Model name
- LoRAs
- Seed
- Sampler settings
- Positive and negative prompts
- Filepath
- Save metadata warnings, when present

Keep this scoped to the active workflow data. Do not turn it into a gallery or asset database.

## Save Result Warnings

Show a small frontend warning when Bubba Save Image returns `metadata_warnings`.

Useful cases:

- PNG saved successfully but metadata embedding failed.
- Some images in a batch received metadata and some did not.
- Workflow metadata was skipped or could not serialize.

This should be a node-level status/toast, not a broader file-management UI.

## Checkpoint And LoRA Combo Polish

Improve the existing checkpoint/LoRA node UI without turning it into an asset browser.

Possible improvements:

- Show selected model preview thumbnail when available.
- Show Civitai link button when sidecar metadata provides one.
- Show selected filename/display name more clearly.
- Show missing-preview state.

Keep management tasks such as downloading previews, organizing libraries, and batch repair outside Bubba Nodes.

## Prompt Preset Snippets

Small local snippets for repeated prompt text:

- Favorite negative prompts
- Common quality tags
- Common style tag groups
- Character/scene fragments

This should stay lightweight and local. If it starts becoming a searchable library, it belongs in a separate asset/tooling project.

## Project Boundary

Bubba Nodes should help build and run the current ComfyUI workflow.

Asset browsing, indexing, batch repair, model library management, and saved-image galleries should stay outside the node pack.
