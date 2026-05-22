# Remediation Plan

Goal: improve production readiness without rewriting the project, while preserving existing workflows wherever possible.

## Recommended Cleanup Roadmap

### Phase 1: Stop the realistic crashers

1. Fix RGB mask sizing in Load Image.
   - Complexity: Low
   - Risk level: Low
   - Suggested order: 1
   - Files/modules affected: `src/bubba_nodes/nodes/load_image_with_metadata.py`, `tests/test_bubba_nodes.py`
   - Breaking change: No
   - Tests: Yes, add RGB and RGBA image tests that assert mask dimensions match image dimensions.

2. Ensure image files are closed after loading.
   - Complexity: Low
   - Risk level: Low
   - Suggested order: 2
   - Files/modules affected: `src/bubba_nodes/nodes/load_image_with_metadata.py`
   - Breaking change: No
   - Tests: Yes, add a Windows-friendly test that reloads or deletes the image after node execution.

3. Add safe relative save-prefix sanitation.
   - Complexity: Medium
   - Risk level: Medium
   - Suggested order: 3
   - Files/modules affected: `src/bubba_nodes/nodes/filename.py`, `src/bubba_nodes/nodes/save_image.py`, new `src/bubba_nodes/utils/paths.py`
   - Breaking change: Mostly no. Some previously accepted unsafe names should be normalized.
   - Tests: Yes, add tests for a shared `sanitize_relative_save_prefix` helper covering `..`, absolute paths, drive letters, UNC paths, reserved Windows names, trailing dots/spaces, and normal names.

4. Rename metadata `filepath` to `save_prefix` with migration.
   - Complexity: Low to Medium
   - Risk level: Medium
   - Suggested order: 4
   - Files/modules affected: `src/bubba_nodes/models/metadata.py`, `src/bubba_nodes/nodes/filename.py`, `src/bubba_nodes/nodes/save_image.py`, `src/bubba_nodes/nodes/load_image_with_metadata.py`, `README.md`, `web/docs/Example/en.md`, tests
   - Breaking change: No if old `filepath` is still accepted from saved PNG metadata and old workflows.
   - Tests: Yes, add metadata coercion tests that load old `{"filepath": "Character/Scene"}` payloads and emit `save_prefix`.

5. Normalize mojibake and enforce UTF-8.
   - Complexity: Low
   - Risk level: Low
   - Suggested order: 5
   - Files/modules affected: `README.md`, affected Python descriptions, affected JS labels/CSS glyphs
   - Breaking change: No
   - Tests: Yes, add a lightweight script or test that scans for common mojibake sequences.

### Phase 2: Make startup resilient

6. Introduce isolated node registration.
   - Complexity: Medium
   - Risk level: Medium
   - Suggested order: 6
   - Files/modules affected: `__init__.py`, `src/bubba_nodes/nodes/__init__.py`, possibly new `src/bubba_nodes/registration.py`
   - Breaking change: No, node class names and display names must remain unchanged.
   - Tests: Yes, add import smoke tests where one node module intentionally fails and unrelated nodes still register.

7. Add a ComfyUI compatibility helper.
   - Complexity: Medium
   - Risk level: Medium
   - Suggested order: 7
   - Files/modules affected: new `src/bubba_nodes/comfy_compat.py`, model/loader/sampler/upscaler/save nodes
   - Breaking change: No
   - Tests: Yes, mock current and older ComfyUI API shapes.

8. Clarify optional dependencies and detailer availability.
   - Complexity: Low to Medium
   - Risk level: Low
   - Suggested order: 8
   - Files/modules affected: `requirements.txt`, `pyproject.toml`, `README.md`, `src/bubba_nodes/utils/detailer_models.py`, `src/bubba_nodes/nodes/detailer.py`
   - Breaking change: No if handled as optional; possible install impact if made core.
   - Tests: Yes, test missing `ultralytics` error message.

9. Replace `print` warnings with a project logger.
   - Complexity: Low
   - Risk level: Low
   - Suggested order: 9
   - Files/modules affected: `__init__.py`, `src/bubba_nodes/utils/prompting.py`, `src/bubba_nodes/nodes/combo_loader.py`
   - Breaking change: No
   - Tests: Optional, but useful for warning paths.

### Phase 3: Reduce frontend maintenance risk

