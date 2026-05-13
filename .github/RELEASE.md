Release & Publish Instructions
=============================

Quick steps to publish a new node release to the Comfy registry.

1) Bump the package version

- Edit `pyproject.toml` and update the `version` field (example: `0.0.5` → `0.0.6`).

2) Commit and push the change

```powershell
git add pyproject.toml
git commit -m "Bump version to 0.0.6"
git push origin main
```

3) Create and push a tag (this triggers the GitHub Action that publishes the node)

```powershell
git tag -a v0.0.6 -m "Release v0.0.6"
git push origin v0.0.6
```

4) (Optional) Create a GitHub Release for release notes

Using the GitHub CLI:
```powershell
gh release create v0.0.6 --title "v0.0.6" --notes "Release notes"
```

Or draft a release in the GitHub web UI under Releases.

5) Requirements and notes

- The workflow `.github/workflows/publish_node.yml` triggers on any pushed tag (`tags: ['*']`).
- Ensure a repository secret named `REGISTRY_ACCESS_TOKEN` exists (used by the publish action).
- Keep the tag name and `pyproject.toml` `version` in sync (convention: tag `vX.Y.Z` for `version = "X.Y.Z"`).
- If you don't have `gh` on PATH immediately after install, run it directly from its install location or add it to PATH (`C:\Program Files\GitHub CLI`).

Saved here so you can re-run the same steps.
