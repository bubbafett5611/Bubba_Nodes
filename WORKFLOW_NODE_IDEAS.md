# Workflow-Driven Node and Prompt Feature Ideas

This document is based on the current Bubba Nodes workflows, including the dedicated merge workflow. It describes additions that would reduce repeated graph wiring, make model and LoRA experiments easier to compare, and improve provenance without expanding Bubba Nodes into a general model manager.

The ideas are ordered roughly by expected value. They are designs, not commitments to implement every item.

## Shared Design Rules

All proposed nodes should follow the repository socket-ordering and pipe-resolution rules:

- `pipe` is first when present.
- Explicit socket inputs override values in `BUBBA_PIPE`.
- Resolved values are written back into the outgoing pipe when they belong to the pipe schema.
- Visible image, mask, latent, model, conditioning, and metadata sockets remain available where they help users understand the graph.
- Existing `BUBBA_METADATA` sockets remain usable as manual overrides.
- Heavy or optional dependencies are imported lazily.
- Deterministic operations expose or inherit a seed and record enough information to reproduce the result.

## 1. Bubba Image-to-Image Prep

### Purpose

Replace the repeated `Load Image -> Image Scale -> VAE Encode` chain with one pipe-aware preparation node.

### Inputs

1. `pipe` (optional)
2. `image` (optional explicit override)
3. `vae` (optional explicit override)
4. target width
5. target height
6. resize method
7. fit mode
8. crop anchor
9. multiple-of constraint

Suggested fit modes:

- `stretch`
- `contain`
- `cover_crop`
- `pad`
- `keep_original`

### Outputs

1. `pipe`
2. prepared `image`
3. encoded `latent`
4. `metadata`
5. `info`

### Behavior

- Resolve the image and VAE from explicit inputs first, then the pipe.
- Resize and crop before encoding.
- Optionally round dimensions to a model-safe multiple such as 8, 16, 32, or 64.
- Write the prepared image and encoded latent to `pipe.image` and `pipe.latent`.
- Preserve the input image when `keep_original` is selected.
- Return a clear error if no image or VAE is available.

### Metadata

The current compact metadata schema does not need to store every resize setting initially. The `info` output should report original size, final size, fit mode, and crop/padding. These fields could later move into a structured image-preparation provenance block.

## 2. Bubba Refiner Pass

### Purpose

Make the common second low-denoise sampling pass explicit and compact, including workflows that replace the base checkpoint with a different refinement model.

### Inputs

1. `pipe` (optional)
2. `latent` (optional)
3. `model` (optional)
4. `positive` (optional)
5. `negative` (optional)
6. `vae` (optional)
7. seed
8. steps
9. cfg
10. sampler
11. scheduler
12. denoise
13. decode image

### Outputs

1. `pipe`
2. `image`
3. `latent`
4. `metadata`
5. `info`

### Behavior

- Resolve the incoming latent and generation stack from explicit inputs, then the pipe.
- Run a second sampling pass with a conservative default denoise such as `0.25` or `0.30`.
- Allow a replacement model while retaining existing conditioning unless explicitly overridden.
- Optionally decode the refined latent and update `pipe.image`.
- Clearly distinguish this operation from the initial generation in the info output.

### Metadata

Refiner provenance should eventually retain both stages rather than overwriting the base sampler settings. A future schema could include a `sampling_stages` list containing model, seed, steps, CFG, sampler, scheduler, and denoise for each pass.

## 3. Bubba Parameter Sweep

### Purpose

Generate controlled variations without manually duplicating nodes or workflows.

### Initial Scope

Support one changing parameter per node:

- CFG
- denoise
- steps
- seed
- LoRA strength
- sampler
- scheduler

Keeping the first version one-dimensional avoids a combinatorial UI and unexpectedly huge queues.

### Inputs

1. `pipe`
2. optional explicit latent/model/conditioning overrides
3. parameter selector
4. values as CSV or start/end/step
5. base seed
6. seed behavior
7. decode images

Seed behavior:

- `fixed`: every candidate uses the same seed
- `increment`: add the candidate index
- `randomized`: deterministically derive candidate seeds from the base seed

### Outputs

1. candidate pipes or a structured sweep result
2. image batch
3. latent batch
4. labels
5. `info`

### Behavior

