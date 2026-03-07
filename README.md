<div align="center">
  <h1>Video Background Remover CLI</h1>
  <img src="https://github.com/Sunwood-ai-labs/video-background-remover-cli/blob/main/example/output_animated.webp" alt="Header image" width="320">
  <p>
    <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white" alt="OpenCV 4.x">
    <img src="https://img.shields.io/badge/rembg-Background%20Removal-0F172A" alt="rembg">
  </p>
  <p>
    <a href="README.md">
      <img src="https://img.shields.io/badge/Language-English-blue.svg" alt="English">
    </a>
    <a href="README.ja.md">
      <img src="https://img.shields.io/badge/%E8%A8%80%E8%AA%9E-%E6%97%A5%E6%9C%AC%E8%AA%9E-lightgrey.svg" alt="Japanese">
    </a>
  </p>
</div>

A Python CLI tool that removes backgrounds from videos using `rembg` and `OpenCV`. It supports full video export, transparent frame extraction, and animated WebP / GIF generation.

## ✨ Features

- Split a video into frames, remove the background, and rebuild it as a video
- Export transparent `webp` / `png` frames at fixed intervals
- Generate transparent animated `webp` / `gif`
- Replace the removed background with a solid color or background image
- Switch between `isnet-general-use`, `u2net`, `u2netp`, `u2net_human_seg`, and `silueta`

## 📋 Requirements

- Python 3.10 or later
- FFmpeg is not required
- The model is downloaded on first run

## 🛠️ Install

### From PyPI

```bash
pip install video-background-remover
```

### Local development

```bash
pip install -e ".[dev]"
```

### With `uv`

```bash
uv sync --extra dev
```

## 🚀 Quick Start

### 1. Export a video with a white background

```bash
video-background-remover assets/onizuka_idle_motion.mp4 output/output_white.mp4 --bg-color white
```

### 2. Export a transparent animated WebP

```bash
video-background-remover assets/onizuka_idle_motion.mp4 output/output_animated.webp --animated webp --webp-fps 10
```

### 3. Export transparent frames every second

```bash
video-background-remover assets/onizuka_idle_motion.mp4 output/frames --interval 1 --format webp
```

## 💡 Usage

```bash
video-background-remover INPUT OUTPUT [options]
```

If you are running directly from the repository, `python main.py ...` and `python -m video_background_remover_cli ...` still work.

### Full video export

```bash
video-background-remover input.mp4 output.mp4 --bg-color white
video-background-remover input.mp4 output.mp4 --bg-image background.jpg
video-background-remover input.mp4 output.mp4 --fps 30
```

Regular video output does not preserve alpha transparency. If you want a visible background, pass `--bg-color` or `--bg-image`.

### Transparent frame export

```bash
video-background-remover input.mp4 output/frames --interval 0.5 --format webp
video-background-remover input.mp4 output/frames --interval 1 --format png
```

When `--interval` is set, `OUTPUT` is treated as a directory name instead of a file path.

### Animated WebP / GIF export

