[![English](https://img.shields.io/badge/Language-English-blue.svg)](README.md)
[![Japanese](https://img.shields.io/badge/%E8%A8%80%E8%AA%9E-%E6%97%A5%E6%9C%AC%E8%AA%9E-lightgrey.svg)](README.ja.md)

# Video Background Remover

![Header image](example/output_animated.webp)

A Python CLI tool that removes backgrounds from videos using `rembg` and `OpenCV`. It supports full video export, transparent frame extraction, and animated WebP / GIF generation.

## Features

- Split a video into frames, remove the background, and rebuild it as a video
- Export transparent `webp` / `png` frames at fixed intervals
- Generate transparent animated `webp` / `gif`
- Replace the removed background with a solid color or background image
- Switch between `isnet-general-use`, `u2net`, `u2netp`, `u2net_human_seg`, and `silueta`

## Requirements

- Python 3.10 or later
- FFmpeg is not required
- The model is downloaded on first run

## Setup

### With `pip`

```bash
pip install -r requirements.txt
```

### With `uv`

```bash
uv sync
```

## Quick Start

### 1. Export a video with a white background

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_white.mp4 --bg-color white
```

### 2. Export a transparent animated WebP

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_animated.webp --animated webp --webp-fps 10
```

### 3. Export transparent frames every second

```bash
python main.py assets/onizuka_idle_motion.mp4 output/frames --interval 1 --format webp
```

## Usage

```bash
python main.py INPUT OUTPUT [options]
```

### Full video export

```bash
python main.py input.mp4 output.mp4 --bg-color white
python main.py input.mp4 output.mp4 --bg-image background.jpg
python main.py input.mp4 output.mp4 --fps 30
```

Regular video output does not preserve alpha transparency. If you want a visible background, pass `--bg-color` or `--bg-image`.

### Transparent frame export

```bash
python main.py input.mp4 output/frames --interval 0.5 --format webp
python main.py input.mp4 output/frames --interval 1 --format png
```

When `--interval` is set, `OUTPUT` is treated as a directory name instead of a file path.

### Animated WebP / GIF export

```bash
python main.py input.mp4 output/output_animated.webp --animated webp
python main.py input.mp4 output/output.gif --animated gif --webp-fps 8
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

With `--animated both`, the tool writes both `.webp` and `.gif` using the same base name.

## Options

| Option | Description |
| --- | --- |
| `--model` | Background removal model. Default: `isnet-general-use` |
| `--fps` | FPS for regular video output. Defaults to the input video's FPS |
| `--bg-color` | Background color. Supports `white`, `black`, `green`, `blue`, `red`, `gray`, `transparent`, or `255,128,0` |
| `--bg-image` | Path to a background image |
| `--keep-frames` | Keep intermediate frames instead of deleting them |
| `--work-dir` | Working directory for extracted frames |
| `--interval` | Export frames every N seconds |
| `--format` | Output format for `--interval` mode: `webp` or `png` |
| `--animated` | Animated output mode: `webp`, `gif`, or `both` |
| `--webp-fps` | FPS for animated output |
| `--max-frames` | Maximum number of frames for animated output |

## Models

| Model | Description |
| --- | --- |
| `isnet-general-use` | General-purpose default model |
| `u2net` | Good for salient object extraction |
| `u2netp` | Lightweight variant of `u2net` |
| `u2net_human_seg` | Optimized for human segmentation |
| `silueta` | Higher quality but slower |

## Output Examples

- Input video: `assets/onizuka_idle_motion.mp4`
- Animated WebP: `example/output_animated.webp`
- GIF: `output/output.gif`
- Transparent frames: `output_frames_webp/`

## Notes

- The initial model load can take some time
- Long videos exported as `--animated gif` can become large
- If you need transparency, prefer `--animated webp` or `--interval` output instead of regular video export
