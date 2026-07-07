# ComfyUI Modernization and Public API Adoption

Status: implemented  
Audit baseline: ComfyUI v0.27.0  
Release window: v0.19.5 through v0.27.0 (the 20 most recent tags at the time of writing)  
Scope: Bubba Nodes backend node definitions, execution helpers, UI results, server routes, model loading, sampling, saving, and compatibility policy

Last implementation audit: 2026-07-02

- 164 automated tests pass, including all-node schema/workflow fixtures, pipe precedence, metadata round trips, loader-state preservation, LoRA-stack order, route idempotence, and public progress.
- Ruff and JavaScript syntax checks pass for the Python tree and all 21 frontend extension files.
- The extension loads 32 native V3 nodes against the exact v0.27.0 baseline; v0.26.2 compatibility also passes and is monitored in required CI.
- Current ComfyUI `main` and its frontend package are monitored in a non-blocking early-warning CI job.
- Source audits report zero legacy node-contract references and zero unsupported internal imports outside the documented compatibility boundary.

## 1. Purpose

Bubba Nodes should use ComfyUI's supported public interfaces wherever they cover our needs, with particular emphasis on `comfy_api.latest`. The objectives are:

1. Reduce dependence on legacy node-schema conventions and private implementation details.
2. Receive current ComfyUI behavior for typed inputs, normalized outputs, UI previews, progress, node replacement, and extension registration.
3. Preserve existing Bubba workflows, socket order, node identifiers, pipe behavior, metadata, and saved-image compatibility.
4. Isolate the remaining unavoidable imports from `nodes`, `folder_paths`, `comfy.*`, and `server` so future migrations are small.
5. Validate Bubba against every new stable ComfyUI release before declaring it supported.

This is a modernization plan, not a requirement to duplicate every new core node. Bubba should continue to add pipe-aware workflow value rather than mirror ComfyUI wholesale.

## 2. Important API policy

At v0.27.0, `comfy_api.latest` declares `STABLE = False`. It is the current public development surface, but the name `latest` does not promise source stability between releases. Conversely, `comfy_api.v0_0_2` is a versioned adapter and is the safer choice for integrations that need a frozen contract.

Our policy will therefore be:

- Use `comfy_api.latest` directly for node schemas, standard I/O types, `NodeOutput`, UI outputs, extension registration, progress, and public input implementations.
- Pin and test a minimum supported ComfyUI version whenever we adopt a newly introduced `latest` feature.
- Keep all uses of unversioned internals behind small Bubba compatibility adapters.
- Do not import underscored modules such as `comfy_api.latest._io` or `_ui`; import only exports from `comfy_api.latest`.
- Do not assume a symbol exists merely because it appears on ComfyUI `master`; verify it against the minimum supported release.
- Consider a versioned API import only if `latest` breaks a feature we must support across several ComfyUI versions. Record that exception in this document.

The practical protection against deprecation is not the word `latest`; it is staying on the public surface, testing the supported release range, and keeping private dependencies isolated.

## 3. Current-state inventory

### 3.1 Public API already in use

`BubbaSaveImage` imports `UI` from `comfy_api.latest` and uses:

- `UI.PreviewImage`
- `UI.ImageSaveHelper.get_save_images_ui`

The native implementation returns these public UI results through `IO.NodeOutput` and passes the concrete V3 node class so hidden prompt/PNG information remains available.

### 3.2 Legacy or internal dependencies