- Hold every non-selected setting constant.
- Preserve candidate order.
- Generate a label for each result, such as `cfg=4.0` or `denoise=0.30`.
- Refuse an empty value list and cap the number of candidates by default.
- Avoid silently combining incompatible latent batch shapes.

### Metadata

Each candidate needs its own settings. A single `BUBBA_METADATA` object cannot accurately represent a heterogeneous batch, so this node should use a dedicated sweep-result payload or return labels alongside images until batch-aware provenance is designed.

## 4. Bubba Contact Sheet

### Purpose

Turn generated batches and experimental candidates into a readable comparison grid.

### Inputs

1. `pipe` (optional)
2. `image` batch
3. optional labels
4. columns
5. cell width
6. cell height
7. fit mode
8. background color
9. label placement
10. font size
11. include metadata summary

### Outputs

1. `pipe`
2. contact-sheet `image`
3. `metadata`
4. layout/label `info`

### Behavior

- Preserve image aspect ratio by default.
- Pad cells rather than distort images.
- Label candidates with supplied text or selected metadata fields.
- Support model, seed, ratio, CFG, denoise, and LoRA summaries.
- Handle partial final rows.
- Update `pipe.image` with the contact sheet while leaving source images untouched.

### Metadata

The output metadata should describe the sheet as a comparison artifact. Individual candidate metadata should remain in the associated sweep or comparison payload rather than being flattened into one record.

## 5. Bubba LoRA Recipe Preset

### Purpose

Save and reuse named combinations of LoRAs and strengths without turning the extension into a LoRA browser.

### Inputs

1. `pipe` (optional)
2. `model` (optional)
3. `clip` (optional)
4. recipe name
5. recipe selector
6. action
7. optional per-slot LoRA names and strengths
8. replace or append mode

Suggested actions:

- `load`
- `save`
- `update`
- `delete` with explicit confirmation

### Outputs

1. `pipe`
2. `metadata`
3. `model`
4. `clip`
5. recipe summary
6. `info`

### Behavior

- Store small local JSON recipes containing ordered LoRA names, model strengths, and CLIP strengths.
- Apply entries in recipe order.
- Report missing LoRA files without crashing ComfyUI startup.
- Allow an incoming pipe to retain its current LoRAs or replace them, based on the selected mode.
- Keep recipe files user-authored and portable.

### Metadata

Applied LoRAs should continue to populate `metadata.loras`. A future structured representation should retain model and CLIP strengths instead of storing names alone.

## 6. Bubba Merge Ratio Sweep

### Purpose

Evaluate several weighted blends of checkpoints A and B with identical generation conditions.

### Inputs

1. optional base `pipe`
2. checkpoint A
3. checkpoint B
4. ratios as CSV or start/end/step
5. optional external CLIP
6. optional external VAE
7. positive conditioning or prompt-test configuration
8. latent
9. fixed seed and sampler settings
10. candidate limit

### Outputs

1. structured merge-sweep result
2. image batch
3. ratio labels
4. candidate recipe summary
5. `info`

### Behavior

- Build each weighted merge using the same source checkpoints.
- Use the same prompt, latent dimensions, seed, and sampling settings for every candidate.
- Keep each `BUBBA_CHECKPOINT_MERGE` payload associated with its preview.
- Ratios should be normalized, deduplicated, sorted only when requested, and constrained to `0.0-1.0`.
- Avoid automatically saving every candidate checkpoint.
- Permit a later selector to promote one candidate to `Bubba Save Checkpoint`.

### Performance and Safety

Merged state dictionaries can consume substantial memory. The implementation should process candidates sequentially where possible and release unselected models promptly. A conservative candidate cap should be enabled by default.

## 7. Bubba Merge Test Suite

### Purpose

Run multiple repeatable prompt cases against one merge so it is not judged from a single image type.

### Inputs

1. `pipe`
2. `checkpoint_merge` (optional when the pipe already contains the merged model)
3. test-case multiselect or preset suite
4. optional custom positive and negative additions
5. external CLIP override
6. external VAE override
7. dimensions
8. fixed seed strategy
9. sampler settings

### Outputs

1. image batch
2. test names
3. structured test results
4. optional contact sheet
5. `info`

### Behavior

- Reuse the existing portrait, full-body anatomy, dynamic scene, style stress, and lighting/color cases.
- Use fixed seeds per test case so separate merge candidates remain comparable.
- Allow custom text to append to every case.
- Preserve case order.
- Optionally generate the contact sheet directly, but also expose the raw image batch.

