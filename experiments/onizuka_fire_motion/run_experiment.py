import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "main.py").exists() and (candidate / "src" / "bg_remover.py").exists():
            return candidate
    raise RuntimeError("Could not locate repository root from script path.")


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_from_repo_root(repo_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if not path.is_absolute():
        path = repo_root / path
    return path


def run_models(
    repo_root: Path,
    output_dir: Path,
    input_video: Path,
    models: list[str],
    webp_fps: int,
) -> list[dict]:
    python_exe = Path(sys.executable)
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for model in models:
        base = output_dir / f"{model}_anim"
        webp_path = base.with_suffix(".webp")
        frames_dir = output_dir / f"{model}_anim_frames"

        if webp_path.exists():
            webp_path.unlink()
        if frames_dir.exists():
            shutil.rmtree(frames_dir)

        cmd = [
            str(python_exe),
            str(repo_root / "main.py"),
            str(input_video),
            str(base),
            "--model",
            model,
            "--animated",
            "webp",
            "--webp-fps",
            str(webp_fps),
        ]

        print(f"=== Running {model} ===")
        started = time.perf_counter()
        completed = subprocess.run(cmd, cwd=repo_root)
        elapsed = round(time.perf_counter() - started, 2)
        if completed.returncode != 0:
            raise RuntimeError(f"Model run failed: {model}")

        frame_count = len(list(frames_dir.glob("*.png")))
        results.append(
            {
                "model": model,
                "seconds": elapsed,
                "output_webp": str(webp_path),
                "webp_bytes": webp_path.stat().st_size,
                "frame_dir": str(frames_dir),
                "frame_count": frame_count,
            }
        )

    return results


def write_results_csv(output_dir: Path, rows: list[dict]) -> None:
    results_csv = output_dir / "results.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_alpha_stats(output_dir: Path, models: list[str]) -> None:
    rows = []
    for model in models:
        frame_dir = output_dir / f"{model}_anim_frames"
        alphas = []
        nonzero = []
        for frame_path in sorted(frame_dir.glob("frame_*.png")):
            alpha = Image.open(frame_path).convert("RGBA").getchannel("A")
            hist = alpha.histogram()
            total = sum(hist)
            nz = total - hist[0]
            weighted = sum(index * count for index, count in enumerate(hist))
            alphas.append(weighted / total / 255)
            nonzero.append(nz / total)

        rows.append(
            {
                "model": model,
                "avg_alpha_mean": round(sum(alphas) / len(alphas), 4),
                "avg_nonzero_alpha_ratio": round(sum(nonzero) / len(nonzero), 4),
                "min_nonzero_alpha_ratio": round(min(nonzero), 4),
                "max_nonzero_alpha_ratio": round(max(nonzero), 4),
            }
        )

    alpha_csv = output_dir / "alpha_stats.csv"
    with alpha_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_comparison_sheets(
    output_dir: Path,
    input_video: Path,
    models: list[str],
    sample_indices: list[int],
    sample_labels: list[str],
    webp_fps: int,
) -> None:
    rows = [("original", None)] + [
        (model, output_dir / f"{model}_anim_frames") for model in models
    ]

    cell_w = 180
    cell_h = 180
    label_h = 28
    row_label_w = 170
    pad = 12
    font = ImageFont.load_default()

    checker = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
    block = 16
    for y in range(cell_h):
        for x in range(cell_w):
            value = 210 if ((x // block) + (y // block)) % 2 == 0 else 245
            checker[y, x] = (value, value, value)
    checker_img = Image.fromarray(checker, "RGB")

    canvas_w = row_label_w + pad + len(sample_indices) * (cell_w + pad) + pad
    canvas_h = label_h + pad + len(rows) * (cell_h + pad) + pad
    sheet = Image.new("RGB", (canvas_w, canvas_h), "white")
    mask_sheet = Image.new("L", (canvas_w, canvas_h), 255)
    draw = ImageDraw.Draw(sheet)
    mask_draw = ImageDraw.Draw(mask_sheet)

    for col, label in enumerate(sample_labels):
        x = row_label_w + pad + col * (cell_w + pad)
        draw.text((x + 4, 6), label, fill="black", font=font)
        mask_draw.text((x + 4, 6), label, fill=0, font=font)

    cap = cv2.VideoCapture(str(input_video))
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_skip = max(1, int(source_fps / webp_fps))
    source_frames = {}
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx * frame_skip)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read source frame for sampled index {idx}")
        source_frames[idx] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cap.release()

    for row, (name, frame_dir) in enumerate(rows):
        y = label_h + pad + row * (cell_h + pad)
        draw.text((8, y + cell_h // 2 - 6), name, fill="black", font=font)
        mask_draw.text((8, y + cell_h // 2 - 6), name, fill=0, font=font)

        for col, idx in enumerate(sample_indices):
            x = row_label_w + pad + col * (cell_w + pad)
            if name == "original":
                img = Image.fromarray(source_frames[idx]).resize((cell_w, cell_h))
                alpha = None
            else:
                rgba = Image.open(frame_dir / f"frame_{idx:04d}.png").convert("RGBA")
                rgba = rgba.resize((cell_w, cell_h))
                img = checker_img.copy()
                img.paste(rgba, mask=rgba.getchannel("A"))
                alpha = rgba.getchannel("A")

            sheet.paste(img, (x, y))
            if alpha is not None:
                mask_sheet.paste(alpha.resize((cell_w, cell_h)), (x, y))
            else:
                mask_sheet.paste(
                    Image.fromarray(np.full((cell_h, cell_w), 220, dtype=np.uint8), "L"),
                    (x, y),
                )

    sheet.save(output_dir / "comparison_sheet.png")
    mask_sheet.convert("RGB").save(output_dir / "comparison_masks.png")


def main() -> int:
    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path.parent)

    parser = argparse.ArgumentParser(
        description="Run the fire-effect model comparison experiment again."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=script_path.parent / "experiment_config.json",
        help="Path to the experiment config JSON.",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Optional override for models. If omitted, models from the config are used.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    models = args.models or config["models"]
    input_video = resolve_from_repo_root(repo_root, config["input_video"])
    output_dir = resolve_from_repo_root(repo_root, config["output_dir"])
    webp_fps = int(config["webp_fps"])
    sample_indices = [int(value) for value in config["sample_indices"]]
    sample_labels = list(config["sample_labels"])

    if len(sample_indices) != len(sample_labels):
        raise RuntimeError("sample_indices and sample_labels must have the same length.")

    print(f"Repo root: {repo_root}")
    print(f"Input video: {input_video}")
    print(f"Output dir: {output_dir}")
    print(f"Models: {', '.join(models)}")

    results = run_models(
        repo_root=repo_root,
        output_dir=output_dir,
        input_video=input_video,
        models=models,
        webp_fps=webp_fps,
    )
    write_results_csv(output_dir, results)
    write_alpha_stats(output_dir, models)
    build_comparison_sheets(
        output_dir=output_dir,
        input_video=input_video,
        models=models,
        sample_indices=sample_indices,
        sample_labels=sample_labels,
        webp_fps=webp_fps,
    )

    print("Done.")
    print(f"Results CSV: {output_dir / 'results.csv'}")
    print(f"Alpha stats: {output_dir / 'alpha_stats.csv'}")
    print(f"Comparison sheet: {output_dir / 'comparison_sheet.png'}")
    print(f"Mask sheet: {output_dir / 'comparison_masks.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
