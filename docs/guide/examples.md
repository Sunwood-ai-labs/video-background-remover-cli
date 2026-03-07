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

## Experiment: Fire Effect Clip

Test clip: `assets/onizuka_fire_motion.mp4`

Settings used:

```bash
python main.py assets/onizuka_fire_motion.mp4 output/model.webp --animated webp --webp-fps 8 --model <model>
```

### Summary

- `silueta` produced the best overall balance on this clip.
- `u2net` kept the silhouette stable, but removed most of the fire aura.
- `u2net_human_seg` was not suitable for this stylized, effect-heavy sample.

### Model Previews

| Model | Preview | Runtime | Notes |
| --- | --- | ---: | --- |
| `isnet-general-use` | <img src="/experiments/onizuka_fire_motion/isnet-general-use.webp" alt="isnet-general-use result" width="180"> | 114.44s | Preserves some effect detail, but leaves halo noise around the subject. |
| `u2net` | <img src="/experiments/onizuka_fire_motion/u2net.webp" alt="u2net result" width="180"> | 76.42s | Strong silhouette stability, but most of the fire aura disappears. |
| `u2netp` | <img src="/experiments/onizuka_fire_motion/u2netp.webp" alt="u2netp result" width="180"> | 30.11s | Fastest run, but quality drops on harder fire frames. |
| `u2net_human_seg` | <img src="/experiments/onizuka_fire_motion/u2net_human_seg.webp" alt="u2net human seg result" width="180"> | 69.97s | Loses most of the character on this stylized clip. |
| `silueta` | <img src="/experiments/onizuka_fire_motion/silueta.webp" alt="silueta result" width="180"> | 69.27s | Best balance of shape retention and cleanup in this comparison. |

### Visual Comparison Sheet

![Comparison sheet](/experiments/onizuka_fire_motion/comparison_sheet.png)

Representative frames sampled at 1.0s, 3.0s, 5.0s, 7.0s, and 9.0s. This makes it easier to spot where the aura survives and where the subject breaks apart.

### Mask Comparison Sheet

![Mask comparison](/experiments/onizuka_fire_motion/comparison_masks.png)

The alpha-mask view is useful for checking subject coverage. `u2net_human_seg` collapses on this clip, while `silueta`, `u2net`, and `isnet-general-use` keep a far more complete silhouette.

### Re-run the Experiment

The tracked experiment definition is stored under `experiments/onizuka_fire_motion/`.

- Script: `experiments/onizuka_fire_motion/run_experiment.py`
- Config: `experiments/onizuka_fire_motion/experiment_config.json`
- Notes: `experiments/onizuka_fire_motion/README.md`
- Output directory: `output/model_experiments/onizuka_fire_motion/`

Run it from the repository root:

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

Export a GIF. GIF does not support partial transparency.

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