### Metadata

Each image needs the test-case name, prompt, seed, merge recipe, and sampler settings. This is another case where a dedicated result payload is safer than pretending one metadata object describes the entire batch.

## 8. Bubba Merge Comparison

### Purpose

Compare a merge against source A, source B, or another merge under identical conditions.

### Inputs

1. comparison pipe or shared generation settings
2. candidate A model or merge payload
3. candidate B model or merge payload
4. CLIP
5. VAE
6. positive and negative conditioning
7. latent
8. seed and sampler settings
9. labels
10. output layout

### Outputs

1. image A
2. image B
3. comparison image
4. candidate labels
5. comparison result
6. `info`

### Behavior

- Generate both candidates from the same starting latent and settings.
- Support side-by-side, splitter, and stacked layouts.
- Use source and recipe names as automatic labels.
- Do not mutate either candidate payload.
- Make accidental unequal seeds or dimensions visible as warnings.

### Metadata

The comparison result should carry independent metadata for both candidates plus the shared evaluation settings.

## 9. Bubba Merge Candidate Selector

### Purpose

Promote one result from a merge sweep or comparison to the existing naming and save pipeline.

### Inputs

1. merge-sweep result
2. candidate selector
3. optional manual label

### Outputs

1. selected `pipe`
2. selected `checkpoint_merge`
3. selected `metadata`
4. selected preview `image`
5. selected recipe
6. `info`

### Behavior

- Populate the selector from available candidate labels where frontend support permits.
- Return the original merge payload, not a reconstructed approximation.
- Include the selected ratio, sources, preview seed, and test case in `info`.
- Fail clearly when the selected candidate no longer exists.

### Relationship to Existing Nodes

The selected payload should connect directly to `Bubba Merge Naming Helper` and `Bubba Save Checkpoint`.

## 10. Bubba Merge Compatibility Check

### Purpose

Inspect source checkpoints before allocating memory for a full merge.

### Inputs

1. checkpoint A
2. checkpoint B
3. optional checkpoint C
4. comparison depth
5. strictness

Suggested comparison depths:

- `headers_only`
- `keys_and_shapes`
- `full_statistics`

### Outputs

1. compatible boolean
2. architecture/family summary
3. matching tensor count
4. shape mismatch count
5. A-only and B-only counts
6. warning text
7. `info`

### Behavior

- Compare state-dictionary keys, tensor shapes, and available architecture metadata.
- Warn about likely incompatible model families.
- Report whether CLIP or VAE components appear absent or inconsistent.
- Distinguish hard incompatibility from ordinary unmatched keys.
- Never claim that matching shapes guarantee a good artistic merge.

### Performance

Use safetensors headers or lazy inspection when available. Full tensor loading should not be required for the default check.

## 11. Bubba Merge Preview Setup

### Purpose

Reduce the repeated external CLIP, external VAE, test-prompt, dimensions, and evaluation-seed setup around merge previews.

### Inputs

1. `pipe`
2. `checkpoint_merge` (optional)
3. external CLIP name
4. CLIP type
5. external VAE name
6. test case
7. custom positive
8. custom negative
9. append custom text
10. size preset
11. orientation
12. batch size
13. evaluation seed

### Outputs

1. `pipe`
2. `latent`
3. `metadata`
4. positive conditioning
5. negative conditioning
6. test name
7. `info`

### Behavior

- Load the selected external CLIP and VAE only when configured.
- Use components already carried by the merge pipe when external overrides are disabled.
- Build conditioning through the same prompt-processing pipeline used by other prompt fields.
- Create a repeatable evaluation latent.
- Write all resolved generation context into the outgoing pipe.

### Boundary

This node is a merge-evaluation convenience node, not a general model-stack manager. `Bubba Combo Loader` remains the general generation loader.

## 12. Bubba Merge Report

### Purpose

Produce a portable record of how a merge was created and evaluated.

### Inputs

1. merge payload or sweep/comparison result
2. optional saved checkpoint path
3. optional preview paths
4. report format
5. output filename
6. include fingerprints
7. include prompts

Suggested formats:

- Markdown
- JSON
- both

### Outputs

1. report text
2. report path
3. `info`

### Behavior

- Include source names, fingerprints, recipe, ratio/strength, tensor statistics, model architecture warnings, preview settings, prompts, seeds, and saved checkpoint path.
- Use relative ComfyUI model names where possible.
- Avoid embedding full images in Markdown; link or list their paths.
- Make reports deterministic so version-control diffs remain useful.