```bash
video-background-remover input.mp4 output/output_animated.webp --animated webp
video-background-remover input.mp4 output/output.gif --animated gif --webp-fps 8
video-background-remover input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

With `--animated both`, the tool writes both `.webp` and `.gif` using the same base name.

## ⚙️ Options

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

## 🧠 Models

| Model | Description |
| --- | --- |
| `isnet-general-use` | General-purpose default model |
| `u2net` | Good for salient object extraction |
| `u2netp` | Lightweight variant of `u2net` |
| `u2net_human_seg` | Optimized for human segmentation |
| `silueta` | Higher quality but slower |

## 🔥 Fire Effect Comparison

Test clip: `assets/onizuka_fire_motion.mp4`

Test settings:

```bash
video-background-remover assets/onizuka_fire_motion.mp4 output/model.webp --animated webp --webp-fps 8 --model <model>
```

| Model | Preview | Notes |
| --- | --- | --- |
| `isnet-general-use` | <img src="example/onizuka_fire_motion_isnet-general-use.webp" alt="isnet-general-use preview" width="180"> | Keeps some effect detail, but halo noise remains around the subject |
| `u2net` | <img src="example/onizuka_fire_motion_u2net.webp" alt="u2net preview" width="180"> | Stable silhouette, but removes most of the fire aura |
| `u2netp` | <img src="example/onizuka_fire_motion_u2netp.webp" alt="u2netp preview" width="180"> | Fastest, but quality drops on complex fire frames |
| `u2net_human_seg` | <img src="example/onizuka_fire_motion_u2net_human_seg.webp" alt="u2net_human_seg preview" width="180"> | Not suitable for this effect-heavy clip |
| `silueta` | <img src="example/onizuka_fire_motion_silueta.webp" alt="silueta preview" width="180"> | Best overall balance for this sample |

### Experiment Summary

- `silueta` gave the best overall balance on this clip.
- `u2net` was the cleanest fallback when you prefer a stable silhouette.
- `u2net_human_seg` was not suitable for this stylized, effect-heavy sample.

### Visual Comparison

![Comparison sheet](example/onizuka_fire_motion_comparison_sheet.png)

![Mask comparison](example/onizuka_fire_motion_comparison_masks.png)

### Re-run This Experiment

The tracked experiment definition lives in `experiments/onizuka_fire_motion/`.

- Script: `experiments/onizuka_fire_motion/run_experiment.py`
- Config: `experiments/onizuka_fire_motion/experiment_config.json`
- Notes: `experiments/onizuka_fire_motion/README.md`
- Generated files: `output/model_experiments/onizuka_fire_motion/`

Run it again from the repository root:

```bash
python experiments/onizuka_fire_motion/run_experiment.py
```

To test an additional model later, add it to the `models` array in `experiments/onizuka_fire_motion/experiment_config.json` and run the same command again.

The script regenerates:

- `<model>_anim.webp`
- `<model>_anim_frames/`
- `results.csv`
- `alpha_stats.csv`
- `comparison_sheet.png`
- `comparison_masks.png`

## 🖼️ Output Examples

- Input video: `assets/onizuka_idle_motion.mp4`
- Animated WebP: `example/output_animated.webp`
- GIF: `output/output.gif`
- Comparison GIF: `example/onizuka_walk_motion.gif`
- Comparison WebP: `example/onizuka_walk_motion.webp`
- Transparent frames: `output_frames_webp/`

### GIF / WebP Comparison

| GIF | WebP |
| --- | --- |
| ![GIF comparison](example/onizuka_walk_motion.gif) | ![WebP comparison](example/onizuka_walk_motion.webp) |

## 📝 Notes

- The initial model load can take some time
- Long videos exported as `--animated gif` can become large
- If you need transparency, prefer `--animated webp` or `--interval` output instead of regular video export

## 🎨 Documentation Color Map

<p>
  <img src="https://img.shields.io/badge/Base_BG-%23F2EFEB-F2EFEB?style=flat-square" alt="Base BG #F2EFEB">
  <img src="https://img.shields.io/badge/Accent_1-%23F22233-F22233?style=flat-square" alt="Accent 1 #F22233">
  <img src="https://img.shields.io/badge/Accent_2-%23F28705-F28705?style=flat-square" alt="Accent 2 #F28705">
  <img src="https://img.shields.io/badge/Accent_3-%23F25D27-F25D27?style=flat-square" alt="Accent 3 #F25D27">
  <img src="https://img.shields.io/badge/Accent_4-%23F20505-F20505?style=flat-square" alt="Accent 4 #F20505">
</p>

## 🧪 Docs Development

- The social card image is published at `docs/public/ogp.jpg`.
- Social card metadata is configured in `docs/.vitepress/config.ts`.
- To verify the current card after a docs change or deployment, open `https://www.opengraphs.com/tools/og-debugger` and test `https://sunwood-ai-labs.github.io/video-background-remover-cli/`.