10. Extract a generic asset tree menu.
   - Complexity: High
   - Risk level: Medium
   - Suggested order: 10
   - Files/modules affected: `web/comfyui/checkpoint_menu.js`, `web/comfyui/lora_menu.js`, `web/comfyui/menu_shared.js`, new `web/comfyui/asset_tree_menu.js`
   - Breaking change: No, UI behavior should remain equivalent.
   - Tests: Yes, add pure helper tests for path splitting, quick sections, recents/favorites, and URL generation.

11. Move frontend styles into dedicated style modules.
   - Complexity: Medium
   - Risk level: Low
    - Suggested order: 11
    - Files/modules affected: `web/comfyui/autocomplete/ui.js`, menu modules, settings module, new CSS/style files
    - Breaking change: No
    - Tests: Manual visual smoke test plus frontend helper tests.

12. Unify prompt conflict rules.
   - Complexity: Medium
   - Risk level: Low
    - Suggested order: 12
    - Files/modules affected: `src/bubba_nodes/utils/prompt_analysis.py`, `web/comfyui/autocomplete/ui.js`, new shared JSON data file
    - Breaking change: No, but warning output may become more consistent.
    - Tests: Yes, Python and JS should consume the same fixture.

### Phase 4: Harden performance and supportability

13. Add guardrails to Detailer.
   - Complexity: Medium
   - Risk level: Medium
    - Suggested order: 13
    - Files/modules affected: `src/bubba_nodes/nodes/detailer.py`, docs
    - Breaking change: No if defaults stay compatible; lowering max values could affect edge users.
    - Tests: Yes, test max detection clamping and info output.

14. Add LRU or clearable detector cache.
   - Complexity: Low to Medium
   - Risk level: Low
    - Suggested order: 14
    - Files/modules affected: `src/bubba_nodes/utils/detailer_models.py`
    - Breaking change: No
    - Tests: Yes, test eviction behavior with fake model loader.

15. Add CSV download size limits and unique temp files.
   - Complexity: Medium
   - Risk level: Low
    - Suggested order: 15
    - Files/modules affected: `src/bubba_nodes/server/autocomplete.py`
    - Breaking change: No unless users rely on very large custom CSV URLs.
    - Tests: Yes, simulate oversized stream and concurrent writes.

16. Improve Save Image metadata embedding.
   - Complexity: Medium
   - Risk level: Medium
    - Suggested order: 16
    - Files/modules affected: `src/bubba_nodes/nodes/save_image.py`
    - Breaking change: No
    - Tests: Yes, save/load round-trip tests with prompt/workflow metadata and Bubba metadata.

## Technical Debt Roadmap

1. Convert repeated node input definitions into small readable helpers only where it removes repetition.
   - Keep ComfyUI node declarations obvious. Do not build a clever DSL.

2. Add focused type hints to utilities and data models.
   - Start with `utils/paths.py`, `utils/detailer_models.py`, `utils/prompting.py`, and server routes.
   - Do not force strict typing onto dynamic ComfyUI node execution signatures until compatibility wrappers exist.

3. Split large frontend modules by responsibility.
   - `autocomplete/ui.js` should become smaller modules for style install, prompt assistant, snippet popover, search controller, and widget hook.
   - `settings.js` should group settings by feature and use small field-builder helpers.

4. Consolidate metadata handling.
   - Add `schema_version`.
   - Rename `filepath` to `save_prefix` because the value is a relative save prefix, not a resolved filesystem path.
   - Add migration helpers.
   - Accept legacy `filepath` from old workflows and saved PNG metadata.
   - Add explicit "empty/default metadata" semantics.

5. Remove root-level temporary notes from release packaging.
   - Move active ideas to `docs/roadmap.md`.
   - Ensure cache, egg-info, and generated review artifacts are not included in published packages unless intended.

6. Make test fixtures less dependent on global monkeypatch state.
   - Split large `tests/test_bubba_nodes.py` into node-focused test files.
   - Keep fake ComfyUI APIs in `tests/fakes/` or `tests/conftest.py`.

## Future Architecture Roadmap

1. Registration architecture
   - Create `registration.py` with a simple list of node specs.
   - Import each node independently.
   - Record unavailable nodes with clear messages.
   - Keep `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` stable.

