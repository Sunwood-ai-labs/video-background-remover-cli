# Examples

## Output Examples

| Type | File |
| --- | --- |
| Input video | `assets/onizuka_idle_motion.mp4` |
| Animated WebP | `example/output_animated.webp` |
| GIF | `output/output.gif` |
| MatAnyone WebP 2 FPS / 300 px | `output/matanyone_full_2fps_300.webp` |
| MatAnyone WebP 5 FPS / 300 px | `output/matanyone_full_5fps_300.webp` |
| MatAnyone WebP 10 FPS / 300 px | `output/matanyone_full_10fps_300.webp` |
| MatAnyone GIF 10 FPS / 300 px | `output/matanyone_full_10fps_300.gif` |
| Comparison GIF | `example/onizuka_walk_motion.gif` |
| Comparison WebP | `example/onizuka_walk_motion.webp` |
| Transparent frames | `output_frames_webp/` |

## MatAnyone Recipes

### Transparent WebP from a foreground + alpha pair

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.webp
```

### Compact preview: 5 FPS at 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_5fps_300.webp --webp-fps 5 --size 300x300
```

### Smaller preview: 2 FPS at 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_2fps_300.webp --webp-fps 2 --size 300x300
```

### Smoother preview: 10 FPS at 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.webp --webp-fps 10 --size 300x300
```

### Animated GIF at 10 FPS

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.gif --animated gif --webp-fps 10 --size 300x300
```

### Flatten to MP4 with a white background

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.mp4 --bg-color white
```

### Notes for MatAnyone inputs

- The alpha video controls which pixels stay visible: white stays, black becomes transparent.
- The exporter removes green matte contamination from semi-transparent edges before saving.
- `300x300` plus `5fps` is usually a strong quality-to-size balance for previews.

### Green Fringe Cleanup Comparison

This preview compares four MatAnyone cleanup strengths on `assets/MatAnyone_cat3`. `soft` keeps the fullest silhouette, while `strong` and `trim` suppress more visible green spill on whiskers and tails.

![MatAnyone green cleanup comparison](/media/matanyone/green-cleanup-preview.png)

The residual map below highlights edge pixels where green is still stronger than red or blue after cleanup. It helps show the remaining hotspots instead of relying only on visual inspection.

![MatAnyone residual green map](/media/matanyone/green-residual-map.png)

- When saving multiple tuning candidates, include the profile or parameter token in the filename, for example `MatAnyone_cat3_trim_sm0_gb4_rb60_as180_am120_md255.webp`.
- In the filename tokens, `sm=spill margin`, `gb=green bias`, `rb=red boost`, `as=alpha spill`, `am=alpha matte`, and `md=max drop`.

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
