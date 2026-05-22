# BubbaDetailer Node Design

## Goal
Implement a single ComfyUI node that performs ADetailer-style region detection and localized inpaint refinement for both bbox and segm detector models.

This should feel like the rest of Bubba Nodes: compact, metadata-aware, and practical in day-to-day graph building. The node should hide detector plumbing, but expose enough controls that users can tune face/hand/detail passes without needing a large subgraph.

## Scope
- One node supports both bbox and segm.
- Model selection from one dropdown.
- Detection and per-region inpaint in one execution.
- Production behavior only (no Stability Matrix-specific fallback paths).
- Batch-aware for `IMAGE` tensors, with deterministic processing per image.
- No frontend extension required for v1.

## Non-Goals
- Training or downloading detector models.
- Reimplementing ControlNet/Impact-Pack style full workflow builders.
- Global img2img refinement. This node is for localized masked inpaint passes.
- Stability Matrix path discovery. Model visibility must come through ComfyUI's `models_dir`.

## Model Directory Contract
Use ComfyUI's configured model folders, not application-specific install paths. A default ComfyUI install should work with:

- `<ComfyUI models_dir>/ultralytics/bbox`
- `<ComfyUI models_dir>/ultralytics/segm`

Also support ComfyUI extra model paths when they register an ultralytics root or a shared models root:

- `<extra models path>/ultralytics/bbox`
- `<extra models path>/ultralytics/segm`
- `<registered ultralytics path>/bbox`
- `<registered ultralytics path>/segm`

Notes:
- This node pack is production-oriented and must rely on ComfyUI's configured model folders.
- No hardcoded `C:/StabilityMatrix/...` fallback should be implemented.
- If users run launchers such as Stability Matrix, those launchers must expose models through ComfyUI's normal model-folder configuration or extra model paths.

## Node Name
`BubbaDetailer`

## Category
`Bubba Nodes/Generation`

## Recommended User Workflow
1. Generate or load an image.
2. Feed the image, checkpoint model, VAE, positive conditioning, and negative conditioning into `BubbaDetailer`.
3. Select a detector such as `bbox/face_yolov8m.pt` or `segm/person_yolov8n-seg.pt`.
4. Use the returned image for save/upscale/compare nodes.
5. Optionally route the returned mask into preview or compare workflows to inspect what was touched.

## Impact Pack Inspiration
The pinned Impact Pack `FaceDetailer`/`DetailerForEach` implementation is a useful reference, especially around the separation between detection and region refinement:

- Detect first, normalize into segment-like records, then pass those records through a reusable per-region detail loop.
- Process batches one image at a time and offset seeds per image/region for reproducible variation.
- Crop from the current working image, not from stale cached crop pixels, so overlapping regions see previous refinements.
- Feather the crop-local mask before compositing.
- Crop conditioning masks when conditioning entries contain a `mask` field.
- Composite refined crops in pixel space. Impact Pack explicitly avoids latent compositing there because it can hurt quality.
- Return optional debug crops in Impact Pack, but keep BubbaDetailer v1 smaller with `image`, `mask`, `metadata`, and `info` only.

What not to copy directly:

- The large hook/refiner/wildcard surface. BubbaDetailer should stay compact for v1.
- SAM-specific controls. A SAM bridge can be a later extension.
- Impact's pipe types. Bubba Nodes already favors explicit model/clip/vae/conditioning/metadata sockets.

## Inputs
### Required
- `image`: `IMAGE`
- `model`: `MODEL` (inpaint-capable checkpoint/model)
- `vae`: `VAE`
- `positive`: `CONDITIONING`
- `negative`: `CONDITIONING`
- `detector_model_name`: list from both ultralytics folders
- `confidence`: `FLOAT` (default `0.30`, range `0.01..1.0`)
- `mask_dilation`: `INT` (default `4`, range `-64..128`)
- `mask_blur`: `INT` (default `4`, range `0..64`)
- `inpaint_padding`: `INT` (default `32`, range `0..256`)
- `seed`: `INT`
- `steps`: `INT` (default `20`)
- `cfg`: `FLOAT` (default `7.0`)
- `sampler_name`: `comfy.samplers.KSampler.SAMPLERS`
- `scheduler`: `comfy.samplers.KSampler.SCHEDULERS`
- `denoise`: `FLOAT` (default `0.45`, range `0.0..1.0`)
- `max_detections`: `INT` (default `10`, range `1..200`)

