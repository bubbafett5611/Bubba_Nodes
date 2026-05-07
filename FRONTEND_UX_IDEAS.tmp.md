# Frontend UX Ideas

Temporary notes for Bubba Nodes frontend ideas that are worth revisiting later.

## Status Snapshot

Completed:

- Save Result Warnings
- Prompt Preset Snippets
- large parts of Checkpoint And LoRA Combo Polish

Decided not to do:

- Metadata Preview Widget as a separate frontend widget
- on-node checkpoint/LoRA summary strip

Keep as boundary / not a feature target:

- Project Boundary

## Metadata Preview Widget

Status: not planned right now

Reason:

- the existing Metadata Debug node already covers the practical inspection use case well enough
- a separate frontend metadata preview felt redundant for the current pack

Keep this scoped to the active workflow data. Do not turn it into a gallery or asset database.

## Save Result Warnings

Status: completed

Show a small frontend warning when Bubba Save Image returns `metadata_warnings`.

Useful cases:

- PNG saved successfully but metadata embedding failed.
- Some images in a batch received metadata and some did not.
- Workflow metadata was skipped or could not serialize.

This should be a node-level status/toast, not a broader file-management UI.

## Checkpoint And LoRA Combo Polish

Status: mostly completed

Improve the existing checkpoint/LoRA node UI without turning it into an asset browser.

Possible improvements:

- Show selected model preview thumbnail when available.
- Show Civitai link button when sidecar metadata provides one.
- Show selected filename/display name more clearly.
- Show missing-preview state.

Keep management tasks such as downloading previews, organizing libraries, and batch repair outside Bubba Nodes.

Notes:

- shared menu code was cleaned up across checkpoint, LoRA, and latent menus
- menu-level preview/info affordances were improved
- Civitai domain is now configurable
- we tried an on-node summary strip and explicitly removed it because it duplicated the selector menu

## Prompt Preset Snippets

Status: completed

Small local snippets for repeated prompt text:

- Favorite negative prompts
- Common quality tags
- Common style tag groups
- Character/scene fragments

This should stay lightweight and local. If it starts becoming a searchable library, it belongs in a separate asset/tooling project.

Notes:

- snippets can now be created from selected prompt text
- snippets expand inline through `@name` autocomplete
- settings include snippet management plus import/export
- autocomplete shows snippet previews
- prompt-side snippet saves show confirmation

## Project Boundary

Status: keep as boundary

Bubba Nodes should help build and run the current ComfyUI workflow.

Asset browsing, indexing, batch repair, model library management, and saved-image galleries should stay outside the node pack.
