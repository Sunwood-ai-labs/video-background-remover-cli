# Usage

```bash
python main.py INPUT OUTPUT [options]
```

## Full Video Export

Regular video output does not preserve alpha transparency. Use `--bg-color` or `--bg-image` to specify a visible background.

```bash
python main.py input.mp4 output.mp4 --bg-color white
python main.py input.mp4 output.mp4 --bg-image background.jpg
python main.py input.mp4 output.mp4 --fps 30
```

## Transparent Frame Export

When `--interval` is specified, `OUTPUT` is treated as a directory name instead of a file path.

```bash
python main.py input.mp4 output/frames --interval 0.5 --format webp
python main.py input.mp4 output/frames --interval 1 --format png
```

## Animated WebP / GIF Export

With `--animated both`, the tool writes both `.webp` and `.gif` using the same base name.

```bash
python main.py input.mp4 output/output_animated.webp --animated webp
python main.py input.mp4 output/output.gif --animated gif --webp-fps 8
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

## Options Reference

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
