"""Shared execution service for CLI and WebUI background-removal requests."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Callable

from .models import ExportRequest
from .options import (
    _build_run_timestamp,
    _looks_like_directory,
    _normalize_animated_output,
    parse_color,
    parse_size,
    resolve_matanyone_inputs,
    resolve_output_target,
)


RemoverFactory = Callable[..., object]
RunnerFactory = Callable[..., object]
RootResolver = Callable[[str | None], Path]
PythonResolver = Callable[[Path | None, str | None], Path]
TimestampBuilder = Callable[[], str]
PairResolver = Callable[[str, str | None], tuple[str, str]]
MkdtempFactory = Callable[..., str]
TemporaryDirectoryFactory = Callable[..., tempfile.TemporaryDirectory]


@dataclass(slots=True)
class ExportServiceContext:
    """Dependencies needed by the shared export service."""

    remover_factory: RemoverFactory
    matanyone_runner_factory: RunnerFactory
    resolve_matanyone_root: RootResolver
    resolve_matanyone_python: PythonResolver
    build_run_timestamp: TimestampBuilder = _build_run_timestamp
    resolve_pair_inputs: PairResolver = resolve_matanyone_inputs
    mkdtemp_factory: MkdtempFactory = tempfile.mkdtemp
    temporary_directory_factory: TemporaryDirectoryFactory = tempfile.TemporaryDirectory


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


def _run_pair_exports(
    remover,
    request: ExportRequest,
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
    """Route a foreground/alpha pair through the shared exporters."""
    inferred_animated = request.animated_format
    if inferred_animated is None and allow_implicit_animated:
        inferred_animated = _infer_matanyone_animated_format(
            request.output_path,
            request.output_format,
        )

    if inferred_animated:
        resolved_output = resolve_output_target(
            output_name_source,
            request.output_path,
            animated=inferred_animated,
            interval=request.interval_seconds,
            run_timestamp=run_timestamp,
            source_mode=source_mode,
        )
        if request.output_path is None:
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
                fps=request.animated_fps,
                max_frames=request.max_frames,
                format=fmt,
                output_size=output_size,
                corner_radius=request.corner_radius,
            )
        return 0

    if request.interval_seconds is not None:
        output_dir = resolve_output_target(
            output_name_source,
            request.output_path,
            interval=request.interval_seconds,
            output_format=request.output_format,
            run_timestamp=run_timestamp,
            source_mode=source_mode,
        )
        if request.output_path is None:
            print(
                "Output not specified. "
                f"Saving extracted frames under: {output_dir}"
            )
        if not output_dir.endswith(f"_{request.output_format}"):
            output_dir = f"{output_dir}_{request.output_format}"
        remover.extract_matanyone_frames_interval(
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            output_dir=output_dir,
            interval_sec=request.interval_seconds,
            format=request.output_format,
            output_size=output_size,
            corner_radius=request.corner_radius,
        )
        return 0

    output_path = resolve_output_target(
        output_name_source,
        request.output_path,
        output_format="mp4",
        run_timestamp=run_timestamp,
        source_mode=source_mode,
    )
    if request.output_path is None:
        print(f"Output not specified. Saving video to: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    remover.process_matanyone_video(
        fg_video_path=fg_video_path,
        alpha_video_path=alpha_video_path,
        output_path=output_path,
        fps=request.fps,
        bg_color=bg_color,
        bg_image_path=request.bg_image_path,
        keep_frames=request.keep_frames,
        work_dir=request.work_dir,
        output_size=output_size,
    )
    return 0


def _run_rembg_backend(
    remover,
    request: ExportRequest,
    *,
    run_timestamp: str,
    bg_color: tuple[int, int, int] | None,
    output_size: tuple[int, int] | None,
) -> int:
    """Execute the regular rembg backend."""
    if request.animated_format:
        resolved_output = resolve_output_target(
            request.input_path,
            request.output_path,
            animated=request.animated_format,
            interval=request.interval_seconds,
            run_timestamp=run_timestamp,
            source_mode="rembg",
        )
        if request.output_path is None:
            print(
                "Output not specified. "
                f"Saving animated output under: {resolved_output}"
            )
        base_output = _normalize_animated_output(resolved_output)
        Path(base_output).parent.mkdir(parents=True, exist_ok=True)
        formats = ["webp", "gif"] if request.animated_format == "both" else [request.animated_format]
        for fmt in formats:
            remover.to_animated(
                video_path=request.input_path,
                output_path=f"{base_output}.{fmt}",
                fps=request.animated_fps,
                max_frames=request.max_frames,
                format=fmt,
                output_size=output_size,
                remove_background=not request.no_bg_removal,
                corner_radius=request.corner_radius,
            )
        return 0

    if request.interval_seconds is not None:
        output_dir = resolve_output_target(
            request.input_path,
            request.output_path,
            animated=request.animated_format,
            interval=request.interval_seconds,
            output_format=request.output_format,
            run_timestamp=run_timestamp,
            source_mode="rembg",
        )
        if request.output_path is None:
            print(
                "Output not specified. "
                f"Saving extracted frames under: {output_dir}"
            )
        if not output_dir.endswith(f"_{request.output_format}"):
            output_dir = f"{output_dir}_{request.output_format}"
        remover.extract_frames_interval(
            video_path=request.input_path,
            output_dir=output_dir,
            interval_sec=request.interval_seconds,
            format=request.output_format,
            output_size=output_size,
            remove_background=not request.no_bg_removal,
            corner_radius=request.corner_radius,
        )
        return 0

    output_path = resolve_output_target(
        request.input_path,
        request.output_path,
        animated=request.animated_format,
        interval=request.interval_seconds,
        output_format=request.output_format,
        run_timestamp=run_timestamp,
        source_mode="rembg",
    )
    if request.output_path is None:
        print(f"Output not specified. Saving video to: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    remover.process_video(
        input_path=request.input_path,
        output_path=output_path,
        fps=request.fps,
        bg_color=bg_color,
        bg_image_path=request.bg_image_path,
        keep_frames=request.keep_frames,
        work_dir=request.work_dir,
        output_size=output_size,
    )
    return 0


def _build_matanyone_runner(request: ExportRequest, context: ExportServiceContext):
    """Create the subprocess runner for MatAnyone-backed inference."""
    try:
        python_executable = context.resolve_matanyone_python(
            None,
            request.matanyone_python,
        )
        repo_root = (
            context.resolve_matanyone_root(request.matanyone_root)
            if request.matanyone_root
            else python_executable.parent.parent
        )
    except ValueError:
        repo_root = context.resolve_matanyone_root(request.matanyone_root)
        python_executable = context.resolve_matanyone_python(
            repo_root,
            request.matanyone_python,
        )

    return context.matanyone_runner_factory(
        repo_root=repo_root,
        python_executable=python_executable,
        device=request.matanyone_device,
        model_name=request.matanyone_model_name,
        performance_profile=request.matanyone_performance_profile,
        sam_model_type=request.matanyone_sam_model_type,
        cpu_threads=request.matanyone_cpu_threads,
        frame_limit=request.matanyone_frame_limit,
        video_target_fps=request.matanyone_video_target_fps,
        output_fps=request.matanyone_output_fps,
        select_frame=request.matanyone_select_frame,
        end_frame=request.matanyone_end_frame,
        positive_points=list(request.positive_points),
        negative_points=list(request.negative_points),
    )


def execute_export(request: ExportRequest, *, context: ExportServiceContext) -> int:
    """Execute one export request using the shared background-removal core."""
    if request.interval_seconds is not None and request.output_format == "mp4":
        raise ValueError(
            "--format mp4 cannot be used with --interval. "
            "Use webp/png for frame extraction."
        )

    if request.animated_format and request.output_format == "mp4":
        raise ValueError(
            "--format mp4 cannot be used with --animated. "
            "Use regular video output instead."
        )

    if request.no_bg_removal and request.animated_format is None and request.interval_seconds is None:
        raise ValueError(
            "--no-bg-removal currently supports only --animated or --interval output."
        )

    if request.use_matanyone_pair and request.backend_name == "matanyone":
        raise ValueError(
            "Use either --matanyone for an existing foreground/alpha pair or "
            "--backend matanyone for running MatAnyone on a regular input, not both."
        )

    if request.backend_name == "matanyone" and request.no_bg_removal:
        raise ValueError("--no-bg-removal cannot be used with --backend matanyone.")

    if request.backend_name != "matanyone" and (
        request.matanyone_root
        or request.matanyone_python
        or request.positive_points
        or request.negative_points
    ):
        print(
            "Warning: MatAnyone-specific options were provided while using the rembg backend. "
            "They will be ignored."
        )

    bg_color = parse_color(request.bg_color_text) if request.bg_color_text else None
    output_size = parse_size(request.size_text) if request.size_text else None

    if request.backend_name == "matanyone":
        print(f"Using backend: {request.backend_name} ({request.matanyone_model_name})")
    else:
        print(f"Using model: {request.model_name}")

    remover = context.remover_factory(model_name=request.model_name)
    run_timestamp = context.build_run_timestamp()

    if request.use_matanyone_pair:
        fg_video_path, alpha_video_path = context.resolve_pair_inputs(
            request.input_path,
            request.alpha_video_path,
        )
        return _run_pair_exports(
            remover,
            request,
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            run_timestamp=run_timestamp,
            output_name_source=fg_video_path,
            source_mode="matanyone",
            bg_color=bg_color,
            output_size=output_size,
            allow_implicit_animated=True,
        )

    if request.backend_name == "matanyone":
        runner = _build_matanyone_runner(request, context)
        temp_dir_kwargs: dict[str, str] = {}
        if request.work_dir:
            Path(request.work_dir).mkdir(parents=True, exist_ok=True)
            temp_dir_kwargs["dir"] = request.work_dir

        if request.keep_frames:
            matanyone_output_root = Path(
                context.mkdtemp_factory(prefix="matanyone_backend_", **temp_dir_kwargs)
            )
            output_context = nullcontext(str(matanyone_output_root))
        else:
            output_context = context.temporary_directory_factory(
                prefix="matanyone_backend_",
                **temp_dir_kwargs,
            )

        with output_context as temp_output_root:
            result = runner.run(request.input_path, temp_output_root)
            if request.keep_frames:
                print(
                    "Keeping MatAnyone intermediate outputs under: "
                    f"{result.output_dir}"
                )
            return _run_pair_exports(
                remover,
                request,
                fg_video_path=str(result.foreground_path),
                alpha_video_path=str(result.alpha_path),
                run_timestamp=run_timestamp,
                output_name_source=request.input_path,
                source_mode="rembg",
                bg_color=bg_color,
                output_size=output_size,
                allow_implicit_animated=False,
            )

    return _run_rembg_backend(
        remover,
        request,
        run_timestamp=run_timestamp,
        bg_color=bg_color,
        output_size=output_size,
    )