### Optional
- `clip`: `CLIP` (needed only if prompt override strings are used)
- `detail_positive`: `STRING` multiline (empty = use incoming `positive`)
- `detail_negative`: `STRING` multiline (empty = use incoming `negative`)
- `include_labels`: `STRING` (comma-separated detector labels to keep)
- `exclude_labels`: `STRING` (comma-separated detector labels to skip)
- `metadata`: `BUBBA_METADATA`

### v1 Input Refinements
Use these exact labels and defaults unless implementation friction says otherwise:

- `detector_model_name`: dropdown values like `bbox/foo.pt` and `segm/bar.pt`.
- `confidence`: default `0.30`, step `0.01`.
- `mask_dilation`: default `4`, allow negative values for erosion.
- `mask_blur`: default `4`, integer radius.
- `inpaint_padding`: default `32`.
- `force_square_crop`: `BOOLEAN`, optional, default `False`.
- `crop_multiple`: hidden/internal constant of `8` for v1, not a user control.

`force_square_crop` is worth adding because portraits and hands often inpaint better with stable framing, but it should remain optional because object/detail masks can waste work when forced square.

## Outputs
- `image`: `IMAGE` (refined/composited)
- `mask`: `MASK` (union of processed regions)
- `metadata`: `BUBBA_METADATA`
- `info`: `STRING` (human-readable detection/refinement summary)

## Model Discovery
Build one dropdown list by combining both directories:

- `bbox/<filename>.pt`
- `segm/<filename>.pt`

Rules:
- Include only `.pt` files.
- Ignore non-model files (`.json`, `.jpeg`, etc.).
- Sort ascending for stable UX.

## Mode Resolution
Infer mode from selected model prefix:

- `bbox/...` -> bbox flow
- `segm/...` -> segmentation flow

No separate mode input is required.

## Internal Structure
Add one public node file and keep most logic in small helpers:

- `src/bubba_nodes/nodes/detailer.py`
  - ComfyUI node class and orchestration.
- `src/bubba_nodes/utils/detailer_core.py`
  - Reusable `detail_each(...)` loop inspired by Impact Pack's `DetailerForEach.do_detail(...)`, but scoped to Bubba data types.
- `src/bubba_nodes/utils/detailer_models.py`
  - Detector model discovery, path resolution, lazy loading, cache.
- `src/bubba_nodes/utils/detailer_masks.py`
  - Detection-to-mask conversion, dilation/erosion, blur, bounds, crop alignment.
- `src/bubba_nodes/utils/detailer_types.py`
  - Lightweight dataclasses for detections and crop plans.

This keeps the node readable and lets tests exercise geometry/mask behavior without importing ComfyUI internals.

## Runtime Dependencies
Use a lazy import for Ultralytics:

```python
from ultralytics import YOLO
```

If import fails, raise a clear node error:

```text
BubbaDetailer requires ultralytics to load detector models. Install it in the ComfyUI Python environment, then restart ComfyUI.
```

Do not import Ultralytics at package import time. ComfyUI should still start even if the dependency is missing and the user is not using this node.

## High-Level Execution Flow
1. Resolve conditioning:
   - If detail override strings are provided, encode with `clip`.
   - Otherwise pass through incoming `positive`/`negative`.
2. Run detector on input image at selected confidence.
3. Convert detections to masks:
   - bbox: rectangle mask from xyxy.
   - segm: polygon/raster mask from segmentation points; fallback to bbox if mask data is missing.
4. Apply mask post-processing:
   - dilation/erosion from `mask_dilation`.
   - feather blur from `mask_blur`.