2. Compatibility architecture
   - Create `comfy_compat.py`.
   - Wrap common APIs: folder paths, image save helper, sampler calls, loader node methods, frontend route registration.
   - Add tests for expected API shapes.

3. Optional feature architecture
   - Treat heavy features as optional groups: detailer, autocomplete sync, preview routes.
   - Each optional feature should fail gracefully and explain exactly what to install or configure.

4. Frontend architecture
   - Use one configurable asset menu for checkpoints and LoRAs.
   - Use shared storage helpers and shared style tokens.
   - Add pure JS tests for parsing/search/path helpers.

5. Metadata architecture
   - Add schema versioning.
   - Standardize on `save_prefix` for `Character/Scene` style output prefixes.
   - Keep metadata backwards-compatible for PNGs and old workflows.
   - Provide clear migration behavior when fields are added or renamed.

6. Documentation architecture
   - Keep README focused on install, quick start, and troubleshooting.
   - Move detailed node reference to `web/docs` or `docs/nodes.md`.
   - Add a `docs/troubleshooting.md` for ComfyUI Manager and Windows issues.

## Contributor Standards Guide For Future PRs

### Stability

- A new node must not be able to prevent unrelated nodes from registering.
- Optional dependencies must be imported lazily and must produce a user-readable error.
- Any ComfyUI internal API call should go through an existing compatibility helper when one exists.
- Startup should do minimal work: no model loads, no network calls, no large file parsing.

### Readability

- Prefer straightforward functions over clever abstractions.
- Keep node execution methods readable for non-expert contributors.
- Extract helpers when a method grows multiple responsibilities or repeats logic in another node.
- Use comments only where they explain non-obvious ComfyUI behavior or compatibility decisions.

### Compatibility

- Preserve node class names, display names, return types, and common input names unless a breaking change is explicitly planned.
- If an input value changes format, support old workflow values with migration or fallback parsing.
- Name metadata fields by what they represent. For example, use `save_prefix` for a relative folder/name prefix and reserve `path` or `filepath` for resolved filesystem paths.
- Test Windows-style paths and slash normalization for file/path features.

### Error Handling

- Errors shown to ComfyUI users should say what failed, why it likely failed, and how to fix it.
- Avoid swallowing exceptions silently. If degradation is intentional, log enough context for support.
- Prefer `ValueError` with clear messages for user-correctable input issues.

### Dependencies

- Do not add a dependency without documenting why it is needed.
- Heavy or specialized dependencies should be optional unless every user needs them.
- Keep version ranges conservative. Avoid unbounded major-version upgrades for fragile libraries.
- Update both `requirements.txt` and `pyproject.toml` together.

### Frontend

- Do not duplicate large UI modules for asset types. Add configuration to shared code instead.
- Use `textContent` for user-facing text unless HTML is intentionally required and sanitized.
- Add `aria-label` and state attributes for custom buttons.
- Clean up event listeners, observers, workers, timers, and DOM nodes.
- Keep CSS tokens consistent with ComfyUI theme variables.

### Tests

- Every bug fix should include a regression test unless it is purely documentation.
- New nodes should have tests for `INPUT_TYPES`, return metadata, happy path, invalid input, and missing optional dependency behavior.
- File I/O tests should cover Windows-sensitive cases: path separators, reserved names, locked files where practical.
- Frontend pure helpers should have JS tests; DOM-heavy behavior should at least have a manual smoke-test checklist.

### Documentation

- README changes should be user-oriented: install, use, troubleshoot.
- Advanced design notes belong in `docs/`.
- Any new optional dependency needs a troubleshooting entry.
- Any new node needs a short example workflow or practical usage note.

## Suggested Implementation Order Summary

1. Fix Load Image mask dimensions.
2. Close image files during Load Image.
3. Add path sanitizer and tests.
4. Rename metadata `filepath` to `save_prefix` with legacy migration.
5. Clean encoding/mojibake.
6. Implement isolated node registration.
7. Add ComfyUI compatibility helper.
8. Clarify `ultralytics` dependency and detailer messaging.
9. Replace `print` with logger.
10. Refactor asset menus.
11. Extract frontend styles.
12. Unify prompt conflict rules.
13. Add detailer guardrails.
14. Bound detector cache.
15. Harden CSV sync.
16. Improve Save Image metadata embedding.
