"""Command-line interface for shared background-removal workflows."""

from __future__ import annotations

import argparse
import sys
import tempfile

from .background_removal import (
    _build_run_timestamp,
    _default_output_name,
    _default_output_root,
    _normalize_animated_output,
    parse_color,
    parse_size,
    resolve_matanyone_inputs,
    resolve_output_target,
)
from .background_removal.models import ExportRequest
from .background_removal.service import ExportServiceContext, execute_export
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
        help="Maximum number of frames for animated output",
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


def run(args: argparse.Namespace) -> int:
    """Execute the CLI command."""
    from .bg_remover import VideoBackgroundRemover

    request = ExportRequest.from_namespace(args)
    context = ExportServiceContext(
        remover_factory=VideoBackgroundRemover,
        matanyone_runner_factory=MatAnyoneRunner,
        resolve_matanyone_root=resolve_matanyone_root,
        resolve_matanyone_python=resolve_matanyone_python,
        build_run_timestamp=_build_run_timestamp,
        resolve_pair_inputs=resolve_matanyone_inputs,
        mkdtemp_factory=tempfile.mkdtemp,
        temporary_directory_factory=tempfile.TemporaryDirectory,
    )
    return execute_export(request, context=context)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