5. Process detections up to `max_detections`:
   - Compute padded crop from mask bounds using `inpaint_padding`.
   - Clamp to image bounds.
   - Align crop edges to VAE factor (8 px).
   - VAE inpaint encode with local mask.
   - Sample with configured sampler settings and `denoise`.
   - Decode and alpha composite back into the full image.
6. Accumulate union mask.
7. Update metadata and return outputs.

## Detection Ordering
Sort detections by descending mask area before processing.

Rationale:
- Larger regions first reduce artifacts from overlapping edits.
- Deterministic behavior across runs.

## Detector Result Contract
Normalize every detection to this internal shape:

```python
@dataclass(frozen=True)
class DetailerDetection:
    label: str
    confidence: float
    bbox_xyxy: tuple[int, int, int, int]
    mask: torch.Tensor  # H x W, float32, 0.0..1.0
    area: int
```

For bbox models, `mask` is a filled rectangle from `bbox_xyxy`.

For segm models, `mask` comes from the model-provided binary mask when available. If the model returns polygons, rasterize to the original image size. If segmentation data is missing but a bbox is present, use the bbox fallback and record the fallback in `info`.

## Crop Plan Contract
Each processed region should create:

```python
@dataclass(frozen=True)
class DetailerCrop:
    x1: int
    y1: int
    x2: int
    y2: int
    mask: torch.Tensor  # crop-local MASK, H x W
```

Rules:
- Bounds are derived from the post-processed mask, not the raw bbox.
- Padding is applied before clamping.
- Crop width and height are aligned to multiples of 8 by expanding where possible.
- If `force_square_crop` is true, expand the shorter side before 8 px alignment.
- Skip crops smaller than 8x8 after clamping.

## Inpaint Implementation Strategy
Prefer ComfyUI's native inpaint primitives instead of custom latent surgery.

Target approach:
1. Crop image and mask in pixel space.
2. Encode with `VAEEncodeForInpaint` or equivalent native inpaint helper.
3. Sample with `common_ksampler`.
4. Decode with `vae.decode`.
5. Resize decoded crop back to the exact crop size if VAE alignment changed it.
6. Composite over the working image using the softened crop mask.

Keep the initial implementation conservative:
- Process one crop at a time.
- Feed each crop result into the next crop so overlapping regions are deterministic.
- Use `seed + detection_index` to avoid identical noise in repeated regions while preserving reproducibility.

### Conditioning Masks
Before sampling a crop, inspect each conditioning entry. If its details mapping contains a `mask`, crop that mask to the same crop region before passing it to the sampler. Leave all other conditioning details unchanged.

This mirrors Impact Pack's handling and prevents global masked conditioning from being spatially misaligned inside the cropped inpaint pass.

### Pixel-Space Composite
Composite decoded crops back into the working `IMAGE` tensor in pixel space using the feathered crop mask. Do not latent-composite the crop back into the original latent for v1.

Rationale:
- It matches the observed quality choice in Impact Pack.
- It keeps the node usable for input images that did not originate from an available latent.
- It makes no-detection and partial-detection behavior easy to reason about.

### Batch Behavior
Unlike Impact Pack's lower-level `DetailerForEach`, BubbaDetailer should accept `IMAGE` batches at the public node boundary:

- Iterate each image independently.
- Use `seed + batch_index` as the base seed for that image.
- Use `base_seed + detection_index` for each processed crop.
- Concatenate refined images and masks back into normal ComfyUI batch tensors.

This gives users the convenient behavior of Impact's `FaceDetailer.doit(...)` while keeping the internal detail loop simple.

## Empty Detection Behavior
If no valid detections:
- Return original image unchanged.
- Return zero mask.
- Metadata indicates `detailer_detections = 0`.
- `info` says no detections matched confidence/label filters.

## Metadata Additions
Recommended fields to append to `BubbaMetadata`:
- `detailer_model: str`
- `detailer_mode: str` (`bbox` or `segm`)
- `detailer_confidence: float`
- `detailer_detections: int`
- `detailer_denoise: float`
- `detailer_labels: list[str]`
- `detailer_time_seconds: float`

