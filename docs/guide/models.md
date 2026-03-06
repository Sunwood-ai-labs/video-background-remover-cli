# Models

Video Background Remover CLI supports several AI models provided by `rembg`. You can switch between them using the `--model` option.

## Available Models

| Model | Description |
| --- | --- |
| `isnet-general-use` | General-purpose default model. Recommended for most use cases. |
| `u2net` | Good for salient object extraction. |
| `u2netp` | Lightweight variant of `u2net`. Faster but slightly less accurate. |
| `u2net_human_seg` | Optimized for human / person segmentation. |
| `silueta` | Higher quality output but slower processing speed. |

## How to Use

Pass the model name with the `--model` flag:

```bash
python main.py input.mp4 output.mp4 --model u2net_human_seg
```

## Notes

- Models are downloaded automatically on first use and cached locally.
- The download may take a moment depending on your connection speed.
- `isnet-general-use` is the default and works well for most videos.
- For videos containing people, `u2net_human_seg` often produces better results.
