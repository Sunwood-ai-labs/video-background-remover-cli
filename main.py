"""
Video Background Remover - Main entry point.

Using RMBG-1.4 model (same as Xenova/remove-background-web)
https://huggingface.co/spaces/Xenova/remove-background-web

Usage:
    python main.py input_video.mp4 output_video.mp4
    python main.py input_video.mp4 output_video.mp4 --bg-color white
    python main.py input_video.mp4 output_video.mp4 --bg-image background.jpg
    python main.py input_video.mp4 output_frames/ --interval 1 --format webp
"""

import argparse
import sys
import os
from src.bg_remover import VideoBackgroundRemover


def parse_color(color_str: str) -> tuple:
    """Parse color string to RGB tuple."""
    colors = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "red": (255, 0, 0),
        "gray": (128, 128, 128),
        "transparent": None,
    }

    color_str = color_str.lower()
    if color_str in colors:
        return colors[color_str]

    # Parse RGB values (e.g., "255,128,0")
    try:
        values = [int(x.strip()) for x in color_str.split(",")]
        if len(values) == 3:
            return tuple(values)
    except ValueError:
        pass

    raise ValueError(
        f"Invalid color: {color_str}. Use color name or RGB values (e.g., '255,128,0')"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Remove background from video using RMBG-1.4 (same model as Xenova/remove-background-web)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full video processing
  %(prog)s input.mp4 output.mp4
  %(prog)s input.mp4 output.mp4 --bg-color green

  # Extract frames at 1-second intervals as webp
  %(prog)s input.mp4 output_frames/ --interval 1 --format webp
        """,
    )
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", help="Output video path or directory (for --interval)")
    parser.add_argument(
        "--model",
        type=str,
        default="isnet-general-use",
        choices=[
            "isnet-general-use",
            "u2net",
            "u2netp",
            "u2net_human_seg",
            "silueta",
        ],
        help="Background removal model (default: isnet-general-use)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Output FPS (default: same as input)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        help="Background color (e.g., white, black, green, or '255,128,0')",
    )
    parser.add_argument(
        "--bg-image",
        type=str,
        help="Path to background image",
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
        help="Extract frames at interval (in seconds). Output becomes directory.",
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
        help="Output as animated image: webp, gif, or both",
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

    args = parser.parse_args()

    # Parse background color
    bg_color = None
    if args.bg_color:
        bg_color = parse_color(args.bg_color)

    # Create remover with specified model
    print(f"Using model: {args.model}")
    remover = VideoBackgroundRemover(model_name=args.model)

    try:
        if args.animated:
            # Animated mode (webp, gif, or both)
            base_output = args.output.rstrip(".webp").rstrip(".gif")

            formats = []
            if args.animated == "both":
                formats = ["webp", "gif"]
            else:
                formats = [args.animated]

            for fmt in formats:
                output_path = f"{base_output}.{fmt}"
                remover.to_animated(
                    video_path=args.input,
                    output_path=output_path,
                    fps=args.webp_fps,
                    max_frames=args.max_frames,
                    format=fmt,
                )
        elif args.interval:
            # Interval mode: extract frames at intervals
            output_dir = args.output
            # Add format extension to directory name if not already
            if not output_dir.endswith(f"_{args.format}"):
                output_dir = f"{output_dir}_{args.format}"

            remover.extract_frames_interval(
                video_path=args.input,
                output_dir=output_dir,
                interval_sec=args.interval,
                format=args.format,
            )
        else:
            # Full video mode
            remover.process_video(
                input_path=args.input,
                output_path=args.output,
                fps=args.fps,
                bg_color=bg_color,
                bg_image_path=args.bg_image,
                keep_frames=args.keep_frames,
                work_dir=args.work_dir,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
