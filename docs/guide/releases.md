# Releases

## v0.3.0

Release date: 2026-03-15

This release covers the work shipped after [v0.2.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/releases/tag/v0.2.0). It turns the Gradio app into the main product surface for the repository and expands the MatAnyone export workflow into a more complete desktop-friendly UI.

### Highlights

- Added a Gradio 6 WebUI that combines direct `rembg` export helpers with interactive MatAnyone video and image workflows.
- Added the main `MatAnyone2` video flow with animated `webp` / `gif` export, preview cards, download buttons, and better status feedback.
- Added `MP4 -> WebP/GIF` for direct animated conversion without background removal.
- Added `MatAnyone2 Tile` for 2x2 and 3x3 tiled videos, including tile splitting after matting and per-tile animated `webp` / `gif` outputs.
- Added resume helpers for Tile workflows so previously generated foreground and alpha videos can be reused from dedicated Tile output folders.
- Added English and Japanese UI switching across the Gradio app.

### Tooling and Delivery

- Refactored shared background-removal logic into reusable modules for the CLI and WebUI.
- Added MatAnyone runtime bridge helpers and package entry points so the WebUI can launch through the managed Python environment.
- Improved Windows launch stability and Gradio startup handling for the interactive app.
- Kept release version metadata synchronized in `pyproject.toml` and package fallback version code.

### Docs and Assets

- Expanded the README and the VitePress guides for the new WebUI workflows.
- Added concrete Tile workflow screenshots and sample `webp` / `gif` assets to the documentation.
- Added this release summary page so GitHub releases can point to a docs-backed explanation of what shipped.

### Validation

The following checks were run for this release:

- `uv run --extra webui python -m unittest tests.test_webui`
- `uv run python -m unittest discover -s tests`
- `uv run --extra dev python -m build`
- `npm run docs:build`

### Related Links

- [GitHub release for v0.3.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/releases/tag/v0.3.0)
- [CHANGELOG.md](https://github.com/Sunwood-ai-labs/video-background-remover-cli/blob/main/CHANGELOG.md)