Because `BubbaMetadata` is currently a strict Pydantic model, these fields must be added to `src/bubba_nodes/models/metadata.py` before calling `updated(...)` with them.

## Info String
Return a concise summary useful in ComfyUI previews:

```text
Detector: bbox/face.pt  Mode: bbox  Matched: 3  Processed: 3  Time: 1.842s
Labels: face:3
Fallbacks: segm_to_bbox:0  Skipped: 0
```

Avoid dumping per-box coordinates into the default info output. That belongs in debug logs later if needed.

## Error Handling
- Missing detector model file: raise clear node error with selected model name.
- Segm detection with empty masks: fallback to bbox if available; otherwise skip detection.
- Invalid label filters: treat as no-op, do not crash.
- Empty model dropdown: expose a sentinel like `"No ultralytics models found"` and raise a helpful error if executed.
- Missing `clip` while prompt override text is non-empty: raise a clear error explaining that `clip` is required only for override prompts.
- Detector load failure: include the resolved model path in the error.

## Performance Guardrails
- Enforce `max_detections`.
- Avoid full-image inpaint passes.
- Reuse detector instance when possible (runtime-level cache).
- Cache by absolute model path and file mtime so replacing a `.pt` reloads naturally.
- Convert each batch image to detector input once.
- Keep masks on the same device/dtype as the image only after CPU-side geometry is complete.

## Suggested Defaults
- confidence: `0.30`
- mask_dilation: `4`
- mask_blur: `4`
- inpaint_padding: `32`
- denoise: `0.45`
- max_detections: `10`

## Implementation Notes for This Repo
- Add new node at `src/bubba_nodes/nodes/detailer.py`.
- Register in `src/bubba_nodes/nodes/__init__.py` mappings.
- Keep existing metadata pass-through pattern used by current nodes.
- Use ComfyUI inpaint encode/decode primitives consistent with native inpaint flow.
- Add optional imports inside functions/classes so tests and normal startup do not fail without ComfyUI/Ultralytics runtime extras.

## Test Plan
Unit tests should cover the pieces that are deterministic without running a real detector:

- Model discovery includes only `.pt`, prefixes with `bbox/` and `segm/`, and sorts results.
- Model path resolution rejects bad prefixes and missing files with clear errors.
- Label include/exclude parsing trims whitespace and is case-insensitive.
- Bbox detections convert to expected rectangle masks.
- Segm detections fallback to bbox when segmentation mask is absent.
- Dilation supports positive and negative values.
- Crop planning clamps to image bounds and aligns to 8 px.
- Empty detections return original image, zero mask, and metadata with zero count.
- Node registration includes `BubbaDetailer` and display names match.

Integration tests can be manual for v1 because real Ultralytics + ComfyUI inpaint sampling is environment-heavy.

## Build Order
1. Add metadata fields and tests.
2. Add model discovery/path utilities and tests.
3. Add mask/crop utility dataclasses and tests.
4. Add `BubbaDetailer.INPUT_TYPES`, outputs, registration, and no-detection path.
5. Add detector loading/inference normalization.
6. Add inpaint loop and compositing.
7. Run manual ComfyUI validation with one bbox face model and one segm model.

## Open Design Choice
The only major choice to settle before coding is whether `ultralytics` becomes a declared dependency in `pyproject.toml`/`requirements.txt`.

Recommended: keep it as an optional runtime dependency for v1 and show a clear error only when the node runs. Declaring it as mandatory would make the whole node pack heavier for users who only want prompt, metadata, save, or upscale nodes.

## Future Extensions
- Per-class denoise or per-class prompt map.
- Optional non-maximum suppression tuning.
- Optional "merge overlapping masks" strategy switch.
- Iterative multi-pass detailing.
- Debug output with detection boxes/masks as preview images.
- Separate "Detect Only" utility node if users want reusable masks without inpainting.
