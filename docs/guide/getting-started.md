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
python main.py assets/onizuka_idle_motion.mp4 --bg-color white
```

### Export a transparent animated WebP

```bash
python main.py assets/onizuka_idle_motion.mp4 --animated webp --webp-fps 10
```

### Export transparent frames every second

```bash
python main.py assets/onizuka_idle_motion.mp4 --interval 1 --format webp
```

### Export an MP4 with an explicit output mode

```bash
python main.py assets/onizuka_idle_motion.mp4 --format mp4 --bg-color white
```

### Resize output to 300x300

```bash
python main.py assets/onizuka_idle_motion.mp4 --animated webp --size 300x300
```

### Convert a MatAnyone pair into a transparent WebP

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.webp
```

### Build a compact MatAnyone preview

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_5fps_300.webp --webp-fps 5 --size 300x300
```
