# Changelog

This file is a high-level summary of the major releases for `video-background-remover`.

## 0.2.0 - 2026-03-07

This release turns the project from a repository-first utility into a packaged CLI with clearer distribution and documentation.

### Highlights

- Packaged the project for PyPI with `video-background-remover` and `vbr` console commands
- Added a dedicated package entry point for `python -m video_background_remover_cli`
- Expanded project metadata for distribution, installation, and repository links
- Added automated tests for CLI behavior and release version synchronization
- Introduced a VitePress documentation site with English and Japanese guides
- Added model comparison assets and rerun scripts for the fire-effect sample experiment
- Automated version synchronization, package publishing, and GitHub Pages deployment

## 0.1.1 - 0.1.6

These releases were primarily used to stabilize packaging and deployment rather than to introduce user-facing features.

### Highlights

- Validated the PyPI publishing pipeline and trusted publishing setup
- Refined release automation so repository version files stay aligned with release tags
- Improved GitHub Pages deployment and docs asset handling
- Polished documentation presentation, social cards, favicon assets, and metadata

## 0.1.0

Initial public release of the video background removal CLI.

### Highlights

- Added video background removal powered by `rembg` and `OpenCV`
- Supported full video export, transparent frame extraction, and animated WebP or GIF output
- Added background replacement with solid colors or background images
- Exposed multiple segmentation models including `isnet-general-use`, `u2net`, `u2netp`, `u2net_human_seg`, and `silueta`
- Included README-based usage examples for English and Japanese users
