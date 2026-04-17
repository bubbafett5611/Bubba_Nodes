# Bubba Nodes — Planned Additions

## Infrastructure — Tag Database

### SQLite Tag Database (`data/tags.db`)
- Source CSVs: Danbooru and e621 from [sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete)
- Schema:
	```sql
	CREATE TABLE tags (
			id         INTEGER PRIMARY KEY,
			name       TEXT NOT NULL UNIQUE,
			category   TEXT,        -- hair_color, pose, expression, clothing, style, etc.
			post_count INTEGER,     -- used to filter low-quality swap candidates
			aliases    TEXT         -- comma-separated
	);
	CREATE INDEX idx_category ON tags(category);
	CREATE INDEX idx_name     ON tags(name);
	```
- Build script (`scripts/build_tag_db.py`): one-time import of CSVs into `data/tags.db`; ship the `.db` file or the script, not raw CSVs
- Query at runtime only (no CSV loading at node init); stdlib `sqlite3`, zero extra dependencies
- Filter by `post_count` threshold to drop noise tags from swap candidates

---

## Priority 1 — Complete the Save Pipeline

### Bubba Metadata Bundle
- Inputs: model name (STRING), sampler INFO (STRING), positive prompt (STRING), negative prompt (STRING), seed (INT), filepath (STRING)
- Output: single METADATA object (or JSON STRING) passed to downstream nodes
- Goal: consolidate scattered metadata into one bundle rather than wiring many separate strings

### Bubba Save Image + Metadata
- Inputs: IMAGE, METADATA bundle (or individual fields), filepath (STRING), preview_only (BOOLEAN)
- Behavior: embed prompt/seed/sampler data into PNG tEXt chunks AND write a sidecar `.json` alongside the image
- Goal: make saved outputs fully reproducible without relying on the overlay text

### Bubba Filename Template
- Inputs: template string (e.g. `{character}/{scene}/{date}_{seed}`), individual token values (character, scene, seed, date)
- Output: sanitized filepath STRING
- Goal: succeeds the current `BubbaFilename` builder with dynamic tokens and optional truncation per segment

---

## Priority 2 — Prompt Workflow Improvements

### Bubba Prompt Inspector
- Inputs: positive (STRING), negative (STRING)
- Outputs: token count (INT), duplicate tag list (STRING), conflict warnings (STRING), formatted preview (STRING)
- Goal: surface issues in prompt sections before sampling, built on existing clean/dedupe logic

### Bubba Prompt Variants
- Inputs: sections_text (STRING from BubbaCharacterPromptBuilder), variant_count (INT), swap_sections (multi-select: style, scene, expression, pose), min_post_count (INT, default 100)
- Output: batch of positive prompts (STRING list), batch of negative prompts (STRING list)
- Tag source: `data/tags.db` — queries by category and post_count threshold; falls back to existing section values if DB not present
- Goal: produce N prompt variations by swapping tags sourced from the full Danbooru/e621 dataset, filtered to relevant categories

### Bubba Preset Manager
- Inputs: action (list/rename/duplicate/delete/export/import), preset_name (STRING), new_name (STRING, optional), json_snippet (STRING, optional)
- Output: result message (STRING), updated preset list (STRING)
- Goal: extend load/save presets with full CRUD and import/export on top of the existing `prompt_presets.json`

---

## Priority 3 — Batch & Comparison Tools

### Bubba Seed Explorer
- Inputs: model, positive, negative, latent_image, seed_start (INT), seed_count (INT), steps, cfg, sampler_name, scheduler
- Outputs: IMAGE batch, INFO summary (STRING listing each seed + time)
- Goal: run N seeds in one node and pair with BubbaOverlay + Contact Sheet for comparison grids

### Bubba Contact Sheet
- Inputs: IMAGE batch, label_text batch (STRING list), columns (INT), cell_padding (INT), font_size (INT), background_color (STRING)
- Output: IMAGE (single composite grid)
- Goal: labeled comparison grid from any batch; natural follow-on to Seed Explorer and overlay metadata