| Dependency | Current consumers | Public replacement now? | Design disposition |
|---|---|---:|---|
| Legacy `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION` node schema | Removed | Yes: `IO.ComfyNode`, `IO.Schema`, typed inputs/outputs | All nodes are native V3 |
| `NODE_CLASS_MAPPINGS` registration | Removed | Yes: `ComfyExtension.get_node_list()` | Native extension registration preserves class IDs |
| Custom UI dictionaries | Image Compare and custom frontend status payloads | No stock UI type for these contracts | Return through `IO.NodeOutput`; retain only where required by custom JS |
| `comfy.utils.ProgressBar` or implicit long-task progress | upscalers/detailer | Yes: `ComfyAPISync.execution.set_progress()` | Adopt for long loops and optional previews |
| `nodes.CheckpointLoaderSimple`, `VAELoader`, `CLIPLoader`, `LoraLoader`, `common_ksampler` | loaders, LoRA nodes, samplers/detailer | No complete public execution-service replacement | Put behind `compat/core_nodes.py`; continue delegating to core |
| `folder_paths` | model lists and path resolution | No equivalent in `comfy_api.latest` | Put behind `compat/paths.py` |
| `comfy.samplers`, `comfy.utils` | samplers and upscalers | No complete public equivalent | Put behind focused adapters; never spread new direct imports |
| `comfy_extras.nodes_upscale_model` | ESRGAN/spandrel upscalers | No public execution-service equivalent | Keep loader/execution delegation in `compat/core_nodes.py` |
| `node_helpers.pillow`, `comfy.model_management` | image loading and intermediate dtype/device | No complete public equivalent | Keep runtime alignment in `compat/runtime.py` |
| `server.PromptServer` | autocomplete, checkpoint preview, Discord routes | No route API in `comfy_api.latest` | Put behind `compat/routes.py`; lazy import at registration time |

### 3.3 Public API adoption status

- All nodes use `IO.ComfyNode`, `IO.Schema`, typed public inputs/outputs, `IO.Custom(...)`, and `IO.NodeOutput`.
- Package registration uses `ComfyExtension`.
- Detailer and Tiled Diffusion use `ComfyAPISync.execution.set_progress()`.
- Save/preview/text results use `UI.ImageSaveHelper`, `UI.PreviewImage`, and `UI.PreviewText` where their frontend contracts fit.
- `UI.PreviewMask` is available but no current Bubba node exposes a standalone mask-preview UI.
- `ComfyAPI.node_replacement` remains reserved for a future class-ID migration; no replacement is needed while IDs remain unchanged.

External cache providers are deliberately out of scope. Bubba does not operate a distributed cache, and registering one would add complexity without improving ordinary workflows.

## 4. Findings from the last 20 releases

The audited tags are v0.27.0, v0.26.2, v0.26.1, v0.26.0, v0.25.1, v0.25.0, v0.24.1, v0.24.0, v0.23.0, v0.22.3, v0.22.2, v0.22.1, v0.22.0, v0.21.1, v0.21.0, v0.20.3, v0.20.2, v0.20.1, v0.20.0, and v0.19.5.

Patch releases mostly backported subsets of their following minor release, so the table identifies the Bubba-relevant capability rather than repeating partner-node changes.

| Release(s) | Relevant upstream change | Bubba consequence |
|---|---|---|
| v0.27.0 | Native INT8/ConvRot, faster and corrected INT8 LoRAs, Turing support, Seed node, Conditioning Multiply, asset hashing opt-in | Inherited through core loaders; add compatibility tests. Do not rely on asset hashes being present. Consider pipe-aware conditioning and connectable seed features. |
| v0.26.0–v0.26.2 | Save nodes gained output sockets; custom-node path initialization changed; frontend 1.45.19 | Add trailing saved-path output to Bubba Save. Test startup/import without path hacks. |
| v0.25.0–v0.25.1 | Asset IDs in execution events, asset dimensions/pagination, LoRA mappings, dynamic VRAM headroom, 10-bit video | Keep asset integration optional. Inherit memory/model fixes. No need to add video scope merely because core supports it. |
| v0.24.0–v0.24.1 | Mostly model, dtype, preview, and partner-node fixes | No direct implementation requirement; keep runtime smoke coverage. |
| v0.23.0 | V3 conversion of core nodes, multithreaded model loading/disk offload, Save Image Advanced, asset hashes, LoRA reshape fix, consolidated warnings | V3 is production-used upstream and should be Bubba's target schema. Drop the proposed custom checkpoint cache. Study Advanced Save options. |
| v0.22.0–v0.22.3 | Dynamic CLIP saving, batch input relaxations, upload-mask endpoint deprecation, node metadata/category cleanup | Test CLIP/model pass-through. Avoid deprecated mask-upload assumptions. Add richer V3 schema metadata. |
| v0.21.0–v0.21.1 | Node replacement idempotence, async LoRA loading, dynamic combo/autogrow examples, FP8 and Anima TE LoRA fixes, high-quality latent previews | Preserve node IDs; use replacement API only when needed. Let core own LoRA loading. V3 combo inputs can replace hand-built schema dictionaries. |
| v0.20.0–v0.20.3 | OpenAPI 3.1, execution cycle validation, improved media loading and alpha handling, intermediate dtype adoption | No direct OpenAPI client needed. Ensure custom pipe graphs validate without cycles and do not mutate incoming image/mask/latent values. |
| v0.19.5 | Primarily API/partner model and resolution updates | No Bubba-specific work. |

