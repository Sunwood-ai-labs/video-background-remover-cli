"""Synchronize repository version files from a release version."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[A-Za-z0-9.-]*)?$")


def normalize_version(version: str) -> str:
    """Strip an optional leading v and validate the remaining version."""
    normalized = version.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]

    if not VERSION_PATTERN.match(normalized):
        raise ValueError(
            f"Unsupported version '{version}'. Expected a tag like v1.2.3 or a version like 1.2.3."
        )

    return normalized


def replace_first(pattern: str, replacement: str, content: str, path: Path) -> str:
    """Replace the first regex match or raise if the pattern is missing."""
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Could not update version in {path}")
    return updated


def sync_version(version: str, root: Path = ROOT) -> list[Path]:
    """Apply the release version to tracked version files."""
    normalized = normalize_version(version)
    updated_files: list[Path] = []

    replacements: dict[Path, tuple[str, str]] = {
        root / "pyproject.toml": (
            r'^version = "[^"]+"$',
            f'version = "{normalized}"',
        ),
        root / "src" / "video_background_remover_cli" / "__init__.py": (
            r'^    __version__ = "[^"]+"$',
            f'    __version__ = "{normalized}"',
        ),
        root / "uv.lock": (
            r'(^name = "video-background-remover"\r?\nversion = ")[^"]+(")',
            rf"\g<1>{normalized}\2",
        ),
    }

    for path, (pattern, replacement) in replacements.items():
        original = path.read_text(encoding="utf-8")
        updated = replace_first(pattern, replacement, original, path)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            updated_files.append(path)

    return updated_files


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Synchronize package versions from a release tag or version."
    )
    parser.add_argument("version", help="Release version or tag, for example 0.1.2 or v0.1.2")
    args = parser.parse_args(argv)

    try:
        updated_files = sync_version(args.version)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for path in updated_files:
        print(f"Updated {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
