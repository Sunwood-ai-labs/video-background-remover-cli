"""Command-line interface for video background removal."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
import sys
import tempfile

from .matanyone_bridge import (
    MATANYONE_DEVICE_CHOICES,
    MATANYONE_MODEL_CHOICES,
    MATANYONE_PROFILE_CHOICES,
    MATANYONE_SAM_MODEL_CHOICES,
    MatAnyoneRunner,
    resolve_matanyone_python,
    resolve_matanyone_root,
)


MODEL_CHOICES = [
    "isnet-general-use",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
]
BACKEND_CHOICES = ["rembg", "matanyone"]
MATANYONE_STEM_SUFFIXES = ("_fg", "_alpha")
DEFAULT_OUTPUT_DIR = Path("output")
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def parse_color(color_str: str) -> tuple[int, int, int] | None:
    """Parse a background color string into an RGB tuple."""
    colors: dict[str, tuple[int, int, int] | None] = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "red": (255, 0, 0),
        "gray": (128, 128, 128),
        "transparent": None,
    }

    normalized = color_str.lower()
    if normalized in colors:
        return colors[normalized]

    try:
        values = tuple(int(value.strip()) for value in normalized.split(","))
    except ValueError as exc:
        raise ValueError(
            f"Invalid color: {color_str}. Use a color name or RGB values like '255,128,0'."
        ) from exc

    if len(values) != 3 or any(value < 0 or value > 255 for value in values):
        raise ValueError(
            f"Invalid color: {color_str}. Use a color name or RGB values like '255,128,0'."
        )

    return values


def parse_size(size_str: str) -> tuple[int, int]:
    """Parse a size string like 300x300 into a width/height tuple."""
    normalized = size_str.lower().replace(" ", "")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid size: {size_str}. Use WIDTHxHEIGHT like '300x300'."
        )

    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(
            f"Invalid size: {size_str}. Use WIDTHxHEIGHT like '300x300'."
        ) from exc

    if width <= 0 or height <= 0:
        raise ValueError(
            f"Invalid size: {size_str}. Width and height must be positive integers."
        )

    return width, height


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-background-remover",
        description=(
            "Remove video backgrounds with rembg and OpenCV. "
            "Supports full video export, transparent frame export, animated WebP / GIF, "
            "and MatAnyone foreground+alpha pair conversion."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  video-background-remover input.mp4 --size 300x300 --bg-color green\n"
            "  video-background-remover input.mov --format mp4 --bg-color green\n"
            "  video-background-remover input.mp4 output.mp4 --bg-color green\n"
            "  video-background-remover input.mp4 output/frames --interval 1 --format webp\n"
            "  video-background-remover input.mp4 output/anim.webp --animated webp --webp-fps 10\n"
            "  video-background-remover input.mp4 output/anim.webp --animated both --no-bg-removal --corner-radius 32\n"
            "  video-background-remover assets/MatAnyone --matanyone output/clip.webp"
        ),
    )
    parser.add_argument("input", help="Input video file path")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help=(
            "Output video path, output file path, or output directory depending on mode "
            "(default: auto-save under ./output/<input-name>_<timestamp>)"
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default="isnet-general-use",
        choices=MODEL_CHOICES,
        help="rembg background removal model (default: isnet-general-use)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="rembg",
        choices=BACKEND_CHOICES,
        help="Inference backend for regular inputs: rembg or matanyone (default: rembg)",
    )
    parser.add_argument(
        "--matanyone",
        action="store_true",
        help=(
            "Treat INPUT as a MatAnyone foreground video or directory containing "
            "a *_fg.* and matching *_alpha.* video pair"
        ),
    )
    parser.add_argument(
        "--alpha-video",
        type=str,
        default=None,
        help="Explicit alpha/mask video path for --matanyone mode",
    )
    parser.add_argument(
        "--matanyone-root",
        type=str,
        default=None,
        help="Optional fallback path to a local MatAnyone checkout used only to discover its .venv",
    )
    parser.add_argument(
        "--matanyone-python",
        type=str,
        default=None,
        help="Python executable where matanyone2-runtime is installed",
    )
    parser.add_argument(
        "--matanyone-model",
        type=str,
        default="MatAnyone 2",
        choices=MATANYONE_MODEL_CHOICES,
        help="MatAnyone package model used when --backend matanyone is selected",
    )
    parser.add_argument(
        "--matanyone-device",
        type=str,
        default="auto",
        choices=MATANYONE_DEVICE_CHOICES,
        help="Device for MatAnyone backend: auto, cpu, or cuda (default: auto)",
    )
    parser.add_argument(
        "--matanyone-performance-profile",
        type=str,
        default="auto",
        choices=MATANYONE_PROFILE_CHOICES,
        help="MatAnyone performance profile (default: auto)",
    )
    parser.add_argument(
        "--matanyone-sam-model-type",
        type=str,
        default="auto",
        choices=MATANYONE_SAM_MODEL_CHOICES,
        help="SAM checkpoint type for MatAnyone backend (default: auto)",
    )
    parser.add_argument(
        "--matanyone-cpu-threads",
        type=int,
        default=None,
        help="Optional CPU thread count forwarded to the MatAnyone backend",
    )
    parser.add_argument(
        "--matanyone-frame-limit",
        type=int,
        default=None,
        help="Optional MatAnyone frame cap for loading long videos",
    )
    parser.add_argument(
        "--matanyone-video-target-fps",
        type=float,
        default=0.0,
        help="MatAnyone video sampling FPS. Use 0 to keep all frames (default: 0)",
    )
    parser.add_argument(
        "--matanyone-output-fps",
        type=float,
        default=None,
        help="Optional output FPS override passed to MatAnyone",
    )
    parser.add_argument(
        "--matanyone-select-frame",
        type=int,
        default=0,
        help="Frame index used for the initial MatAnyone prompt point (default: 0)",
    )
    parser.add_argument(
        "--matanyone-end-frame",
        type=int,
        default=None,
        help="Optional exclusive end frame forwarded to MatAnyone",
    )
    parser.add_argument(
        "--positive-point",
        action="append",
        default=[],
        help='Positive prompt point for MatAnyone in "x,y" format. Repeat to add more points.',
    )
    parser.add_argument(
        "--negative-point",
        action="append",
        default=[],
        help='Negative prompt point for MatAnyone in "x,y" format. Repeat to add more points.',
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Output FPS for regular video output (default: same as input)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        help="Background color: white, black, green, blue, red, gray, transparent, or 255,128,0",
    )
    parser.add_argument("--bg-image", type=str, help="Path to background image")
    parser.add_argument(
        "--size",
        type=str,
        default=None,
        help="Output size as WIDTHxHEIGHT, for example 300x300",
    )
    parser.add_argument(
        "--keep-frames",
        action="store_true",
        help="Keep intermediate frame images",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default=None,
        help="Working directory for temporary frames",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Extract frames at a fixed interval in seconds; output becomes a directory",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="webp",
        choices=["mp4", "webp", "png"],
        help=(
            "Output format hint. Use webp/png for transparent frame or MatAnyone WebP output, "
            "or mp4 for regular video export (default: webp)"
        ),
    )
    parser.add_argument(
        "--animated",
        type=str,
        nargs="?",
        const="webp",
        choices=["webp", "gif", "both"],
        default=None,
        help="Output as animated webp, gif, or both",
    )
    parser.add_argument(
        "--webp-fps",
        type=int,
        default=10,
        help="FPS for animated output (default: 10)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames for animated output",
    )
    parser.add_argument(
        "--bounce",
        action="store_true",
        help=(
            "Create a ping-pong (bounce) loop by adding reversed frames at the end. "
            "This creates a seamless loop animation."
        ),
    )
    parser.add_argument(
        "--no-bg-removal",
        action="store_true",
        help=(
            "Skip rembg inference and keep the original video content. "
            "Useful for plain GIF/WebP conversion or transparent rounded-corner exports."
        ),
    )
    parser.add_argument(
        "--corner-radius",
        type=int,
        default=0,
        help=(
            "Rounded corner radius in output pixels. "
            "The area outside the rounded rectangle becomes transparent for WebP/GIF/PNG outputs."
        ),
    )
    return parser


def _normalize_animated_output(output: str) -> str:
    """Drop a supported animated suffix without using rstrip semantics."""
    output_path = Path(output)
    if output_path.suffix.lower() in {".webp", ".gif"}:
        return str(output_path.with_suffix(""))
    return str(output_path)


def _looks_like_directory(path_str: str) -> bool:
    """Detect whether a user-supplied path should be treated as a directory."""
    return path_str.endswith(("/", "\\")) or (
        Path(path_str).exists() and Path(path_str).is_dir()
    )


def _default_output_name(
    input_path: str,
    *,
    animated: str | None = None,
    interval: float | None = None,
    output_format: str | None = None,
    source_mode: str = "rembg",
) -> str:
    """Build a default output name from the input file and mode."""
    input_file = Path(input_path)
    input_stem = input_file.stem
    if source_mode == "matanyone":
        for suffix in MATANYONE_STEM_SUFFIXES:
            if input_stem.endswith(suffix):
                input_stem = input_stem[: -len(suffix)]
                break

        if animated:
            return f"{input_stem}_transparent_animated"
        if interval is not None:
            return f"{input_stem}_transparent_frames"

        suffix = ".mp4" if output_format == "mp4" else ".webp"
        return f"{input_stem}_transparent{suffix}"

    if animated:
        return f"{input_stem}_animated"
    if interval is not None:
        return f"{input_stem}_frames"
    suffix = ".mp4" if output_format == "mp4" else (input_file.suffix or ".mp4")
    return f"{input_stem}_bg_removed{suffix}"


def _build_run_timestamp(now: datetime | None = None) -> str:
    """Create the timestamp suffix used for auto-created output directories."""
    current = now or datetime.now()
    return current.strftime(TIMESTAMP_FORMAT)


def _default_output_root(input_path: str, *, run_timestamp: str | None = None) -> Path:
    """Build the auto-created output directory for an input file."""
    timestamp = run_timestamp or _build_run_timestamp()
    return DEFAULT_OUTPUT_DIR / f"{Path(input_path).stem}_{timestamp}"


def resolve_output_target(
    input_path: str,
    output: str | None,
    *,
    animated: str | None = None,
    interval: float | None = None,
    output_format: str | None = None,
    run_timestamp: str | None = None,
    source_mode: str = "rembg",
) -> str:
    """Resolve a final output target, filling in sensible defaults when omitted."""
    output_name = _default_output_name(
        input_path,
        animated=animated,
        interval=interval,
        output_format=output_format,
        source_mode=source_mode,
    )
    if not output:
        return str(
            _default_output_root(input_path, run_timestamp=run_timestamp) / output_name
        )

    if _looks_like_directory(output):
        return str(Path(output) / output_name)

    return output


def _replace_stem_token(path: Path, source_token: str, target_token: str) -> Path:
    """Swap a token inside the filename stem while preserving the suffix."""
    if source_token not in path.stem:
        raise ValueError(
            f"Cannot infer matching MatAnyone pair from {path}. "
            f"The filename must contain {source_token!r}."
        )

    return path.with_name(f"{path.stem.replace(source_token, target_token, 1)}{path.suffix}")


def resolve_matanyone_inputs(
    input_path: str,
    alpha_video: str | None = None,
) -> tuple[str, str]:
    """Resolve foreground and alpha videos for MatAnyone mode."""
    input_candidate = Path(input_path)

    if input_candidate.is_dir():
        fg_candidates = sorted(
            path
            for path in input_candidate.iterdir()
            if path.is_file() and "_fg" in path.stem
        )
        if not fg_candidates:
            raise ValueError(
                f"No MatAnyone foreground video (*_fg.*) found in {input_candidate}"
            )
        if len(fg_candidates) > 1 and alpha_video is None:
            raise ValueError(
                f"Multiple MatAnyone foreground videos found in {input_candidate}. "
                "Pass a specific foreground input or use --alpha-video."
            )
        fg_path = fg_candidates[0]
    else:
        fg_path = input_candidate

    if alpha_video:
        alpha_path = Path(alpha_video)
    elif "_alpha" in fg_path.stem:
        alpha_path = fg_path
        fg_path = _replace_stem_token(alpha_path, "_alpha", "_fg")
    else:
        alpha_path = _replace_stem_token(fg_path, "_fg", "_alpha")

    if not fg_path.exists():
        raise ValueError(f"MatAnyone foreground video not found: {fg_path}")
    if not alpha_path.exists():
        raise ValueError(f"MatAnyone alpha video not found: {alpha_path}")

    return str(fg_path), str(alpha_path)


def _infer_matanyone_animated_format(
    output: str | None,
    requested_format: str,
) -> str | None:
    """Infer animated output format for MatAnyone mode from the requested target."""
    if output and not _looks_like_directory(output):
        suffix = Path(output).suffix.lower().lstrip(".")
        if suffix in {"webp", "gif"}:
            return suffix
        if suffix:
            return None

    if requested_format == "webp":
        return "webp"

    return None


def _run_matanyone_pair_pipeline(
    remover,
    args: argparse.Namespace,
    *,
    fg_video_path: str,
    alpha_video_path: str,
    run_timestamp: str,
    output_name_source: str,
    source_mode: str,
    bg_color: tuple[int, int, int] | None,
    output_size: tuple[int, int] | None,
    allow_implicit_animated: bool,
) -> int:
    """Route a MatAnyone foreground/alpha pair through the existing exporters."""
    inferred_animated = args.animated
    if inferred_animated is None and allow_implicit_animated:
        inferred_animated = _infer_matanyone_animated_format(
            args.output,
            args.format,
        )

    if inferred_animated:
        resolved_output = resolve_output_target(
            output_name_source,
            args.output,
            animated=inferred_animated,
            interval=args.interval,
            run_timestamp=run_timestamp,
            source_mode=source_mode,
        )
        if args.output is None:
            print(
                "Output not specified. "
                f"Saving animated output under: {resolved_output}"
            )
        base_output = _normalize_animated_output(resolved_output)
        Path(base_output).parent.mkdir(parents=True, exist_ok=True)
        formats = ["webp", "gif"] if inferred_animated == "both" else [inferred_animated]
        for fmt in formats:
            remover.to_animated_from_mask_pair(
                fg_video_path=fg_video_path,
                alpha_video_path=alpha_video_path,
                output_path=f"{base_output}.{fmt}",
                fps=args.webp_fps,
                max_frames=args.max_frames,
                format=fmt,
                output_size=output_size,
                corner_radius=args.corner_radius,
            )
        return 0

    if args.interval is not None:
        output_dir = resolve_output_target(
            output_name_source,
            args.output,
            interval=args.interval,
            output_format=args.format,
            run_timestamp=run_timestamp,
            source_mode=source_mode,
        )
        if args.output is None:
            print(
                "Output not specified. "
                f"Saving extracted frames under: {output_dir}"
            )
        if not output_dir.endswith(f"_{args.format}"):
            output_dir = f"{output_dir}_{args.format}"
        remover.extract_matanyone_frames_interval(
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            output_dir=output_dir,
            interval_sec=args.interval,
            format=args.format,
            output_size=output_size,
            corner_radius=args.corner_radius,
        )
        return 0

    output_path = resolve_output_target(
        output_name_source,
        args.output,
        output_format="mp4",
        run_timestamp=run_timestamp,
        source_mode=source_mode,
    )
    if args.output is None:
        print(f"Output not specified. Saving video to: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    remover.process_matanyone_video(
        fg_video_path=fg_video_path,
        alpha_video_path=alpha_video_path,
        output_path=output_path,
        fps=args.fps,
        bg_color=bg_color,
        bg_image_path=args.bg_image,
        keep_frames=args.keep_frames,
        work_dir=args.work_dir,
        output_size=output_size,
    )
    return 0


def _build_matanyone_runner(args: argparse.Namespace) -> MatAnyoneRunner:
    """Create the subprocess runner for MatAnyone-backed inference."""
    try:
        python_executable = resolve_matanyone_python(None, args.matanyone_python)
        repo_root = (
            resolve_matanyone_root(args.matanyone_root)
            if args.matanyone_root
            else python_executable.parent.parent
        )
    except ValueError:
        repo_root = resolve_matanyone_root(args.matanyone_root)
        python_executable = resolve_matanyone_python(repo_root, args.matanyone_python)

    return MatAnyoneRunner(
        repo_root=repo_root,
        python_executable=python_executable,
        device=args.matanyone_device,
        model_name=args.matanyone_model,
        performance_profile=args.matanyone_performance_profile,
        sam_model_type=args.matanyone_sam_model_type,
        cpu_threads=args.matanyone_cpu_threads,
        frame_limit=args.matanyone_frame_limit,
        video_target_fps=args.matanyone_video_target_fps,
        output_fps=args.matanyone_output_fps,
        select_frame=args.matanyone_select_frame,
        end_frame=args.matanyone_end_frame,
        positive_points=list(args.positive_point),
        negative_points=list(args.negative_point),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the CLI command."""
    from .bg_remover import VideoBackgroundRemover

    if args.interval is not None and args.format == "mp4":
        raise ValueError(
            "--format mp4 cannot be used with --interval. "
            "Use webp/png for frame extraction."
        )

    if args.animated and args.format == "mp4":
        raise ValueError(
            "--format mp4 cannot be used with --animated. "
            "Use regular video output instead."
        )

    if args.no_bg_removal and args.animated is None and args.interval is None:
        raise ValueError(
            "--no-bg-removal currently supports only --animated or --interval output."
        )

    if args.matanyone and args.backend == "matanyone":
        raise ValueError(
            "Use either --matanyone for an existing foreground/alpha pair or "
            "--backend matanyone for running MatAnyone on a regular input, not both."
        )

    if args.backend == "matanyone" and args.no_bg_removal:
        raise ValueError("--no-bg-removal cannot be used with --backend matanyone.")

    if args.backend != "matanyone" and (
        args.matanyone_root
        or args.matanyone_python
        or args.positive_point
        or args.negative_point
    ):
        print(
            "Warning: MatAnyone-specific options were provided while using the rembg backend. "
            "They will be ignored."
        )

    bg_color = parse_color(args.bg_color) if args.bg_color else None
    output_size = parse_size(args.size) if args.size else None

    if args.backend == "matanyone":
        print(f"Using backend: {args.backend} ({args.matanyone_model})")
    else:
        print(f"Using model: {args.model}")
    remover = VideoBackgroundRemover(model_name=args.model)
    run_timestamp = _build_run_timestamp()

    if args.matanyone:
        fg_video_path, alpha_video_path = resolve_matanyone_inputs(
            args.input,
            alpha_video=args.alpha_video,
        )
        return _run_matanyone_pair_pipeline(
            remover,
            args,
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            run_timestamp=run_timestamp,
            output_name_source=fg_video_path,
            source_mode="matanyone",
            bg_color=bg_color,
            output_size=output_size,
            allow_implicit_animated=True,
        )

    if args.backend == "matanyone":
        runner = _build_matanyone_runner(args)
        temp_dir_kwargs: dict[str, str] = {}
        if args.work_dir:
            Path(args.work_dir).mkdir(parents=True, exist_ok=True)
            temp_dir_kwargs["dir"] = args.work_dir

        if args.keep_frames:
            matanyone_output_root = Path(
                tempfile.mkdtemp(prefix="matanyone_backend_", **temp_dir_kwargs)
            )
            output_context = nullcontext(str(matanyone_output_root))
        else:
            output_context = tempfile.TemporaryDirectory(
                prefix="matanyone_backend_",
                **temp_dir_kwargs,
            )

        with output_context as temp_output_root:
            result = runner.run(args.input, temp_output_root)
            if args.keep_frames:
                print(
                    "Keeping MatAnyone intermediate outputs under: "
                    f"{result.output_dir}"
                )
            return _run_matanyone_pair_pipeline(
                remover,
                args,
                fg_video_path=str(result.foreground_path),
                alpha_video_path=str(result.alpha_path),
                run_timestamp=run_timestamp,
                output_name_source=args.input,
                source_mode="rembg",
                bg_color=bg_color,
                output_size=output_size,
                allow_implicit_animated=False,
            )

    if args.animated:
        resolved_output = resolve_output_target(
            args.input,
            args.output,
            animated=args.animated,
            interval=args.interval,
            run_timestamp=run_timestamp,
            source_mode="rembg",
        )
        if args.output is None:
            print(
                "Output not specified. "
                f"Saving animated output under: {resolved_output}"
            )
        base_output = _normalize_animated_output(resolved_output)
        Path(base_output).parent.mkdir(parents=True, exist_ok=True)
        formats = ["webp", "gif"] if args.animated == "both" else [args.animated]
        for fmt in formats:
            remover.to_animated(
                video_path=args.input,
                output_path=f"{base_output}.{fmt}",
                fps=args.webp_fps,
                max_frames=args.max_frames,
                format=fmt,
                output_size=output_size,
                remove_background=not args.no_bg_removal,
                corner_radius=args.corner_radius,
            )
        return 0

    if args.interval is not None:
        output_dir = resolve_output_target(
            args.input,
            args.output,
            animated=args.animated,
            interval=args.interval,
            output_format=args.format,
            run_timestamp=run_timestamp,
            source_mode="rembg",
        )
        if args.output is None:
            print(
                "Output not specified. "
                f"Saving extracted frames under: {output_dir}"
            )
        if not output_dir.endswith(f"_{args.format}"):
            output_dir = f"{output_dir}_{args.format}"
        remover.extract_frames_interval(
            video_path=args.input,
            output_dir=output_dir,
            interval_sec=args.interval,
            format=args.format,
            output_size=output_size,
            remove_background=not args.no_bg_removal,
            corner_radius=args.corner_radius,
        )
        return 0

    output_path = resolve_output_target(
        args.input,
        args.output,
        animated=args.animated,
        interval=args.interval,
        output_format=args.format,
        run_timestamp=run_timestamp,
        source_mode="rembg",
    )
    if args.output is None:
        print(f"Output not specified. Saving video to: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    remover.process_video(
        input_path=args.input,
        output_path=output_path,
        fps=args.fps,
        bg_color=bg_color,
        bg_image_path=args.bg_image,
        keep_frames=args.keep_frames,
        work_dir=args.work_dir,
        output_size=output_size,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