Sources: [v0.27.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.27.0), [v0.26.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.26.0), [v0.25.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.25.0), [v0.24.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.24.0), [v0.23.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.23.0), [v0.22.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.22.0), [v0.21.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.21.0), and [v0.20.0 release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.20.0).

## 5. Target architecture

### 5.1 V3 node definitions

New nodes should be V3 nodes by default. Existing nodes should migrate without changing their registered class ID, display name, input names, socket order, or output order.

Conceptual shape:

```python
from comfy_api.latest import IO

BUBBA_PIPE = IO.Custom("BUBBA_PIPE")
BUBBA_METADATA = IO.Custom("BUBBA_METADATA")


class BubbaExample(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="BubbaExample",
            display_name="Bubba Example",
            category="Bubba Nodes/Workflow",
            inputs=[
                BUBBA_PIPE.Input("pipe", optional=True),
                IO.Image.Input("image", optional=True),
            ],
            outputs=[
                BUBBA_PIPE.Output("pipe"),
                IO.Image.Output("image"),
            ],
        )

    @classmethod
    def execute(cls, pipe=None, image=None) -> IO.NodeOutput:
        return IO.NodeOutput(updated_pipe, resolved_image)
```

The actual migration must follow the v0.27 signatures and validation behavior. This sample establishes intent rather than serving as a copy-paste patch.

### 5.2 Extension registration

The package exposes a `ComfyExtension` whose `get_node_list()` returns the native V3 node classes directly. Existing serialized node class IDs continue to resolve to the same behavior without a parallel legacy registry.

We should not rename IDs to make Python class names prettier. If an ID ever must change, register an explicit public `NodeReplace` mapping and test old workflow loading.

### 5.3 Compatibility boundary

Create a small `src/bubba_nodes/compat/` package:

- `core_nodes.py`: checkpoint, VAE, CLIP, LoRA, upscale-model, and common sampler delegation
- `paths.py`: filename lists, annotated files, input/output/temp directories, and secure resolution
- `sampling.py`: sampler names, scheduler names, and sampling helpers
- `routes.py`: lazy `PromptServer` access and idempotent route registration
- `checkpoint_io.py`: checkpoint state-dict loading/saving and live checkpoint object reconstruction via ComfyUI internals that have no public V3 execution-service replacement
- `runtime.py`: `node_helpers.pillow` and `comfy.model_management` image-load dtype/device helpers that keep image loading aligned with ComfyUI runtime behavior

No schema/execution adapter is used. Each node module owns its public `IO.Schema` and native `execute` implementation.

Application nodes import these adapters, not ComfyUI internals directly. Adapters should be thin and separately tested; they must not become an alternate ComfyUI abstraction framework.

### 5.4 Standard UI outputs

Use public UI classes whenever the frontend contract is standard:

- Save and preview image: `UI.ImageSaveHelper`, `UI.PreviewImage`
- Mask preview: `UI.PreviewMask`
- Text display: `UI.PreviewText`

Return them through `IO.NodeOutput(..., ui=...)` in V3 nodes. Avoid `.as_dict()` unless compatibility with a custom frontend extension requires a raw payload.

Image Compare may continue using its custom `b64_a`/`b64_b` payload because its interactive slider is not represented by a stock `UI` class. That exception should be documented next to the node and covered by a frontend contract test.

### 5.5 Progress reporting

Detailing and tiled diffusion can run long enough to require public progress reporting. Use `ComfyAPISync.execution.set_progress(value, max_value, preview_image=...)` at coarse boundaries:

