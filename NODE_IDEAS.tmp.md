# Node Ideas

Temporary notes for Bubba Nodes node ideas that feel like a good fit, but are not priorities right now.

## Metadata Merge

Combine two `BUBBA_METADATA` inputs with explicit precedence.

Possible behavior:

- `base_metadata` plus `override_metadata`
- `loras` merge mode:
  - append
  - replace
  - dedupe append
- output a single merged metadata object

This fits the current metadata-first workflow without adding a new subsystem.

## Metadata Extract Fields

Break `BUBBA_METADATA` back out into practical outputs for filenames, overlays, debug flows, and external tools.

Possible outputs:

- model name
- positive prompt
- negative prompt
- seed
- sampler info
- LoRAs as CSV
- filepath

Keep this as a simple glue node, not a generic schema browser.

## Save Manifest

Write a small JSON or JSONL manifest entry for saved images.

Possible uses:

- audit what was saved
- carry save paths plus metadata digest forward
- help external tooling consume results without creating a dependency between projects

This should stay workflow-local and lightweight, not become a library indexer.

## Prompt Budget Guide

Inspect prompt length and section balance in a more workflow-aware way than a raw token count alone.

Possible outputs:

- estimated token pressure
- likely truncation risk
- warning text for oversized positive or negative sections
- section balance hints such as style or quality tags dominating the prompt

This should help users write better prompts, not act like a strict validator.

## Character Section Presets

Store and reuse structured prompt-builder sections for recurring characters or scenes.

Possible scope:

- appearance
- body
- clothing
- pose
- expression
- scene
- style tags
- quality tags
- negative tags

This should complement snippets rather than replace them. Snippets are inline text reuse; this would be structured section reuse.

## Boundaries

If these are revisited later, keep them inside the current Bubba Nodes identity:

- metadata-first workflow helpers
- prompt-building and prompt-quality tools
- practical save/load utilities

Avoid drifting into:

- asset browsing
- model library management
- cloud services
- moderation systems
- giant preset databases
