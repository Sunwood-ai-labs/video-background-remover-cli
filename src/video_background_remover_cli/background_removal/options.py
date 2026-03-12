"""Shared parsing and output-path helpers for background-removal requests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("output")
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
MATANYONE_STEM_SUFFIXES = ("_fg", "_alpha")


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
