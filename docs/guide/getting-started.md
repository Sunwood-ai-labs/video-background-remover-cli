# Getting Started

## Requirements

- Python 3.10 or later
- FFmpeg is not required
- Models are downloaded on first use

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

### Export a video with a white background

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_white.mp4 --bg-color white
```

### Export a transparent animated WebP

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_animated.webp --animated webp --webp-fps 10
```

### Export transparent frames every second

```bash
python main.py assets/onizuka_idle_motion.mp4 output/frames --interval 1 --format webp
```