- one update per detected region in Detailer
- one update per completed tile in Tiled Diffusion Upscaler
- optional first-image preview no more frequently than needed

Do not emit progress for trivial tensor operations. Progress reporting must not change deterministic results or force tensors onto a different device merely to produce previews.

### 5.6 Core loaders and quantized models

Continue delegating actual model loading and LoRA application to ComfyUI. Do not copy quantization, patching, offload, cache, or async-loading logic into Bubba.

Tests should prove that Bubba:

- preserves patched/quantized model identity or documented clone semantics
- does not rebuild model options
- writes explicit overrides back into `BUBBA_PIPE`
- maintains CLIP and VAE references
- applies stacked LoRAs in order
- accepts loader objects carrying FP8, INT8/ConvRot, offload, and async-loading state

These can mostly be protocol-style fakes; at least one optional runtime smoke workflow should use a real supported quantized model when CI resources allow it.

### 5.7 Save and asset outputs

Append save results after existing outputs to preserve compatibility:

```text
pipe, metadata, saved_paths, info
```

`saved_paths` should be a deterministic newline-delimited string unless a public path-list type becomes available. `info` should summarize preview-only behavior and metadata warnings.

Asset IDs are useful but should not become part of `BubbaMetadata` yet. Their API changed several times in the audited window, and asset hashing is disabled by default in v0.27. Bubba's own checkpoint hash generation must remain independent and lazy.

## 6. Migration plan

### Phase 0: Compatibility contract and CI

1. Declare v0.27.0 as the initial V3 migration baseline.
2. Add a startup/import smoke test inside a real ComfyUI checkout.
3. Capture every current node ID, display name, category, ordered input schema, and ordered output schema as a golden compatibility fixture.
4. Add a test that forbids imports from underscored `comfy_api` modules.
5. Add a direct-import allowlist for `nodes`, `folder_paths`, `comfy.*`, and `server`; shrink it during later phases.

Exit criterion: CI detects accidental socket reordering and new private dependencies.

### Phase 1: Public output and progress APIs

1. Convert View Text and Metadata Debug to `UI.PreviewText` where the current JS does not provide additional essential behavior.
2. Refactor Save to return public UI objects through `IO.NodeOutput` once migrated.
3. Add saved-path and info outputs.
4. Adopt public progress in Detailer and Tiled Diffusion Upscaler.
5. Keep Image Compare's custom payload as an explicit exception.

Exit criterion: no ordinary preview/save/text result is manually shaped when a public UI class covers it.

### Phase 2: Compatibility adapters

1. Introduce the focused adapter modules listed in section 5.3.
2. Move existing direct imports without changing runtime behavior.
3. Remove the checkpoint-loader cache TODO; rely on upstream threaded loading and caching.
4. Add quantized-model and patched-LoRA pass-through tests.

Exit criterion: ordinary node modules no longer import `nodes`, `folder_paths`, `server`, or low-level sampling modules directly.

### Phase 3: V3 leaf nodes

Migrate stateless and low-risk nodes first:

- Filename
- View Text
- Prompt Cleaner
- Prompt Inspector
- Metadata Debug
- Empty Latent by Size
- Pipe In and Pipe Out

For each node, compare the generated schema with the golden fixture and load a saved legacy workflow.

Exit criterion: leaf-node workflows execute identically and retain socket placement.

### Phase 4: V3 image and prompt nodes

Migrate prompt builders/randomizer, image compare, watermark, overlays, load-image-with-metadata, upscalers, and Save. Preserve hidden prompt/workflow inputs needed for PNG metadata.

Exit criterion: PNG round trips preserve ComfyUI workflow data, Bubba metadata, masks, image dimensions, and A1111 parameters.

### Phase 5: V3 generation nodes

Migrate checkpoint/combo loaders, LoRA nodes, KSampler, Detailer, and merge nodes last. These sit closest to evolving ComfyUI internals and quantized/offloaded models.

Exit criterion: representative SD/SDXL/Anima or current project workflows match pre-migration deterministic output metadata and execute across supported devices.

