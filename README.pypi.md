# Video Background Remover CLI

<img src="https://raw.githubusercontent.com/Sunwood-ai-labs/video-background-remover-cli/main/example/output_animated.webp" alt="Header image" width="320">

`video-background-remover` is a Python CLI package for removing video backgrounds with `rembg` and `OpenCV`.

## ✨ Features

- Export a processed video with a replacement background
- Export transparent `webp` / `png` frames at fixed intervals
- Generate transparent animated `webp` / `gif`
- Choose from `isnet-general-use`, `u2net`, `u2netp`, `u2net_human_seg`, and `silueta`

## 🛠️ Install

```bash
pip install video-background-remover
```

For isolated CLI installs:

```bash
pipx install video-background-remover
```

## 💡 Usage

```bash
video-background-remover INPUT [OUTPUT] [options]
```

If `OUTPUT` is omitted, the CLI auto-creates `./output/<input-file-name>_<timestamp>/` and saves the result there using a name derived from the input file.

Examples:

```bash
video-background-remover input.mp4 --bg-color white
video-background-remover input.mov --format mp4 --bg-color white
video-background-remover input.mp4 --size 300x300 --bg-color white
video-background-remover input.mp4 --interval 1 --format webp --size 300x300
video-background-remover input.mp4 output/frames --interval 1 --format webp
video-background-remover input.mp4 --animated webp --size 300x300
video-background-remover input.mp4 output/anim.webp --animated webp --webp-fps 10
python -m video_background_remover_cli input.mp4 output.gif --animated gif
```

## 🧪 Development

Build distributions:

```bash
python -m build
```

Upload to PyPI:

```bash
twine upload dist/*
```

Project links:

- Repository: https://github.com/sunwood-ai-labs/video-background-remover-cli
- Documentation: https://sunwood-ai-labs.github.io/video-background-remover-cli/
