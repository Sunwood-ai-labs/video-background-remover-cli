# Getting Started

## Requirements

- Python 3.10 or later
- FFmpeg is **not** required
- The AI model is downloaded automatically on first run

## Installation

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

## Basic Usage

```bash
python main.py INPUT OUTPUT [options]
```

| Argument | Description |
| --- | --- |
| `INPUT` | Path to the input video file |
| `OUTPUT` | Path to the output file or directory |

For the full list of options, see the [Usage](./usage) page.