### Boundary

This is workflow-local provenance, not a searchable model database.

## 13. Bubba Metadata Extract Fields

### Purpose

Expose practical metadata fields without routing pretty-printed JSON through generic text nodes.

### Inputs

1. `pipe` (optional)
2. `metadata` (optional explicit override)

### Outputs

Follow canonical output order:

1. `pipe`
2. `metadata`
3. model name
4. positive prompt
5. negative prompt
6. save prefix
7. seed
8. steps
9. CFG
10. sampler name
11. scheduler
12. denoise
13. LoRAs as text
14. sampler summary
15. `info`

### Behavior

- Resolve explicit metadata before `pipe.metadata`.
- Pass the pipe and metadata through unchanged.
- Use stable, simple scalar outputs suitable for filename, overlay, and external text nodes.
- Return empty/default values rather than errors for optional metadata fields.

## 14. Bubba Filename Template

### Purpose

Build richer image and checkpoint paths from workflow context without repeatedly editing manual folder/name fields.

### Inputs

1. `pipe` (optional)
2. `metadata` (optional)
3. template
4. character
5. scene
6. custom label
7. date/time mode
8. missing-value behavior
9. add numeric collision suffix

Example:

```text
{character}/{scene}/{model}_{seed}_{date}
```

Merge-focused example:

```text
MergeTests/{source_a}-{source_b}/r{ratio}/{test_case}_{seed}
```

### Supported Fields

Initial fields should include:

- `{model}`
- `{seed}`
- `{steps}`
- `{cfg}`
- `{sampler}`
- `{scheduler}`
- `{denoise}`
- `{loras}`
- `{character}`
- `{scene}`
- `{label}`
- `{date}`
- `{time}`
- `{source_a}`
- `{source_b}`
- `{source_c}`
- `{ratio}`
- `{strength}`
- `{test_case}`

### Outputs

1. `pipe`
2. `metadata`
3. save prefix
4. filename-safe label
5. `info`

### Behavior

- Sanitize each substituted segment.
- Prevent absolute paths and parent-directory traversal.
- Provide selectable behavior for missing values: blank, fallback text, or error.
- Update `metadata.save_prefix` and the outgoing pipe.

## 15. Bubba Character/Prompt Section Presets

### Purpose

Reuse structured prompt-builder sections for recurring characters, scenes, or style packages.

### Inputs

1. preset selector
2. action
3. preset name
4. appearance
5. body
6. clothing
7. pose
8. expression
9. scene
10. style tags
11. quality tags
12. negative tags
13. merge mode

Suggested merge modes:

- `replace_all`
- `fill_empty`
- `append`
- `section_by_section`

### Outputs

1. each structured prompt section in canonical prompt order
2. preset name
3. `info`

### Behavior

- Store presets as small, readable local JSON files.
- Keep the schema aligned with `Bubba Character Prompt Builder`.
- Preserve field text exactly; wildcard expansion belongs to the shared prompt-processing stage.
- Treat inline autocomplete snippets and section presets as complementary:
  - snippets insert text while editing;
  - presets restore a structured group of fields.

### Boundary

This should not become a large bundled character database.

## 16. Shared Prompt Field Processing

This replaces the earlier proposal for a separate **Bubba Prompt Variation Builder** node. Wildcards, inline choices, variables, and similar transformations are more useful when they work directly inside the prompt fields users already edit.

### Goals

- Make prompt fields expressive without adding graph clutter.
- Keep expansion deterministic when a seed is fixed.
- Show users both what they authored and what was actually encoded.
- Use one backend implementation across all Bubba prompt-producing nodes.
- Avoid breaking existing plain-text prompts.

### Nodes and Fields That Should Use It

At minimum:

- `Bubba Simple Prompt Builder`
  - positive
  - negative
- `Bubba Character Prompt Builder`
  - appearance
  - body
  - clothing
  - pose
  - expression
  - scene
  - style tags
  - quality tags
  - negative tags
- `Bubba Prompt Randomizer`
  - prefix text
  - extra positive
  - negative prompt
- `Bubba Prompt Cleaner`
  - positive prompt
  - negative prompt
- `Bubba Merge Preview Prompt Runner`
  - custom positive
  - custom negative

Future prompt-bearing fields should opt into the same helper rather than implementing their own syntax.

