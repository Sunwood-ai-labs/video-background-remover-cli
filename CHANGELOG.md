# Changelog

This file is a high-level summary of the major releases for `video-background-remover`.

## 🚀 0.2.0 - 2026-03-07

This release moves the project beyond a repository-local script and turns it into a more complete CLI package with clearer installation, better documentation, stronger release automation, and basic regression coverage.

### Product and CLI

- Packaged the project for PyPI so users can install it as a standard Python tool instead of relying only on repository-local execution
- Added `video-background-remover` and `vbr` console commands for direct command-line use after installation
- Added a dedicated package entry point for `python -m video_background_remover_cli`
- Clarified package metadata, project URLs, and install guidance for local development and distribution

### Documentation and Examples

- Introduced a VitePress documentation site with English and Japanese guides
- Expanded usage guidance for getting started, model selection, examples, and CLI behavior
- Improved presentation assets including social cards, favicon assets, and metadata for GitHub Pages and link previews
- Added and published a model comparison experiment for a fire-effect sample clip, including visual outputs and rerun assets

### Quality and Release Engineering

- Added automated tests covering CLI helper behavior, execution routing, and release version synchronization
- Automated version synchronization so release tags can update tracked version files consistently
- Added GitHub Actions workflows for package publishing and GitHub Pages deployment
- Improved the release pipeline around trusted publishing and repeatable package builds

### Release Scope

- This release summarizes the substantive changes since `v0.1.0`
- Versions `v0.1.1` through `v0.1.6` were mainly used to validate deployment and release workflow changes, so they are treated as release-engineering iterations rather than separate feature milestones

## 🛠️ 0.1.1 - 0.1.6

These releases were primarily used to stabilize packaging and deployment rather than to introduce user-facing features.

### Highlights

- Validated the PyPI publishing pipeline and trusted publishing setup
- Refined release automation so repository version files stay aligned with release tags
- Improved GitHub Pages deployment and docs asset handling
- Polished documentation presentation, social cards, favicon assets, and metadata

## 🌱 0.1.0

Initial public release of the video background removal CLI.

### Highlights

- Added video background removal powered by `rembg` and `OpenCV`
- Supported full video export, transparent frame extraction, and animated WebP or GIF output
- Added background replacement with solid colors or background images
- Exposed multiple segmentation models including `isnet-general-use`, `u2net`, `u2netp`, `u2net_human_seg`, and `silueta`
- Included README-based usage examples for English and Japanese users