### Phase 6: Optional workflow gains

Evaluate, independently of the API migration:

- connectable seed input compatible with core Seed while retaining the manual random button
- pipe-aware conditioning multiplication
- advanced save format/quality controls with sidecar metadata for formats that cannot carry PNG text
- optional asset ID output when ComfyUI exposes a sufficiently stable public contract

These features must not delay the public-API migration.

Implementation notes:

- Pipe-aware conditioning multiplication was added as `BubbaConditioningMultiply`.
- Seed inputs remain typed `INT` widgets with ComfyUI's `control_after_generate` behavior, which keeps them compatible with core Seed connections through the standard widget-to-input conversion path without changing legacy socket order.
- Advanced non-PNG sidecar saving and asset ID outputs remain intentionally deferred because v0.27.0 does not provide a sufficiently stable public asset contract and Bubba Save's current format scope is PNG/preview image saving.

## 7. Compatibility and testing matrix

### Required automated tests

- package import and node discovery in the minimum supported ComfyUI release
- package import and node discovery against current ComfyUI `latest`/nightly in a non-blocking early-warning job
- golden node IDs, ordered inputs, ordered outputs, categories, and display names
- old workflow JSON deserialization for every migrated node family
- explicit-input-over-pipe resolution and outgoing-pipe writeback
- deterministic prompt expansion and sampling metadata
- save/preview UI payload validation
- PNG workflow, Bubba, and A1111 metadata round trips
- path traversal and annotated-file validation
- server route registration twice without duplicate-route failure
- progress calls without executing context failures
- mocked FP8/INT8/offloaded model and LoRA pass-through
- frontend extension smoke tests against the minimum and newest frontend packages

### Release support policy

- `main` targets the newest stable ComfyUI release.
- The package declares a concrete minimum version based on the newest `comfy_api.latest` feature it uses.
- Support at least the current and immediately previous ComfyUI minor release when feasible.
- Nightly failures are warnings until the relevant change enters a stable tag, but should be triaged promptly.
- A new ComfyUI stable release triggers the checklist in section 8.

## 8. Recurring release checklist

For every ComfyUI stable release:

1. Read all release and patch notes since the last supported tag.
2. Diff `comfy_api/latest`, `comfy_api/version_list.py`, representative V3 core nodes, and loader/sampler helper signatures.
3. Search for deprecation notices affecting `nodes`, `folder_paths`, `server`, `comfy.*`, frontend hooks, routes, and UI payloads.
4. Run the full schema and workflow compatibility suite.
5. Run loader/LoRA smoke tests for newly supported quantization or model formats.
6. Verify save UI, PNG metadata, asset behavior, and output paths.
7. Verify all custom JavaScript against the bundled frontend version.
8. Update this document's baseline and exception inventory.
9. Do not add wrappers for new core nodes unless pipe integration or metadata propagation creates clear Bubba value.

## 9. Decisions and non-goals

### Decisions

- V3 `comfy_api.latest` schemas are the target for all Bubba nodes.
- Existing node IDs and socket order are compatibility requirements.
- Public UI and progress APIs should be adopted early.
- Core remains responsible for model loading, sampling, quantization, memory management, and LoRA patch mechanics.
- Private dependencies that lack public replacements will be isolated, not disguised.

### Non-goals

- Reimplementing core loaders, samplers, asset indexing, or caching
- Converting all nodes in a single risky patch
- Adding video, audio, 3D, partner API, or cloud features solely because recent ComfyUI releases added them
- Using `comfy_api.latest` underscored modules
- Treating asset hashing as universally enabled
- Breaking old workflows to obtain cleaner Python names

## 10. Completion criteria

The modernization is complete when:

- every Bubba node is registered through `ComfyExtension` and defined with V3 public schemas
- standard outputs use `IO.NodeOutput` and public `UI` classes
- long-running nodes use public progress reporting
- application node modules have no scattered imports of unsupported internals
- every remaining internal dependency is listed in the compatibility boundary with a test and rationale
- old workflows load without rewiring or socket movement
- save and metadata round trips remain intact
- CI validates the minimum supported stable release and monitors current nightly