### Proposed Syntax

#### File Wildcards

```text
__lighting__
__characters/female__
__locations/nightclub__
```

Each wildcard resolves to one non-empty line from a text file in a configured local wildcard directory. Nested paths are allowed, but path traversal and absolute paths are rejected.

Recommended file layout:

```text
wildcards/
  lighting.txt
  characters/
    female.txt
  locations/
    nightclub.txt
```

Blank lines and lines beginning with `#` should be ignored.

#### Inline Choices

```text
{red|blue|green} dress
{day|night}
{standing|sitting|dancing}
```

One alternative is selected deterministically from each group.

Optional weighted choices could be added later:

```text
{red::3|blue::1|green::1}
```

Weighted syntax should not be included in the first implementation unless its parsing and escaping rules are unambiguous.

#### Variables

Useful workflow variables could be exposed with a syntax that does not collide with inline choices:

```text
${seed}
${model}
${character}
${scene}
```

The first version should support only a small documented set. Unknown variables should remain visible and produce a warning instead of silently disappearing.

### Escaping

Users need a way to write literal syntax:

```text
\{red|blue\}
\__not_a_wildcard__
\${not_a_variable}
```

Escapes should be removed after processing.

### Seed Resolution

Prompt expansion must be deterministic. Suggested seed priority:

1. Explicit prompt-processing seed input, when the node exposes one.
2. Seed carried by the pipe or metadata.
3. A stable default of `0`.

Each field should derive its own random stream from:

- base seed
- node purpose
- field name
- occurrence index

This prevents adding a wildcard to the negative prompt from unexpectedly changing every choice in the positive prompt.

The generated choices should remain stable when unrelated graph nodes are added or moved.

### Processing Order

Use one documented order:

1. Preserve the raw authored text.
2. Substitute known variables.
3. Expand file wildcards.
4. Resolve inline choices.
5. Repeat wildcard/choice expansion up to a safe recursion limit.
6. Remove escape markers.
7. Run existing cleanup.
8. Run existing deduplication.
9. Format structured sections.
10. Encode conditioning.
11. Store resolved prompts in the pipe and metadata.

This order allows a wildcard line to contain another wildcard or an inline choice while preventing infinite recursion.

### Limits and Error Handling

- Default maximum expansion depth: 10.
- Default maximum resolved prompt length: configurable, with a conservative hard ceiling.
- Missing wildcard files should leave the original token visible and add a warning.
- Empty wildcard files should behave the same way.
- Circular wildcard references should stop at the recursion limit and report the chain.
- Invalid paths must never read outside configured wildcard roots.
- The processor should not execute Python, templates, shell expressions, or arbitrary code.

### Metadata and Reproducibility

The final resolved positive and negative prompts should remain in the existing `positive_prompt` and `negative_prompt` fields because those represent what was encoded.

A future metadata schema revision should also retain:

- raw positive prompt
- raw negative prompt
- prompt expansion seed
- selected wildcard values
- wildcard file names
- warnings

Until the schema is expanded, nodes should expose an `info` or expansion-report output containing this information.

### Frontend Experience

Prompt fields should provide lightweight visual help:

- syntax highlighting or chips for recognized wildcards
- warning styling for missing wildcard files
- autocomplete suggestions for wildcard names
- a refresh-wildcards action
- a compact resolved-prompt preview
- an optional “reroll prompt choices” seed button

The backend remains authoritative. Frontend preview and queued execution must use the same parsing rules so the displayed result does not differ from the generated result.

### Interaction With Existing Features

- Autocomplete continues to suggest tags and embeddings.
- Wildcard autocomplete should be a separate suggestion source.
- Cleanup and dedupe operate on resolved text, not wildcard tokens.
- Prompt Inspector should inspect resolved prompts and optionally show raw-to-resolved differences.
- Prompt Randomizer category choices can coexist with text wildcards; both should derive randomness from the same base seed but separate deterministic streams.
- Weighted Stable Diffusion prompt syntax such as `(tag:1.2)` should pass through untouched.
- Inline-choice braces must not treat ordinary prose braces as valid unless they contain an unescaped `|`.

### Suggested Shared Backend API

The implementation should live in a prompt utility module and return a structured result rather than only a string:

