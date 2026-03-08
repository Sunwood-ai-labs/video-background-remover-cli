"""Command-line interface for video background removal."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys


MODEL_CHOICES = [
    "isnet-general-use",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
]
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
        help="Background removal model (default: isnet-general-use)",
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

    bg_color = None
    if args.bg_color:
        bg_color = parse_color(args.bg_color)
    output_size = parse_size(args.size) if args.size else None

    print(f"Using model: {args.model}")
    remover = VideoBackgroundRemover(model_name=args.model)
    run_timestamp = _build_run_timestamp()

    if args.matanyone:
        fg_video_path, alpha_video_path = resolve_matanyone_inputs(
            args.input,
            alpha_video=args.alpha_video,
        )
        inferred_animated = args.animated or _infer_matanyone_animated_format(
            args.output,
            args.format,
        )

        if inferred_animated:
            resolved_output = resolve_output_target(
                fg_video_path,
                args.output,
                animated=inferred_animated,
                interval=args.interval,
                run_timestamp=run_timestamp,
                source_mode="matanyone",
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
                )
            return 0

        if args.interval is not None:
            output_dir = resolve_output_target(
                fg_video_path,
                args.output,
                interval=args.interval,
                output_format=args.format,
                run_timestamp=run_timestamp,
                source_mode="matanyone",
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
            )
            return 0

        output_format = "mp4"
        output_path = resolve_output_target(
            fg_video_path,
            args.output,
            output_format=output_format,
            run_timestamp=run_timestamp,
            source_mode="matanyone",
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
