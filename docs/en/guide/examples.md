# Examples

## Output Examples

| Type | File |
| --- | --- |
| Input video | `assets/onizuka_idle_motion.mp4` |
| Animated WebP | `example/output_animated.webp` |
| GIF | `output/output.gif` |
| Comparison GIF | `example/onizuka_walk_motion.gif` |
| Comparison WebP | `example/onizuka_walk_motion.webp` |
| Transparent frames | `output_frames_webp/` |

## Recipe: White Background Video

Remove the background and fill it with white:

```bash
python main.py input.mp4 output_white.mp4 --bg-color white
```

## Recipe: Custom Background Image

Composite the subject onto a custom background:

```bash
python main.py input.mp4 output_bg.mp4 --bg-image background.jpg
```

## Recipe: Transparent Animated WebP

Export a looping animated WebP with transparency at 10 FPS:

```bash
python main.py input.mp4 output_animated.webp --animated webp --webp-fps 10
```

## Recipe: Animated GIF

Export a GIF (note: GIF does not support partial transparency):

```bash
python main.py input.mp4 output.gif --animated gif --webp-fps 8
```

## Recipe: Both WebP and GIF

Export both formats at once from the same run:

```bash
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

## Recipe: Frame Extraction

Extract transparent PNG frames every 0.5 seconds:

```bash
python main.py input.mp4 output/frames --interval 0.5 --format png
```

Extract transparent WebP frames every second:

```bash
python main.py input.mp4 output/frames --interval 1 --format webp
```

## Recipe: Specify Model

Use the human segmentation model for better results on people:

```bash
python main.py input.mp4 output.mp4 --model u2net_human_seg --bg-color white
```

## Notes

- The initial model load can take some time.
- Long videos exported as `--animated gif` can become large files.
- If you need transparency, prefer `--animated webp` or `--interval` output instead of regular video export.