```python
PromptExpansionResult(
    raw_text="a {red|blue} dress, __lighting__",
    resolved_text="a blue dress, soft rim lighting",
    seed=42,
    selections=[
        {"type": "choice", "source": "{red|blue}", "value": "blue"},
        {"type": "wildcard", "source": "lighting", "value": "soft rim lighting"},
    ],
    warnings=[],
)
```

All prompt-producing nodes should call this shared API before cleanup, formatting, and CLIP encoding.

## 17. Bubba Image Caption to Prompt

### Purpose

Turn the existing vision-language image-description workflow into a reusable prompt-authoring helper.

### Inputs

1. `pipe` (optional)
2. `image`
3. vision-capable text model/encoder
4. instruction
5. maximum tokens
6. temperature
7. output style
8. cleanup
9. dedupe

Suggested output styles:

- detailed description
- concise prose
- booru-like tags
- hybrid

### Outputs

1. `pipe`
2. `metadata`
3. positive prompt text
4. raw caption
5. `info`

### Behavior

- Generate a caption using an explicitly connected compatible model.
- Optionally convert the caption into a cleaned prompt format.
- Pass generated text through shared prompt processing only when explicitly enabled; generated braces should not accidentally become syntax by default.
- Update `pipe.positive_prompt`, but do not invent negative prompts.

### Boundary

Do not download or manage language models. The node should operate on compatible components already available in ComfyUI.

## 18. Bubba Multi-Stage Save

### Purpose

Save raw, detailed, upscaled, and final images with consistent names and provenance.

### Inputs

1. `pipe` (optional)
2. raw image
3. detailed image
4. upscaled image
5. final image
6. `metadata` (optional)
7. base save prefix
8. stage-selection toggles
9. suffix template
10. save workflow metadata
11. save A1111 metadata

### Outputs

1. `pipe`
2. final `image`
3. `metadata`
4. saved paths
5. `info`

### Behavior

- Save only connected and enabled stages.
- Apply predictable suffixes such as `_raw`, `_detail`, `_upscale`, and `_final`.
- Use the same base provenance while adding stage-specific information.
- Return all successful paths and report partial failures clearly.
- Treat the final connected stage as `pipe.image`.

### Boundary

This should remain a compact multi-output convenience, not a full export pipeline.

## 19. Bubba Mask Cleanup

### Purpose

Prepare masks from background removal, segmentation, or watermark inputs before compositing.

### Inputs

1. `pipe` (optional)
2. `mask` (optional)
3. grow/shrink amount
4. feather radius
5. threshold
6. blur radius
7. invert
8. fill holes
9. edge cleanup method

### Outputs

1. `pipe`
2. cleaned `mask`
3. mask preview `image`
4. `info`

### Behavior

- Resolve explicit mask before `pipe.mask`.
- Apply operations in a documented order: threshold, fill holes, grow/shrink, blur/feather, invert.
- Preserve batch dimensions.
- Clamp mask values to the expected range.
- Write the cleaned mask to `pipe.mask`.
- Produce an optional preview that makes soft edges visible.

## Suggested Implementation Order

### Phase 1: Repeated Workflow Friction

1. Shared Prompt Field Processing
2. Bubba Image-to-Image Prep
3. Bubba Metadata Extract Fields
4. Bubba Contact Sheet
5. Bubba Refiner Pass

### Phase 2: Merge Evaluation

1. Bubba Merge Compatibility Check
2. Bubba Merge Ratio Sweep
3. Bubba Merge Test Suite
4. Bubba Merge Candidate Selector
5. Bubba Merge Comparison

### Phase 3: Reusable Recipes and Output

1. Bubba LoRA Recipe Preset
2. Bubba Character/Prompt Section Presets
3. Bubba Filename Template
4. Bubba Multi-Stage Save
5. Bubba Merge Report

### Phase 4: Specialized Utilities

1. Bubba Parameter Sweep
2. Bubba Merge Preview Setup
3. Bubba Image Caption to Prompt
4. Bubba Mask Cleanup

## Recommended First Technical Slice

The first implementation should be the shared prompt processor with:

- deterministic `{a|b|c}` inline choices
- `__file_wildcard__` expansion
- escaping
- safe recursive expansion
- raw/resolved result reporting
- integration into `Bubba Simple Prompt Builder`
- unit tests for deterministic output, missing files, recursion, escaping, cleanup, and dedupe

Once stable, the same helper can be applied to the Character Prompt Builder, Prompt Randomizer, Prompt Cleaner, and Merge Preview Prompt Runner without introducing new graph nodes.
