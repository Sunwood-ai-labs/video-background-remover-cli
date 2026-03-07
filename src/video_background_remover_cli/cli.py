"""Command-line interface for video background removal."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


MODEL_CHOICES = [
    "isnet-general-use",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
]


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


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-background-remover",
        description=(
            "Remove video backgrounds with rembg and OpenCV. "
            "Supports full video export, transparent frame export, and animated WebP / GIF."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  video-background-remover input.mp4 output.mp4 --bg-color green\n"
            "  video-background-remover input.mp4 output/frames --interval 1 --format webp\n"
            "  video-background-remover input.mp4 output/anim.webp --animated webp --webp-fps 10"
        ),
    )
    parser.add_argument("input", help="Input video file path")
    parser.add_argument(
        "output",
        help="Output video path, output file path, or output directory depending on mode",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="isnet-general-use",
        choices=MODEL_CHOICES,
        help="Background removal model (default: isnet-general-use)",
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
        choices=["webp", "png"],
        help="Output format for --interval mode (default: webp)",
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


def run(args: argparse.Namespace) -> int:
    """Execute the CLI command."""
    from .bg_remover import VideoBackgroundRemover

    bg_color = None
    if args.bg_color:
        bg_color = parse_color(args.bg_color)

    print(f"Using model: {args.model}")
    remover = VideoBackgroundRemover(model_name=args.model)

    if args.animated:
        base_output = _normalize_animated_output(args.output)
        formats = ["webp", "gif"] if args.animated == "both" else [args.animated]
        for fmt in formats:
            remover.to_animated(
                video_path=args.input,
                output_path=f"{base_output}.{fmt}",
                fps=args.webp_fps,
                max_frames=args.max_frames,
                format=fmt,
            )
        return 0

    if args.interval is not None:
        output_dir = args.output
        if not output_dir.endswith(f"_{args.format}"):
            output_dir = f"{output_dir}_{args.format}"
        remover.extract_frames_interval(
            video_path=args.input,
            output_dir=output_dir,
            interval_sec=args.interval,
            format=args.format,
        )
        return 0

    remover.process_video(
        input_path=args.input,
        output_path=args.output,
        fps=args.fps,
        bg_color=bg_color,
        bg_image_path=args.bg_image,
        keep_frames=args.keep_frames,
        work_dir=args.work_dir,
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
