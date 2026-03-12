"""Shared background-removal core used by the CLI and WebUI adapters."""

from .examples import CliExampleCase, build_cli_example_cases, build_cli_examples_by_mode
from .models import ExportRequest
from .options import (
    DEFAULT_OUTPUT_DIR,
    TIMESTAMP_FORMAT,
    _build_run_timestamp,
    _default_output_name,
    _default_output_root,
    _normalize_animated_output,
    parse_color,
    parse_size,
    resolve_matanyone_inputs,
    resolve_output_target,
)
from .service import execute_export

__all__ = [
    "CliExampleCase",
    "DEFAULT_OUTPUT_DIR",
    "ExportRequest",
    "TIMESTAMP_FORMAT",
    "_build_run_timestamp",
    "_default_output_name",
    "_default_output_root",
    "_normalize_animated_output",
    "build_cli_example_cases",
    "build_cli_examples_by_mode",
    "execute_export",
    "parse_color",
    "parse_size",
    "resolve_matanyone_inputs",
    "resolve_output_target",
]
