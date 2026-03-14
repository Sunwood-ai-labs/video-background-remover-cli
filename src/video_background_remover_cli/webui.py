"""Gradio WebUI for video-background-remover with integrated MatAnyone workflows."""

from __future__ import annotations

import asyncio
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Any
import zipfile

from PIL import Image

from . import cli as cli_module
from .background_removal import (
    build_cli_examples_by_mode,
    execute_export,
    parse_color,
    parse_size,
    resolve_matanyone_inputs,
)
from .background_removal.models import ExportRequest
from .background_removal.service import ExportServiceContext
from .bg_remover import VideoBackgroundRemover
from .matanyone_bridge import (
    MATANYONE_DEVICE_CHOICES,
    MATANYONE_MODEL_CHOICES,
    MATANYONE_PROFILE_CHOICES,
    MATANYONE_SAM_MODEL_CHOICES,
    MatAnyoneRunner,
    resolve_matanyone_python,
    resolve_matanyone_root,
)


DEFAULT_RESULTS_DIR = Path("output") / "webui"
INTERNAL_LAUNCH_FLAG = "--_internal-launch"


def _configure_windows_event_loop_policy() -> None:
    """Use the selector loop on Windows to avoid noisy Proactor socket-reset logs."""
    if os.name != "nt":
        return
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is None:
        return
    current_policy = asyncio.get_event_loop_policy()
    if isinstance(current_policy, selector_policy):
        return
    asyncio.set_event_loop_policy(selector_policy())


def _suppress_windows_connection_reset_noise() -> None:
    """Ignore benign WinError 10054 transport shutdown noise on Windows."""
    if os.name != "nt":
        return
    try:
        from asyncio import proactor_events
    except ImportError:
        return

    transport_class = getattr(proactor_events, "_ProactorBasePipeTransport", None)
    if transport_class is None:
        return
    original = getattr(transport_class, "_call_connection_lost", None)
    if original is None or getattr(original, "_vbr_patched", False):
        return

    def patched_call_connection_lost(self: Any, exc: BaseException | None) -> None:
        try:
            original(self, exc)
        except (ConnectionResetError, OSError) as error:
            if getattr(error, "winerror", None) == 10054:
                return
            raise

    setattr(patched_call_connection_lost, "_vbr_patched", True)
    transport_class._call_connection_lost = patched_call_connection_lost


def build_parser() -> argparse.ArgumentParser:
    """Create the WebUI argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-background-remover-webui",
        description=(
            "Launch the video-background-remover Gradio app with integrated "
            "MatAnyone workflows and animated WebP/GIF export helpers."
        ),
    )
    parser.add_argument(
        "--matanyone-root",
        type=str,
        default=None,
        help="Path to the MatAnyone repository (default: auto-discover).",
    )
    parser.add_argument(
        "--matanyone-python",
        type=str,
        default=None,
        help="Python executable for the MatAnyone environment.",
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="MatAnyone device selection (default: auto).",
    )
    parser.add_argument(
        "--sam-model-type",
        type=str,
        default="auto",
        help="MatAnyone SAM checkpoint type (default: auto).",
    )
    parser.add_argument(
        "--performance-profile",
        type=str,
        default="auto",
        help="MatAnyone runtime profile (default: auto).",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=None,
        help="Optional CPU thread count when running on CPU.",
    )
    parser.add_argument(
        "--server-name",
        type=str,
        default="127.0.0.1",
        help="Gradio bind address (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Gradio server port (default: 7860).",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Enable a Gradio public share link.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Gradio debug mode.",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory where the WebUI saves outputs and exports.",
    )
    parser.add_argument(
        INTERNAL_LAUNCH_FLAG,
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def _repo_src_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _filtered_forward_args(argv: list[str]) -> list[str]:
    return [arg for arg in argv if arg != INTERNAL_LAUNCH_FLAG]


def build_external_launch_command(
    python_executable: str | Path,
    argv: list[str],
) -> list[str]:
    """Build the delegated command that runs this WebUI inside another Python."""
    forwarded_args = _filtered_forward_args(list(argv))
    return [
        str(python_executable),
        "-m",
        "video_background_remover_cli.webui",
        INTERNAL_LAUNCH_FLAG,
        *forwarded_args,
    ]


def build_pythonpath(existing_pythonpath: str | None, *paths: str | Path) -> str:
    """Prepend one or more paths to PYTHONPATH without losing the existing value."""
    extras = [str(Path(path)) for path in paths if path]
    if existing_pythonpath:
        extras.append(existing_pythonpath)
    return os.pathsep.join(extras)


def _delegate_to_matanyone_python(args: argparse.Namespace, argv: list[str]) -> int:
    """Run the WebUI inside the MatAnyone Python environment."""
    matanyone_root = resolve_matanyone_root(args.matanyone_root)
    python_executable = resolve_matanyone_python(
        matanyone_root,
        explicit_python=args.matanyone_python,
    )
    current_python = Path(sys.executable).resolve()
    if current_python == python_executable.resolve():
        return _launch_in_process(args)

    command = build_external_launch_command(python_executable, argv)
    env = os.environ.copy()
    env["PYTHONPATH"] = build_pythonpath(
        env.get("PYTHONPATH"),
        _repo_src_dir(),
    )
    print("Launching WebUI with MatAnyone Python:", python_executable, flush=True)
    os.execvpe(str(python_executable), command, env)
    raise RuntimeError("Failed to delegate the WebUI process.")


def _ensure_import_path(path: Path) -> None:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _configure_matanyone_imports(matanyone_root: Path) -> None:
    _ensure_import_path(matanyone_root)
    hugging_face_dir = matanyone_root / "hugging_face"
    if hugging_face_dir.exists():
        _ensure_import_path(hugging_face_dir)


def _resolve_device_name(requested_device: str, torch_module: Any) -> str:
    if requested_device != "auto":
        return requested_device
    return "cuda" if torch_module.cuda.is_available() else "cpu"


def _timestamp_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _collect_existing_files(paths: list[str | Path]) -> list[str]:
    return [str(Path(path)) for path in paths if path and Path(path).exists()]


def _zip_paths(paths: list[str | Path], zip_path: str | Path) -> str:
    archive_path = Path(zip_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        archive.write(
                            child,
                            arcname=str(Path(path.name) / child.relative_to(path)),
                        )
            else:
                archive.write(path, arcname=path.name)
    return str(archive_path)


def _as_pil_image(image_like: Any) -> Image.Image:
    if isinstance(image_like, Image.Image):
        return image_like
    return Image.fromarray(image_like)


def _safe_output_size(size_text: str) -> tuple[int, int] | None:
    normalized = (size_text or "").strip()
    return parse_size(normalized) if normalized else None


def _safe_max_frames(value: float | int | None) -> int | None:
    if value in (None, "", 0):
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _safe_interval_seconds(value: float | int | None) -> float:
    interval = float(value or 1.0)
    return max(interval, 0.01)


def _resolve_background_color(
    preset_value: str,
    custom_value: str,
) -> tuple[int, int, int] | None:
    custom_text = (custom_value or "").strip()
    if custom_text:
        return parse_color(custom_text)
    return parse_color(preset_value)


def _resolve_preferred_path(
    upload_path: str | None,
    manual_path: str | None,
) -> str | None:
    manual_value = (manual_path or "").strip()
    return manual_value or upload_path


def _parse_points_text(points_text: str) -> list[str]:
    parsed: list[str] = []
    for raw_line in (points_text or "").replace(";", "\n").splitlines():
        candidate = raw_line.strip()
        if not candidate:
            continue
        parts = [item.strip() for item in candidate.split(",")]
        if len(parts) != 2:
            raise ValueError(
                f"Invalid point: {candidate}. Use one 'x,y' pair per line."
            )
        int(parts[0])
        int(parts[1])
        parsed.append(candidate)
    return parsed


def _push_progress(progress: Any, value: float, desc: str) -> None:
    """Send a lightweight progress update to Gradio when available."""
    if progress is None:
        return
    progress(value, desc=desc)


def _build_cli_output_target(
    base_dir: Path,
    input_path: str,
    source_mode: str,
    export_mode: str,
    animated_format: str,
    frame_format: str,
    video_format: str,
) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    if source_mode == "matanyone_pair":
        stem = stem.replace("_fg", "").replace("_alpha", "")

    if export_mode == "animated":
        suffix = "webp" if animated_format == "both" else animated_format
        return str(base_dir / f"{stem}_animated.{suffix}")
    if export_mode == "interval":
        return str(base_dir / f"{stem}_frames")
    extension = video_format
    return str(base_dir / f"{stem}_output.{extension}")


def _launch_in_process(args: argparse.Namespace) -> int:
    """Run the actual Gradio app inside a MatAnyone-capable Python environment."""
    matanyone_root = resolve_matanyone_root(args.matanyone_root)
    _configure_matanyone_imports(matanyone_root)
    import cv2
    import gradio as gr
    import numpy as np
    import torch

    globals()["gr"] = gr
    globals()["np"] = np

    from hugging_face.tools.painter import mask_painter
    from matanyone2.demo_core import (
        PROFILE_CHOICES,
        RuntimeModelManager,
        SamMaskGenerator,
        apply_sam_points,
        compose_selected_mask,
        configure_ffmpeg_binary,
        configure_runtime,
        create_empty_media_state,
        create_run_output_dir,
        export_debug_artifacts,
        generate_video_from_frames,
        load_image_state,
        load_video_state,
        prepare_sam_frame,
        resolve_sam_model_type,
        resize_output_frame,
        run_matting,
        save_cli_outputs,
    )
    from matanyone2.utils.device import set_default_device

    device_name = _resolve_device_name(args.device, torch)
    set_default_device(device_name)
    configure_runtime(device_name, args.cpu_threads)
    sam_model_type = resolve_sam_model_type(args.sam_model_type, device_name)
    configure_ffmpeg_binary()

    checkpoint_folder = matanyone_root / "pretrained_models"
    runtime_models = RuntimeModelManager(device_name, str(checkpoint_folder))
    sam_checkpoint = runtime_models.get_sam_checkpoint(sam_model_type)
    sam_generator = SamMaskGenerator(sam_checkpoint, sam_model_type, device_name)

    available_models = runtime_models.prefetch_available_models()
    if not available_models:
        raise RuntimeError(
            "No MatAnyone checkpoints are available. "
            "Please populate pretrained_models and try again."
        )
    default_model = (
        "MatAnyone 2" if "MatAnyone 2" in available_models else available_models[0]
    )

    results_root = Path(args.results_dir).resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    remover = VideoBackgroundRemover()

    tutorial_single = matanyone_root / "hugging_face" / "assets" / "tutorial_single_target.mp4"
    tutorial_multi = matanyone_root / "hugging_face" / "assets" / "tutorial_multi_targets.mp4"
    local_star_cat_video = (Path.cwd() / "assets" / "star-cat2.mp4").resolve()
    video_examples = [
        matanyone_root / "hugging_face" / "test_sample" / name
        for name in [
            "test-sample-0-720p.mp4",
            "test-sample-1-720p.mp4",
            "test-sample-2-720p.mp4",
            "test-sample-3-720p.mp4",
            "test-sample-4-720p.mp4",
            "test-sample-5-720p.mp4",
        ]
    ]
    if local_star_cat_video.exists():
        video_examples.insert(0, local_star_cat_video)
    image_examples = [
        matanyone_root / "hugging_face" / "test_sample" / name
        for name in [
            "test-sample-0.jpg",
            "test-sample-1.jpg",
            "test-sample-2.jpg",
            "test-sample-3.jpg",
        ]
    ]
    video_examples = [str(path) for path in video_examples if path.exists()]
    image_examples = [str(path) for path in image_examples if path.exists()]
    cli_examples_by_mode = build_cli_examples_by_mode(Path.cwd())

    def load_runtime_model(display_name: str):
        return runtime_models.load_model(display_name)

    def reset_states(profile_name: str):
        media_state, interactive_state = create_empty_media_state(profile_name, False)
        return media_state, interactive_state

    def reset_video_tab():
        media_state, interactive_state = reset_states(args.performance_profile)
        return (
            media_state,
            interactive_state,
            [[], []],
            gr.update(value=None, visible=False),
            gr.update(value="", visible=True),
            gr.update(value=1, minimum=1, maximum=100, visible=False),
            gr.update(value=1, minimum=1, maximum=100, visible=False),
            gr.update(value="Positive", visible=False),
            gr.update(choices=[], value=[], visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=[], visible=False),
            {},
            gr.update(visible=False),
            gr.update(value=[], visible=False),
            gr.update(value="Load a video to begin interactive target assignment."),
            gr.update(value=""),
        )

    def reset_image_tab():
        media_state, interactive_state = reset_states(args.performance_profile)
        return (
            media_state,
            interactive_state,
            [[], []],
            gr.update(value=None, visible=False),
            gr.update(value="", visible=True),
            gr.update(value=10, minimum=1, maximum=10, visible=False),
            gr.update(value=1, minimum=1, maximum=1, visible=False),
            gr.update(value="Positive", visible=False),
            gr.update(choices=[], value=[], visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=[], visible=False),
            gr.update(value="Load an image to begin interactive target assignment."),
        )

    def get_prompt(click_state: list[list[Any]], click_input: str) -> dict[str, Any]:
        import json

        inputs = json.loads(click_input)
        points = click_state[0]
        labels = click_state[1]
        for input_item in inputs:
            points.append(input_item[:2])
            labels.append(input_item[2])
        click_state[0] = points
        click_state[1] = labels
        return {
            "prompt_type": ["click"],
            "input_point": click_state[0],
            "input_label": click_state[1],
            "multimask_output": True,
        }

    def load_video_input(
        video_input: str,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not video_input:
            raise gr.Error("Select a video first.")
        _push_progress(progress, 0.05, "Opening video...")
        media_state, interactive_state = reset_states(performance_profile)
        media_state, media_info, _runtime_profile = load_video_state(
            video_input,
            device_name,
            performance_profile,
        )
        _push_progress(progress, 0.65, "Preparing the first interactive frame...")
        prepare_sam_frame(sam_generator, media_state, 0, force=True)
        frame_count = len(media_state["origin_images"])
        _push_progress(progress, 1.0, "Video ready")
        return (
            media_state,
            interactive_state,
            [[], []],
            gr.update(value=media_state["origin_images"][0], visible=True),
            gr.update(value=media_info),
            gr.update(value=1, minimum=1, maximum=frame_count, visible=True),
            gr.update(value=frame_count, minimum=1, maximum=frame_count, visible=True),
            gr.update(value="Positive", visible=True),
            gr.update(choices=[], value=[], visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=[], visible=False),
            {},
            gr.update(visible=False),
            gr.update(value=[], visible=False),
            gr.update(
                value=(
                    "Video loaded. Click the frame to add positive or negative points, "
                    "then press Add Mask. Mask Selection will fill after you add a mask."
                )
            ),
            gr.update(value=""),
        )

    def load_image_input(
        image_input: np.ndarray,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if image_input is None:
            raise gr.Error("Select an image first.")
        _push_progress(progress, 0.05, "Opening image...")
        media_state, interactive_state = reset_states(performance_profile)
        media_state, media_info, _runtime_profile = load_image_state(
            image_input,
            device_name,
            performance_profile,
        )
        _push_progress(progress, 0.65, "Preparing the interactive preview...")
        prepare_sam_frame(sam_generator, media_state, 0, force=True)
        _push_progress(progress, 1.0, "Image ready")
        return (
            media_state,
            interactive_state,
            [[], []],
            gr.update(value=media_state["origin_images"][0], visible=True),
            gr.update(value=media_info),
            gr.update(value=10, minimum=1, maximum=10, visible=True),
            gr.update(value=1, minimum=1, maximum=1, visible=False),
            gr.update(value="Positive", visible=True),
            gr.update(choices=[], value=[], visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=[], visible=False),
            gr.update(value="Image loaded. Click to assign points, then press Add Mask. Mask Selection will fill after you add a mask."),
        )

    def select_media_frame(
        slider_value: int,
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load media first.")
        selected_index = max(0, int(slider_value) - 1)
        media_state["select_frame_number"] = selected_index
        prepare_sam_frame(sam_generator, media_state, selected_index, force=True)
        return media_state["painted_images"][selected_index], media_state, interactive_state

    def select_image_template(
        _refine_iter: int,
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load media first.")
        media_state["select_frame_number"] = 0
        prepare_sam_frame(sam_generator, media_state, 0, force=True)
        return media_state["painted_images"][0], media_state, interactive_state

    def set_track_end(
        slider_value: int,
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load media first.")
        selected_index = max(0, min(len(media_state["origin_images"]) - 1, int(slider_value) - 1))
        interactive_state["track_end_number"] = selected_index
        return media_state["painted_images"][selected_index], interactive_state

    def sam_refine(
        media_state: dict[str, Any],
        point_prompt: str,
        click_state: list[list[Any]],
        interactive_state: dict[str, Any],
        evt: gr.SelectData,
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load media first.")
        if point_prompt == "Positive":
            coordinate = f"[[{evt.index[0]},{evt.index[1]},1]]"
            interactive_state["positive_click_times"] += 1
        else:
            coordinate = f"[[{evt.index[0]},{evt.index[1]},0]]"
            interactive_state["negative_click_times"] += 1

        prompt = get_prompt(click_state, coordinate)
        selected_frame = media_state["select_frame_number"]
        mask, logit, painted_image = apply_sam_points(
            sam_generator,
            media_state,
            prompt["input_point"],
            prompt["input_label"],
            frame_index=selected_frame,
            multimask=prompt["multimask_output"],
        )
        media_state["masks"][selected_frame] = mask
        media_state["logits"][selected_frame] = logit
        media_state["painted_images"][selected_frame] = painted_image
        return painted_image, media_state, interactive_state

    def show_mask(
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
        mask_dropdown: list[str],
    ):
        if not media_state.get("origin_images"):
            return None
        selected_frame = media_state["origin_images"][media_state["select_frame_number"]]
        preview = np.asarray(selected_frame).copy()
        for mask_name in sorted(mask_dropdown or []):
            mask_number = int(mask_name.split("_")[1]) - 1
            mask = interactive_state["multi_mask"]["masks"][mask_number]
            preview = mask_painter(preview, mask.astype("uint8"), mask_color=mask_number + 2)
        return preview

    def add_multi_mask(
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
        mask_dropdown: list[str],
    ):
        current_mask = media_state["masks"][media_state["select_frame_number"]]
        interactive_state["multi_mask"]["masks"].append(current_mask)
        new_name = f"mask_{len(interactive_state['multi_mask']['masks']):03d}"
        interactive_state["multi_mask"]["mask_names"].append(new_name)
        selected_masks = list(mask_dropdown or [])
        selected_masks.append(new_name)
        preview = show_mask(media_state, interactive_state, selected_masks)
        return (
            interactive_state,
            gr.update(
                choices=interactive_state["multi_mask"]["mask_names"],
                value=selected_masks,
                visible=True,
            ),
            preview,
            [[], []],
        )

    def remove_multi_mask(interactive_state: dict[str, Any]):
        interactive_state["multi_mask"]["mask_names"] = []
        interactive_state["multi_mask"]["masks"] = []
        return interactive_state, gr.update(choices=[], value=[], visible=True)

    def clear_clicks(media_state: dict[str, Any]):
        if not media_state.get("origin_images"):
            return None, [[], []]
        template_frame = media_state["origin_images"][media_state["select_frame_number"]]
        return template_frame, [[], []]

    def build_selected_mask(
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
        mask_dropdown: list[str],
    ):
        template_mask = compose_selected_mask(
            media_state["masks"][media_state["select_frame_number"]],
            interactive_state["multi_mask"]["masks"],
            mask_dropdown,
        )
        if interactive_state["multi_mask"]["masks"]:
            media_state["masks"][media_state["select_frame_number"]] = template_mask
        return template_mask

    def video_matting(
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
        mask_dropdown: list[str],
        erode_kernel_size: int,
        dilate_kernel_size: int,
        model_selection: str,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load a video first.")
        yield (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(value="Preparing video matting..."),
        )
        _push_progress(progress, 0.05, "Loading the selected model...")
        sam_generator.release()
        selected_model = load_runtime_model(model_selection)
        _push_progress(progress, 0.2, "Building the selected mask...")
        template_mask = build_selected_mask(media_state, interactive_state, mask_dropdown)
        _push_progress(progress, 0.35, "Running MatAnyone video matting...")
        foreground, alpha, _runtime_profile = run_matting(
            selected_model,
            media_state,
            template_mask,
            performance_profile,
            device_name,
            erode_kernel_size=erode_kernel_size,
            dilate_kernel_size=dilate_kernel_size,
        )
        _push_progress(progress, 0.78, "Saving foreground and alpha videos...")
        run_output_dir = create_run_output_dir(
            str(results_root / "matanyone_video"),
            media_state,
        )
        source_name = media_state.get("video_name") or "output.mp4"
        save_cli_outputs(
            run_output_dir,
            source_name,
            media_state.get("source_size"),
            template_mask.astype("uint8"),
            _as_pil_image(media_state["painted_images"][media_state["select_frame_number"]]),
            foreground,
            alpha,
            True,
            fps=media_state["fps"],
            audio_path=media_state.get("audio") or "",
        )
        _push_progress(progress, 0.92, "Writing debug artifacts...")
        debug_dir = export_debug_artifacts(
            run_output_dir,
            media_state,
            template_mask,
            foreground,
            alpha,
            device_name=device_name,
            performance_profile=performance_profile,
            model_name=model_selection,
        )
        stem = Path(source_name).stem
        foreground_path = Path(run_output_dir) / f"{stem}_foreground.mp4"
        alpha_path = Path(run_output_dir) / f"{stem}_alpha.mp4"
        metadata_path = Path(run_output_dir) / "metadata.json"
        export_state = {
            "run_output_dir": run_output_dir,
            "foreground_path": str(foreground_path),
            "alpha_path": str(alpha_path),
            "source_name": source_name,
            "fps": media_state.get("fps"),
        }
        file_list = _collect_existing_files([foreground_path, alpha_path, metadata_path])
        status = f"Saved video outputs to {run_output_dir}\nDebug artifacts: {debug_dir}"
        _push_progress(progress, 1.0, "Video matting complete")
        yield (
            gr.update(value=str(foreground_path), visible=True),
            gr.update(value=str(alpha_path), visible=True),
            gr.update(value=file_list, visible=True),
            export_state,
            gr.update(visible=True),
            gr.update(value=status),
        )

    def image_matting(
        media_state: dict[str, Any],
        interactive_state: dict[str, Any],
        mask_dropdown: list[str],
        erode_kernel_size: int,
        dilate_kernel_size: int,
        refine_iter: int,
        model_selection: str,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load an image first.")
        yield (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(value="Preparing image matting..."),
        )
        _push_progress(progress, 0.05, "Loading the selected model...")
        sam_generator.release()
        selected_model = load_runtime_model(model_selection)
        _push_progress(progress, 0.2, "Building the selected mask...")
        template_mask = build_selected_mask(media_state, interactive_state, mask_dropdown)
        _push_progress(progress, 0.4, "Running MatAnyone image matting...")
        foreground, alpha, _runtime_profile = run_matting(
            selected_model,
            media_state,
            template_mask,
            performance_profile,
            device_name,
            erode_kernel_size=erode_kernel_size,
            dilate_kernel_size=dilate_kernel_size,
            refine_iter=refine_iter,
        )
        _push_progress(progress, 0.82, "Saving image outputs...")
        run_output_dir = create_run_output_dir(
            str(results_root / "matanyone_image"),
            media_state,
        )
        source_name = media_state.get("image_name") or "output.png"
        save_cli_outputs(
            run_output_dir,
            source_name,
            media_state.get("source_size"),
            template_mask.astype("uint8"),
            _as_pil_image(media_state["painted_images"][media_state["select_frame_number"]]),
            foreground,
            alpha,
            False,
        )
        debug_dir = export_debug_artifacts(
            run_output_dir,
            media_state,
            template_mask,
            foreground,
            alpha,
            device_name=device_name,
            performance_profile=performance_profile,
            model_name=model_selection,
        )
        stem = Path(source_name).stem
        foreground_path = Path(run_output_dir) / f"{stem}_foreground.png"
        alpha_path = Path(run_output_dir) / f"{stem}_alpha.png"
        foreground_frame = resize_output_frame(foreground[-1], media_state.get("source_size"))
        alpha_frame = resize_output_frame(alpha[-1], media_state.get("source_size"))
        foreground_pil = Image.fromarray(foreground_frame)
        alpha_pil = Image.fromarray(alpha_frame[:, :, 0])
        webp_path = Path(run_output_dir) / f"{stem}_foreground.webp"
        foreground_pil.save(webp_path, format="WEBP", quality=95)
        file_list = _collect_existing_files(
            [foreground_path, webp_path, alpha_path, Path(run_output_dir) / "metadata.json"]
        )
        status = f"Saved image outputs to {run_output_dir}\nDebug artifacts: {debug_dir}"
        _push_progress(progress, 1.0, "Image matting complete")
        yield (
            gr.update(value=foreground_pil, visible=True),
            gr.update(value=alpha_pil, visible=True),
            gr.update(value=file_list, visible=True),
            gr.update(value=status),
        )

    def export_video_results(
        export_state: dict[str, Any],
        export_mode: str,
        output_fps: int,
        max_frames: int | float | None,
        interval_seconds: float,
        size_text: str,
        corner_radius: int,
        background_preset: str,
        background_custom: str,
        background_image: str | None,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not export_state or not export_state.get("foreground_path"):
            raise gr.Error("Run video matting first.")
        yield gr.update(value=[], visible=False), gr.update(
            value=f"Preparing export: {export_mode}..."
        )
        _push_progress(progress, 0.05, "Preparing export settings...")

        foreground_path = export_state["foreground_path"]
        alpha_path = export_state["alpha_path"]
        source_name = export_state["source_name"]
        export_dir = Path(export_state["run_output_dir"]) / "exports" / _timestamp_token()
        export_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(source_name).stem
        output_size = _safe_output_size(size_text)
        max_frames_value = _safe_max_frames(max_frames)
        interval_value = _safe_interval_seconds(interval_seconds)
        fps_value = max(1, int(output_fps))
        radius_value = max(0, int(corner_radius))
        bg_color = _resolve_background_color(background_preset, background_custom)

        exported_paths: list[str] = []

        if export_mode == "animated_webp":
            _push_progress(progress, 0.2, "Rendering animated WebP...")
            output_path = export_dir / f"{stem}_transparent.webp"
            remover.to_animated_from_mask_pair(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_path=str(output_path),
                fps=fps_value,
                max_frames=max_frames_value,
                format="webp",
                output_size=output_size,
                corner_radius=radius_value,
            )
            exported_paths.append(str(output_path))
        elif export_mode == "animated_gif":
            _push_progress(progress, 0.2, "Rendering animated GIF...")
            output_path = export_dir / f"{stem}_transparent.gif"
            remover.to_animated_from_mask_pair(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_path=str(output_path),
                fps=fps_value,
                max_frames=max_frames_value,
                format="gif",
                output_size=output_size,
                corner_radius=radius_value,
            )
            exported_paths.append(str(output_path))
        elif export_mode == "animated_both":
            _push_progress(progress, 0.2, "Rendering animated WebP and GIF...")
            for fmt in ("webp", "gif"):
                output_path = export_dir / f"{stem}_transparent.{fmt}"
                remover.to_animated_from_mask_pair(
                    fg_video_path=foreground_path,
                    alpha_video_path=alpha_path,
                    output_path=str(output_path),
                    fps=fps_value,
                    max_frames=max_frames_value,
                    format=fmt,
                    output_size=output_size,
                    corner_radius=radius_value,
                )
                exported_paths.append(str(output_path))
        elif export_mode == "frames_webp":
            _push_progress(progress, 0.2, "Rendering transparent WebP frames...")
            frame_dir = export_dir / f"{stem}_frames_webp"
            remover.extract_matanyone_frames_interval(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_dir=str(frame_dir),
                interval_sec=interval_value,
                format="webp",
                output_size=output_size,
                corner_radius=radius_value,
            )
            exported_paths.append(_zip_paths([frame_dir], export_dir / f"{frame_dir.name}.zip"))
        elif export_mode == "frames_png":
            _push_progress(progress, 0.2, "Rendering transparent PNG frames...")
            frame_dir = export_dir / f"{stem}_frames_png"
            remover.extract_matanyone_frames_interval(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_dir=str(frame_dir),
                interval_sec=interval_value,
                format="png",
                output_size=output_size,
                corner_radius=radius_value,
            )
            exported_paths.append(_zip_paths([frame_dir], export_dir / f"{frame_dir.name}.zip"))
        elif export_mode == "video_webm":
            _push_progress(progress, 0.2, "Encoding transparent WebM...")
            output_path = export_dir / f"{stem}_transparent.webm"
            remover.process_matanyone_video(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_path=str(output_path),
                fps=fps_value,
                keep_frames=False,
                output_size=output_size,
            )
            exported_paths.append(str(output_path))
        elif export_mode == "video_mp4":
            _push_progress(progress, 0.2, "Encoding flattened MP4...")
            output_path = export_dir / f"{stem}_flattened.mp4"
            remover.process_matanyone_video(
                fg_video_path=foreground_path,
                alpha_video_path=alpha_path,
                output_path=str(output_path),
                fps=fps_value,
                bg_color=bg_color,
                bg_image_path=background_image,
                keep_frames=False,
                output_size=output_size,
            )
            exported_paths.append(str(output_path))
        else:
            raise gr.Error(f"Unsupported export mode: {export_mode}")

        status = f"Export complete: {export_mode}\nSaved under {export_dir}"
        _push_progress(progress, 1.0, "Export complete")
        yield gr.update(value=_collect_existing_files(exported_paths), visible=True), gr.update(value=status)

    # ========== MatAnyone2 Tab Functions (from MatAnyone app.py) ==========

    def get_frames_from_video_v2(
        video_input: str,
        video_state: dict,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Extract frames from uploaded video - MatAnyone2 version."""
        _push_progress(progress, 0.05, "Opening video...")
        video_state, video_info, _runtime_profile = load_video_state(
            video_input, device_name, performance_profile
        )
        _push_progress(progress, 0.7, "Preparing the first frame...")
        prepare_sam_frame(sam_generator, video_state, 0, force=True)
        frame_count = len(video_state["origin_images"])
        _push_progress(progress, 1.0, "Video ready")
        return (
            video_state,
            video_info,
            video_state["origin_images"][0],
            gr.update(visible=True, maximum=frame_count, value=1),
            gr.update(visible=False, maximum=frame_count, value=frame_count),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(
                value=(
                    "Video loaded. Add a positive point, save a mask, and run Video Matting. "
                    "When matting finishes, this tab will also create animated WebP and GIF files."
                )
            ),
        )

    def get_frames_from_image_v2(
        image_input: np.ndarray,
        image_state: dict,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Extract frames from uploaded image - MatAnyone2 version."""
        _push_progress(progress, 0.05, "Opening image...")
        image_state, image_info, _runtime_profile = load_image_state(
            image_input, device_name, performance_profile
        )
        _push_progress(progress, 0.7, "Preparing the interactive preview...")
        prepare_sam_frame(sam_generator, image_state, 0, force=True)
        frame_count = len(image_state["origin_images"])
        _push_progress(progress, 1.0, "Image ready")
        return (
            image_state,
            image_info,
            image_state["origin_images"][0],
            gr.update(visible=True, maximum=10, value=10),
            gr.update(visible=False, maximum=frame_count, value=frame_count),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
        )

    def select_video_template_v2(slider_value: int, video_state: dict, interactive_state: dict):
        """Select frame from video slider - MatAnyone2 version."""
        selected_index = max(0, int(slider_value) - 1)
        video_state["select_frame_number"] = selected_index
        prepare_sam_frame(sam_generator, video_state, selected_index, force=True)
        return video_state["painted_images"][selected_index], video_state, interactive_state

    def select_image_template_v2(refine_iter: int, image_state: dict, interactive_state: dict):
        """Select template for image - MatAnyone2 version."""
        image_state["select_frame_number"] = 0
        prepare_sam_frame(sam_generator, image_state, 0, force=True)
        return image_state["painted_images"][0], image_state, interactive_state

    def get_end_number_v2(slider_value: int, video_state: dict, interactive_state: dict):
        """Set tracking end frame - MatAnyone2 version."""
        interactive_state["track_end_number"] = slider_value
        return video_state["painted_images"][slider_value], interactive_state

    def sam_refine_v2(video_state: dict, point_prompt: str, click_state: list, interactive_state: dict, evt: gr.SelectData):
        """Use SAM to get mask - MatAnyone2 version."""
        if point_prompt == "Positive":
            coordinate = "[[{},{},1]]".format(evt.index[0], evt.index[1])
            interactive_state["positive_click_times"] += 1
        else:
            coordinate = "[[{},{},0]]".format(evt.index[0], evt.index[1])
            interactive_state["negative_click_times"] += 1

        selected_frame = video_state["select_frame_number"]
        import json
        inputs = json.loads(coordinate)
        points = click_state[0]
        labels = click_state[1]
        for inp in inputs:
            points.append(inp[:2])
            labels.append(inp[2])
        click_state[0] = points
        click_state[1] = labels

        mask, logit, painted_image = apply_sam_points(
            sam_generator,
            video_state,
            points,
            labels,
            frame_index=selected_frame,
            multimask="True",
        )
        video_state["masks"][selected_frame] = mask
        video_state["logits"][selected_frame] = logit
        video_state["painted_images"][selected_frame] = painted_image
        return painted_image, video_state, interactive_state

    def add_multi_mask_v2(video_state: dict, interactive_state: dict, mask_dropdown: list):
        """Add mask to multi-mask list - MatAnyone2 version."""
        mask = video_state["masks"][video_state["select_frame_number"]]
        interactive_state["multi_mask"]["masks"].append(mask)
        interactive_state["multi_mask"]["mask_names"].append(
            "mask_{:03d}".format(len(interactive_state["multi_mask"]["masks"]))
        )
        mask_dropdown.append("mask_{:03d}".format(len(interactive_state["multi_mask"]["masks"])))
        select_frame = show_mask_v2(video_state, interactive_state, mask_dropdown)
        return (
            interactive_state,
            gr.update(choices=interactive_state["multi_mask"]["mask_names"], value=mask_dropdown),
            select_frame,
            [[], []],
        )

    def clear_click_v2(video_state: dict, click_state: list):
        """Clear click state - MatAnyone2 version."""
        click_state = [[], []]
        template_frame = video_state["origin_images"][video_state["select_frame_number"]]
        return template_frame, click_state

    def remove_multi_mask_v2(interactive_state: dict, mask_dropdown: list):
        """Remove all masks - MatAnyone2 version."""
        interactive_state["multi_mask"]["mask_names"] = []
        interactive_state["multi_mask"]["masks"] = []
        return interactive_state, gr.update(choices=[], value=[])

    def show_mask_v2(video_state: dict, interactive_state: dict, mask_dropdown: list):
        """Show selected masks - MatAnyone2 version."""
        mask_dropdown.sort()
        if video_state["origin_images"]:
            select_frame = video_state["origin_images"][video_state["select_frame_number"]]
            for i in range(len(mask_dropdown)):
                mask_number = int(mask_dropdown[i].split("_")[1]) - 1
                mask = interactive_state["multi_mask"]["masks"][mask_number]
                select_frame = mask_painter(select_frame, mask.astype("uint8"), mask_color=mask_number + 2)
            return select_frame
        return None

    def video_matting_v2(
        video_state: dict,
        interactive_state: dict,
        mask_dropdown: list,
        erode_kernel_size: int,
        dilate_kernel_size: int,
        model_selection: str,
        performance_profile: str,
        export_fps: int,
        export_max_frames: int,
        export_bounce: bool,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Video matting - MatAnyone2 version using generate_video_from_frames."""
        if not video_state.get("origin_images"):
            raise gr.Error("Load a video first.")

        yield (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(value="Preparing MatAnyone video matting and animated exports..."),
        )
        _push_progress(progress, 0.05, "Loading the selected model...")
        sam_generator.release()
        try:
            selected_model = load_runtime_model(model_selection)
        except (FileNotFoundError, ValueError) as e:
            if available_models:
                print(f"Warning: {str(e)}. Using {available_models[0]} instead.")
                selected_model = load_runtime_model(available_models[0])
            else:
                raise ValueError("No models are available! Please check if the model files exist.")

        _push_progress(progress, 0.2, "Building the selected mask...")
        template_mask = compose_selected_mask(
            video_state["masks"][video_state["select_frame_number"]],
            interactive_state["multi_mask"]["masks"],
            mask_dropdown,
        )
        if interactive_state["multi_mask"]["masks"]:
            video_state["masks"][video_state["select_frame_number"]] = template_mask

        fps = video_state["fps"]
        audio_path = video_state.get("audio", "")

        _push_progress(progress, 0.35, "Running MatAnyone video matting...")
        foreground, alpha, _runtime_profile = run_matting(
            selected_model,
            video_state,
            template_mask,
            performance_profile,
            device_name,
            erode_kernel_size=erode_kernel_size,
            dilate_kernel_size=dilate_kernel_size,
        )

        target_size = video_state.get("source_size")
        run_output_dir = create_run_output_dir(str(results_root / "matanyone2_video"), video_state)
        video_name = video_state.get("video_name") or "output"

        _push_progress(progress, 0.8, "Encoding foreground and alpha videos...")
        foreground_output = generate_video_from_frames(
            foreground,
            output_path=str(Path(run_output_dir) / f"{video_name}_fg.mp4"),
            fps=fps,
            audio_path=audio_path,
            target_size=target_size,
        )
        alpha_output = generate_video_from_frames(
            alpha,
            output_path=str(Path(run_output_dir) / f"{video_name}_alpha.mp4"),
            fps=fps,
            gray2rgb=True,
            audio_path=audio_path,
            target_size=target_size,
        )
        _push_progress(progress, 0.94, "Saving debug artifacts...")
        debug_dir = export_debug_artifacts(
            run_output_dir,
            video_state,
            template_mask,
            foreground,
            alpha,
            device_name=device_name,
            performance_profile=performance_profile,
            model_name=model_selection,
        )
        print(f"Saved debug artifacts to {debug_dir}")
        print(f"[Video Matting] Foreground: {foreground_output}")
        print(f"[Video Matting] Alpha: {alpha_output}")
        _push_progress(progress, 0.97, "Rendering animated WebP and GIF...")

        bg_remover = VideoBackgroundRemover()
        stem = Path(video_name).stem
        webp_output = str(Path(run_output_dir) / f"{stem}_animated.webp")
        gif_output = str(Path(run_output_dir) / f"{stem}_animated.gif")
        bg_remover.to_animated_from_mask_pair(
            fg_video_path=str(foreground_output),
            alpha_video_path=str(alpha_output),
            output_path=webp_output,
            fps=max(1, int(export_fps)),
            max_frames=_safe_max_frames(export_max_frames),
            output_size=None,
            format="webp",
            bounce=export_bounce,
        )
        bg_remover.to_animated_from_mask_pair(
            fg_video_path=str(foreground_output),
            alpha_video_path=str(alpha_output),
            output_path=gif_output,
            fps=max(1, int(export_fps)),
            max_frames=_safe_max_frames(export_max_frames),
            output_size=None,
            format="gif",
            bounce=export_bounce,
        )
        _push_progress(progress, 1.0, "Video matting and animated exports complete")
        yield (
            gr.update(value=foreground_output, visible=True),
            gr.update(value=alpha_output, visible=True),
            gr.update(value=webp_output, visible=True),
            gr.update(value=gif_output, visible=True),
            gr.update(
                value=(
                    "Done. MatAnyone video matting finished and animated previews were exported.\n"
                    f"Foreground: {foreground_output}\n"
                    f"Alpha: {alpha_output}\n"
                    f"WebP: {webp_output}\n"
                    f"GIF: {gif_output}\n"
                    f"Debug artifacts: {debug_dir}"
                )
            ),
        )

    def export_to_webp_v2(
        fg_video_path: str,
        alpha_video_path: str,
        fps: int = 10,
        max_frames: int = 150,
        output_size: tuple = None,
        bounce: bool = False,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Export MatAnyone2 result to animated WebP."""
        if not fg_video_path or not alpha_video_path:
            raise gr.Error("Run Video Matting first to generate output videos.")

        yield (
            gr.update(),
            gr.update(value="Preparing animated WebP export..."),
        )
        _push_progress(progress, 0.05, "Preparing animated WebP export...")
        print(f"[WebP Export] Starting export...")
        print(f"[WebP Export] FG: {fg_video_path}")
        print(f"[WebP Export] Alpha: {alpha_video_path}")
        print(f"[WebP Export] FPS: {fps}, Max frames: {max_frames}")
        print(f"[WebP Export] Bounce: {bounce}")

        bg_remover = VideoBackgroundRemover()
        output_path = str(Path(fg_video_path).parent / f"{Path(fg_video_path).stem}_animated.webp")
        print(f"[WebP Export] Output: {output_path}")

        _push_progress(progress, 0.2, "Rendering animated WebP...")
        bg_remover.to_animated_from_mask_pair(
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            output_path=output_path,
            fps=fps,
            max_frames=max_frames,
            output_size=output_size,
            format="webp",
            bounce=bounce,
        )
        print(f"[WebP Export] Done!")
        _push_progress(progress, 1.0, "Animated WebP export complete")
        yield (
            gr.update(value=output_path, visible=True),
            gr.update(value=f"Animated WebP exported to {output_path}"),
        )

    def export_to_gif_v2(
        fg_video_path: str,
        alpha_video_path: str,
        fps: int = 10,
        max_frames: int = 150,
        output_size: tuple = None,
        bounce: bool = False,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Export MatAnyone2 result to animated GIF.

        Args:
            bounce: If True, add reversed frames at the end for ping-pong loop effect.
        """
        if not fg_video_path or not alpha_video_path:
            raise gr.Error("Run Video Matting first to generate output videos.")

        yield (
            gr.update(),
            gr.update(value="Preparing animated GIF export..."),
        )
        _push_progress(progress, 0.05, "Preparing animated GIF export...")
        print(f"[GIF Export] Starting export...")
        print(f"[GIF Export] FG: {fg_video_path}")
        print(f"[GIF Export] Alpha: {alpha_video_path}")
        print(f"[GIF Export] FPS: {fps}, Max frames: {max_frames}")
        print(f"[GIF Export] Bounce: {bounce}")

        bg_remover = VideoBackgroundRemover()
        output_path = str(Path(fg_video_path).parent / f"{Path(fg_video_path).stem}_animated.gif")
        print(f"[GIF Export] Output: {output_path}")

        _push_progress(progress, 0.2, "Rendering animated GIF...")
        bg_remover.to_animated_from_mask_pair(
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            output_path=output_path,
            fps=fps,
            max_frames=max_frames,
            output_size=output_size,
            format="gif",
            bounce=bounce,
        )
        print(f"[GIF Export] Done!")
        _push_progress(progress, 1.0, "Animated GIF export complete")
        yield (
            gr.update(value=output_path, visible=True),
            gr.update(value=f"Animated GIF exported to {output_path}"),
        )

    def image_matting_v2(
        image_state: dict,
        interactive_state: dict,
        mask_dropdown: list,
        erode_kernel_size: int,
        dilate_kernel_size: int,
        refine_iter: int,
        model_selection: str,
        performance_profile: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Image matting - MatAnyone2 version."""
        if not image_state.get("origin_images"):
            raise gr.Error("Load an image first.")

        _push_progress(progress, 0.05, "Loading the selected model...")
        sam_generator.release()
        try:
            selected_model = load_runtime_model(model_selection)
        except (FileNotFoundError, ValueError) as e:
            if available_models:
                print(f"Warning: {str(e)}. Using {available_models[0]} instead.")
                selected_model = load_runtime_model(available_models[0])
            else:
                raise ValueError("No models are available! Please check if the model files exist.")

        _push_progress(progress, 0.2, "Building the selected mask...")
        template_mask = compose_selected_mask(
            image_state["masks"][image_state["select_frame_number"]],
            interactive_state["multi_mask"]["masks"],
            mask_dropdown,
        )
        if interactive_state["multi_mask"]["masks"]:
            image_state["masks"][image_state["select_frame_number"]] = template_mask

        _push_progress(progress, 0.4, "Running MatAnyone image matting...")
        foreground, alpha, _runtime_profile = run_matting(
            selected_model,
            image_state,
            template_mask,
            performance_profile,
            device_name,
            erode_kernel_size=erode_kernel_size,
            dilate_kernel_size=dilate_kernel_size,
            refine_iter=refine_iter,
        )

        _push_progress(progress, 0.82, "Saving image outputs...")
        target_size = image_state.get("source_size")
        foreground_frame = resize_output_frame(foreground[-1], target_size, interpolation=cv2.INTER_LINEAR)
        alpha_frame = resize_output_frame(alpha[-1], target_size, interpolation=cv2.INTER_LINEAR)
        foreground_output = Image.fromarray(foreground_frame)
        alpha_output = Image.fromarray(alpha_frame[:, :, 0])

        run_output_dir = create_run_output_dir(str(results_root / "matanyone2_image"), image_state)
        save_cli_outputs(
            run_output_dir,
            image_state.get("image_name") or "output.png",
            target_size,
            template_mask.astype("uint8"),
            image_state["painted_images"][image_state["select_frame_number"]],
            foreground,
            alpha,
            False,
        )
        debug_dir = export_debug_artifacts(
            run_output_dir,
            image_state,
            template_mask,
            foreground,
            alpha,
            device_name=device_name,
            performance_profile=performance_profile,
            model_name=model_selection,
        )
        print(f"Saved debug artifacts to {debug_dir}")
        _push_progress(progress, 1.0, "Image matting complete")
        return foreground_output, alpha_output

    def restart_v2():
        """Reset all states for new input - MatAnyone2 version."""
        media_state, interactive_state = create_empty_media_state(args.performance_profile, False)
        return (
            media_state,
            interactive_state,
            [[], []],
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False, choices=[], value=[]),
            "",
            gr.update(visible=False),
        )

    # ========== End MatAnyone2 Tab Functions ==========

    def run_cli_export(
        source_mode: str,
        upload_input_path: str | None,
        manual_input_path: str,
        upload_alpha_path: str | None,
        manual_alpha_path: str,
        output_path_text: str,
        export_mode: str,
        video_format: str,
        animated_format: str,
        frame_format: str,
        rembg_model: str,
        background_preset: str,
        background_custom: str,
        background_image_path: str | None,
        output_size_text: str,
        regular_fps: int | float | None,
        animated_fps: int | float,
        max_frames: int | float | None,
        interval_seconds: float,
        keep_frames: bool,
        work_dir_text: str,
        no_bg_removal: bool,
        corner_radius: int,
        matanyone_root_text: str,
        matanyone_python_text: str,
        matanyone_model_name: str,
        matanyone_device_name: str,
        matanyone_profile_name: str,
        matanyone_sam_name: str,
        matanyone_cpu_threads: int | float | None,
        matanyone_frame_limit: int | float | None,
        matanyone_video_target_fps: float | None,
        matanyone_output_fps: float | None,
        matanyone_select_frame: int | float,
        matanyone_end_frame: int | float | None,
        positive_points_text: str,
        negative_points_text: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        yield (
            gr.update(value=""),
            gr.update(value="Validating input and preparing the export..."),
        )
        _push_progress(progress, 0.05, "Preparing export request...")
        input_path = _resolve_preferred_path(upload_input_path, manual_input_path)
        if not input_path:
            raise gr.Error("Input path is required.")

        alpha_path = _resolve_preferred_path(upload_alpha_path, manual_alpha_path)
        output_path_value = (output_path_text or "").strip()
        base_dir = results_root / "cli_runs" / _timestamp_token()
        if not output_path_value:
            output_path_value = _build_cli_output_target(
                base_dir,
                input_path,
                source_mode,
                export_mode,
                animated_format,
                frame_format,
                video_format,
            )

        try:
            output_size = _safe_output_size(output_size_text)
            bg_color = _resolve_background_color(background_preset, background_custom)
            positive_points = _parse_points_text(positive_points_text)
            negative_points = _parse_points_text(negative_points_text)
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc

        if source_mode == "matanyone_pair":
            try:
                resolved_fg, resolved_alpha = resolve_matanyone_inputs(
                    input_path,
                    alpha_video=alpha_path or None,
                )
            except ValueError as exc:
                raise gr.Error(str(exc)) from exc
            input_path_for_output = resolved_fg
        else:
            resolved_fg = None
            resolved_alpha = None
            input_path_for_output = input_path
        regular_backend = "matanyone" if source_mode == "matanyone_backend" else "rembg"

        request = ExportRequest(
            input_path=input_path if source_mode != "matanyone_pair" else input_path_for_output,
            output_path=output_path_value,
            model_name=rembg_model,
            backend_name=regular_backend if source_mode != "matanyone_pair" else "rembg",
            use_matanyone_pair=(source_mode == "matanyone_pair"),
            alpha_video_path=resolved_alpha if source_mode == "matanyone_pair" else None,
            matanyone_root=(matanyone_root_text or "").strip() or None,
            matanyone_python=(matanyone_python_text or "").strip() or None,
            matanyone_model_name=matanyone_model_name,
            matanyone_device=matanyone_device_name,
            matanyone_performance_profile=matanyone_profile_name,
            matanyone_sam_model_type=matanyone_sam_name,
            matanyone_cpu_threads=int(matanyone_cpu_threads) if matanyone_cpu_threads not in (None, "") else None,
            matanyone_frame_limit=int(matanyone_frame_limit) if matanyone_frame_limit not in (None, "") else None,
            matanyone_video_target_fps=float(matanyone_video_target_fps or 0.0),
            matanyone_output_fps=float(matanyone_output_fps) if matanyone_output_fps not in (None, "") else None,
            matanyone_select_frame=int(matanyone_select_frame or 0),
            matanyone_end_frame=int(matanyone_end_frame) if matanyone_end_frame not in (None, "") else None,
            positive_points=positive_points,
            negative_points=negative_points,
            fps=int(regular_fps) if regular_fps not in (None, "", 0) else None,
            bg_color_text=None if bg_color is None else ",".join(str(value) for value in bg_color),
            bg_image_path=background_image_path,
            size_text=f"{output_size[0]}x{output_size[1]}" if output_size else None,
            keep_frames=bool(keep_frames),
            work_dir=(work_dir_text or "").strip() or None,
            interval_seconds=_safe_interval_seconds(interval_seconds) if export_mode == "interval" else None,
            output_format=frame_format if export_mode == "interval" else "mp4",
            animated_format=animated_format if export_mode == "animated" else None,
            animated_fps=max(1, int(animated_fps or 10)),
            max_frames=_safe_max_frames(max_frames),
            no_bg_removal=bool(no_bg_removal),
            corner_radius=max(0, int(corner_radius)),
        )

        if export_mode == "video" and source_mode == "matanyone_pair" and video_format == "webm":
            request.output_path = output_path_value
        elif export_mode == "video" and video_format == "webm":
            raise gr.Error("Regular video export to .webm is only supported for MatAnyone foreground+alpha pairs.")

        if export_mode == "interval":
            request.output_format = frame_format
        elif export_mode == "animated":
            request.output_format = (
                animated_format if animated_format in {"webp", "gif"} else "webp"
            )
        else:
            request.output_format = video_format

        context = ExportServiceContext(
            remover_factory=VideoBackgroundRemover,
            matanyone_runner_factory=MatAnyoneRunner,
            resolve_matanyone_root=resolve_matanyone_root,
            resolve_matanyone_python=resolve_matanyone_python,
        )

        try:
            _push_progress(progress, 0.2, "Running the selected export...")
            execute_export(request, context=context)
        except Exception as exc:
            yield (
                gr.update(value=""),
                gr.update(value=f"Error: {exc}"),
            )
            return

        collected_paths: list[str] = []
        output_path = Path(request.output_path)
        if export_mode == "animated":
            output_root = output_path.with_suffix("")
            formats = ["webp", "gif"] if animated_format == "both" else [animated_format]
            collected_paths.extend(
                str(output_root.with_suffix(f".{fmt}")) for fmt in formats
            )
        elif export_mode == "interval":
            frame_dir = Path(f"{request.output_path}_{frame_format}")
            if frame_dir.exists():
                collected_paths.append(_zip_paths([frame_dir], frame_dir.with_suffix(".zip")))
        else:
            collected_paths.append(str(output_path))

        status_lines = [
            f"Source mode: {source_mode}",
            f"Backend: {request.backend_name}",
            f"Export mode: {export_mode}",
            f"Saved target: {request.output_path}",
        ]
        _push_progress(progress, 1.0, "Export complete")
        yield (
            gr.update(value="\n".join(_collect_existing_files(collected_paths))),
            gr.update(value="\n".join(status_lines)),
        )

    default_matanyone_python = str(resolve_matanyone_python(matanyone_root, args.matanyone_python))

    def build_cli_export_tab(
        *,
        tab_label: str,
        source_mode_value: str,
        description: str,
        manual_input_placeholder: str,
        examples: list[list[Any]],
        show_alpha_inputs: bool = False,
        manual_alpha_placeholder: str = r"D:\path\to\clip_alpha.mp4",
        show_matanyone_settings: bool = False,
    ) -> None:
        with gr.TabItem(tab_label):
            gr.Markdown(description)

            source_mode_state = gr.State(source_mode_value)

            with gr.Row():
                cli_export_mode = gr.Radio(
                    choices=[
                        ("Regular Video Output", "video"),
                        ("Animated Output", "animated"),
                        ("Frame Extraction", "interval"),
                    ],
                    value="video",
                    label="Export Mode",
                )

            with gr.Row():
                cli_input_upload = gr.File(type="filepath", label="Input File")
                cli_input_path = gr.Textbox(
                    label="Or Manual Input Path",
                    placeholder=manual_input_placeholder,
                )

            if show_alpha_inputs:
                with gr.Row():
                    cli_alpha_upload: Any = gr.File(type="filepath", label="Alpha Video")
                    cli_alpha_path: Any = gr.Textbox(
                        label="Or Manual Alpha Path",
                        placeholder=manual_alpha_placeholder,
                    )
            else:
                cli_alpha_upload = gr.State(None)
                cli_alpha_path = gr.State("")

            cli_output_path = gr.Textbox(
                label="Output Path (optional)",
                placeholder=r"Leave blank to auto-save under output\webui\cli_runs",
            )

            with gr.Accordion("General Output Settings", open=True):
                with gr.Row():
                    cli_video_format = gr.Dropdown(
                        choices=["mp4", "webm"],
                        value="mp4",
                        label="Regular Video Format",
                    )
                    cli_animated_format = gr.Dropdown(
                        choices=["webp", "gif", "both"],
                        value="webp",
                        label="Animated Format",
                    )
                    cli_frame_format = gr.Dropdown(
                        choices=["webp", "png"],
                        value="webp",
                        label="Frame Format",
                    )
                with gr.Row():
                    cli_regular_fps = gr.Number(value=0, precision=0, label="Video FPS Override (0 = input)")
                    cli_animated_fps = gr.Number(value=10, precision=0, label="Animated FPS")
                    cli_max_frames = gr.Number(value=0, precision=0, label="Max Frames (0 = all)")
                    cli_interval = gr.Number(value=1.0, label="Frame Interval Seconds")
                with gr.Row():
                    cli_size = gr.Textbox(value="", label="Output Size (WIDTHxHEIGHT)")
                    cli_corner_radius = gr.Slider(minimum=0, maximum=128, step=1, value=0, label="Corner Radius")
                    cli_keep_frames = gr.Checkbox(value=False, label="Keep Intermediate Frames")
                    cli_no_bg_removal = gr.Checkbox(value=False, label="Skip Background Removal")
                cli_work_dir = gr.Textbox(
                    value="",
                    label="Work Dir (optional)",
                    placeholder=r"D:\path\to\temp",
                )
                with gr.Row():
                    cli_bg_preset = gr.Dropdown(
                        choices=["transparent", "white", "black", "green", "blue", "red", "gray"],
                        value="white",
                        label="Background Preset",
                    )
                    cli_bg_custom = gr.Textbox(value="", label="Custom RGB Background")
                    cli_bg_image = gr.File(type="filepath", file_types=["image"], label="Background Image")
                cli_rembg_model = gr.Dropdown(
                    choices=cli_module.MODEL_CHOICES,
                    value=cli_module.MODEL_CHOICES[0],
                    label="rembg Model",
                )

            if show_matanyone_settings:
                with gr.Accordion("MatAnyone Backend Settings", open=False):
                    with gr.Row():
                        cli_matanyone_root: Any = gr.Textbox(
                            value=str(matanyone_root),
                            label="MatAnyone Root",
                        )
                        cli_matanyone_python: Any = gr.Textbox(
                            value=default_matanyone_python,
                            label="MatAnyone Python",
                        )
                    with gr.Row():
                        cli_matanyone_model: Any = gr.Dropdown(
                            choices=MATANYONE_MODEL_CHOICES,
                            value="MatAnyone 2",
                            label="MatAnyone Model",
                        )
                        cli_matanyone_device: Any = gr.Dropdown(
                            choices=MATANYONE_DEVICE_CHOICES,
                            value=args.device,
                            label="MatAnyone Device",
                        )
                        cli_matanyone_profile: Any = gr.Dropdown(
                            choices=MATANYONE_PROFILE_CHOICES,
                            value=args.performance_profile,
                            label="Performance Profile",
                        )
                        cli_matanyone_sam: Any = gr.Dropdown(
                            choices=MATANYONE_SAM_MODEL_CHOICES,
                            value=args.sam_model_type,
                            label="SAM Model Type",
                        )
                    with gr.Row():
                        cli_matanyone_cpu_threads: Any = gr.Number(value=0, precision=0, label="CPU Threads (0 = auto)")
                        cli_matanyone_frame_limit: Any = gr.Number(value=0, precision=0, label="Frame Limit (0 = none)")
                        cli_matanyone_video_target_fps: Any = gr.Number(value=0.0, label="Video Target FPS")
                        cli_matanyone_output_fps: Any = gr.Number(value=0.0, label="Output FPS Override")
                    with gr.Row():
                        cli_matanyone_select_frame: Any = gr.Number(value=0, precision=0, label="Select Frame")
                        cli_matanyone_end_frame: Any = gr.Number(value=0, precision=0, label="End Frame (0 = none)")
                    with gr.Row():
                        cli_positive_points: Any = gr.Textbox(
                            value="",
                            lines=4,
                            label="Positive Points",
                            placeholder="320,180",
                        )
                        cli_negative_points: Any = gr.Textbox(
                            value="",
                            lines=4,
                            label="Negative Points",
                            placeholder="16,16",
                        )
            else:
                cli_matanyone_root = gr.State("")
                cli_matanyone_python = gr.State("")
                cli_matanyone_model = gr.State("MatAnyone 2")
                cli_matanyone_device = gr.State(args.device)
                cli_matanyone_profile = gr.State(args.performance_profile)
                cli_matanyone_sam = gr.State(args.sam_model_type)
                cli_matanyone_cpu_threads = gr.State(0)
                cli_matanyone_frame_limit = gr.State(0)
                cli_matanyone_video_target_fps = gr.State(0.0)
                cli_matanyone_output_fps = gr.State(0.0)
                cli_matanyone_select_frame = gr.State(0)
                cli_matanyone_end_frame = gr.State(0)
                cli_positive_points = gr.State("")
                cli_negative_points = gr.State("")

            cli_run_button = gr.Button(f"Run {tab_label}")
            cli_export_files = gr.Textbox(
                label="CLI Export Outputs",
                lines=6,
                interactive=False,
            )
            cli_export_status = gr.Textbox(
                label="CLI Export Status",
                lines=6,
                value="Idle. Choose an example or input file, then run an export.",
            )

            cli_run_button.click(
                fn=run_cli_export,
                inputs=[
                    source_mode_state,
                    cli_input_upload,
                    cli_input_path,
                    cli_alpha_upload,
                    cli_alpha_path,
                    cli_output_path,
                    cli_export_mode,
                    cli_video_format,
                    cli_animated_format,
                    cli_frame_format,
                    cli_rembg_model,
                    cli_bg_preset,
                    cli_bg_custom,
                    cli_bg_image,
                    cli_size,
                    cli_regular_fps,
                    cli_animated_fps,
                    cli_max_frames,
                    cli_interval,
                    cli_keep_frames,
                    cli_work_dir,
                    cli_no_bg_removal,
                    cli_corner_radius,
                    cli_matanyone_root,
                    cli_matanyone_python,
                    cli_matanyone_model,
                    cli_matanyone_device,
                    cli_matanyone_profile,
                    cli_matanyone_sam,
                    cli_matanyone_cpu_threads,
                    cli_matanyone_frame_limit,
                    cli_matanyone_video_target_fps,
                    cli_matanyone_output_fps,
                    cli_matanyone_select_frame,
                    cli_matanyone_end_frame,
                    cli_positive_points,
                    cli_negative_points,
                ],
                outputs=[cli_export_files, cli_export_status],
                show_progress="full",
            )

            example_inputs = [
                cli_input_upload,
                cli_input_path,
            ]
            if show_alpha_inputs:
                example_inputs.extend([cli_alpha_upload, cli_alpha_path])
            example_inputs.extend(
                [
                    cli_output_path,
                    cli_export_mode,
                    cli_video_format,
                    cli_animated_format,
                    cli_frame_format,
                ]
            )
            gr.Examples(examples=examples, inputs=example_inputs)

    css = """
    .gradio-container {max-width: 1280px !important; margin: 0 auto;}
    .vbr-title h1 {margin-bottom: 0.25rem; font-size: 2.5rem;}
    .vbr-hint {color: #4b5563; font-size: 0.95rem;}
    """

    with gr.Blocks(title="Video Background Remover Studio") as demo:
        gr.HTML(
            """
            <div class="vbr-title">
              <h1>Video Background Remover Studio</h1>
            </div>
            """
        )
        gr.Markdown(
            "video-background-remover の Gradio アプリとして、MatAnyone の "
            "Video / Image ワークフローも統合し、foreground + alpha の結果を "
            "`webp` / `gif` / `png` / `mp4` / `webm` に追加書き出しできます。"
        )
        gr.Markdown(
            f"<div class='vbr-hint'>Device: <code>{device_name}</code> / "
            f"SAM: <code>{sam_model_type}</code> / "
            f"Results: <code>{results_root}</code></div>"
        )

        gr.Markdown(
            "### Mission\n"
            "This app is focused on one primary job: remove the background from a video and export `webp` / `gif`.\n\n"
            "Use `Main Workflow > Video` for the default MatAnyone flow. The other tabs are kept for advanced or legacy cases."
        )

        with gr.Tabs(selected="main_workflow"):
            build_cli_export_tab(
                tab_label="Advanced rembg",
                source_mode_value="regular",
                description=(
                    "Advanced rembg-based export tools. "
                    "Use this only when you specifically want the rembg path instead of the main MatAnyone workflow."
                ),
                manual_input_placeholder=r"D:\path\to\input.mp4",
                examples=cli_examples_by_mode["regular"],
            )

            with gr.TabItem("Legacy MatAnyone", id="legacy_matanyone"):
                gr.Markdown(
                    "### Legacy Interactive Workflow\n"
                    "This tab is kept for compatibility. For the main video background-removal flow, use `Main Workflow > Video`."
                )
                if tutorial_single.exists() or tutorial_multi.exists():
                    with gr.Accordion("Tutorial Videos", open=False):
                        with gr.Row():
                            if tutorial_single.exists():
                                gr.Video(value=str(tutorial_single), label="Single Target Tutorial")
                            if tutorial_multi.exists():
                                gr.Video(value=str(tutorial_multi), label="Multiple Targets Tutorial")
                with gr.Tabs():
                    with gr.TabItem("Video"):
                        video_state_default, interactive_state_default = reset_states(args.performance_profile)
                        video_state = gr.State(video_state_default)
                        interactive_state = gr.State(interactive_state_default)
                        video_click_state = gr.State([[], []])
                        video_export_state = gr.State({})

                        with gr.Row():
                            video_model_selection = gr.Radio(choices=available_models, value=default_model, label="Model Selection")
                            video_profile = gr.Radio(choices=PROFILE_CHOICES, value=args.performance_profile, label="Performance Profile")

                        with gr.Accordion("Matting Settings", open=True):
                            with gr.Row():
                                video_erode = gr.Slider(label="Erode Kernel Size", minimum=0, maximum=30, step=1, value=10)
                                video_dilate = gr.Slider(label="Dilate Kernel Size", minimum=0, maximum=30, step=1, value=10)
                            with gr.Row():
                                video_start_frame = gr.Slider(minimum=1, maximum=100, step=1, value=1, label="Start Frame", visible=False)
                                video_end_frame = gr.Slider(minimum=1, maximum=100, step=1, value=1, label="Track End Frame", visible=False)
                            with gr.Row():
                                video_point_prompt = gr.Radio(choices=["Positive", "Negative"], value="Positive", label="Point Prompt", visible=False)
                                video_mask_dropdown = gr.Dropdown(multiselect=True, value=[], label="Mask Selection (after Add Mask)", visible=False)

                        with gr.Row():
                            with gr.Column(scale=2):
                                video_input = gr.Video(label="Input Video")
                                load_video_button = gr.Button("Load Video")
                                video_info = gr.Textbox(label="Video Info", lines=6)
                            with gr.Column(scale=2):
                                video_template_frame = gr.Image(type="pil", label="Interactive Frame", interactive=True, visible=False)
                                with gr.Row():
                                    video_clear_button = gr.Button("Clear Clicks", visible=False)
                                    video_add_mask_button = gr.Button("Add Mask", visible=False)
                                    video_remove_mask_button = gr.Button("Remove Masks", visible=False)
                                    video_matting_button = gr.Button("Video Matting", visible=False)

                        with gr.Row():
                            video_foreground_output = gr.Video(label="Foreground Output", visible=False)
                            video_alpha_output = gr.Video(label="Alpha Output", visible=False)
                        video_matting_files = gr.File(label="Saved Video Files", file_count="multiple", visible=False)
                        video_status = gr.Textbox(
                            label="Status",
                            lines=4,
                            value="Idle. Load a video to start mask selection and matting.",
                        )

                        with gr.Group(visible=False) as video_export_group:
                            gr.Markdown("### Extra Exports")
                            with gr.Row():
                                video_export_mode = gr.Radio(
                                    choices=[
                                        ("Animated WebP", "animated_webp"),
                                        ("Animated GIF", "animated_gif"),
                                        ("Animated WebP + GIF", "animated_both"),
                                        ("Transparent Frames (WebP ZIP)", "frames_webp"),
                                        ("Transparent Frames (PNG ZIP)", "frames_png"),
                                        ("Transparent WebM", "video_webm"),
                                        ("Flattened MP4", "video_mp4"),
                                    ],
                                    value="animated_webp",
                                    label="Export Mode",
                                )
                                video_export_fps = gr.Slider(minimum=1, maximum=30, step=1, value=10, label="Output FPS")
                                video_export_max_frames = gr.Number(value=120, precision=0, label="Max Frames (0 = all)")
                            with gr.Row():
                                video_export_interval = gr.Number(value=1.0, label="Frame Interval Seconds")
                                video_export_size = gr.Textbox(value="", label="Output Size (WIDTHxHEIGHT)")
                                video_export_radius = gr.Slider(minimum=0, maximum=128, step=1, value=0, label="Corner Radius")
                            with gr.Row():
                                video_export_bg_preset = gr.Dropdown(
                                    choices=["transparent", "white", "black", "green", "blue", "red", "gray"],
                                    value="transparent",
                                    label="MP4 Background Preset",
                                )
                                video_export_bg_custom = gr.Textbox(value="", label="Custom RGB for MP4 (optional)", placeholder="255,128,0")
                                video_export_bg_image = gr.File(file_types=["image"], type="filepath", label="Background Image for MP4 (optional)")
                            video_export_button = gr.Button("Export Results")
                            video_export_files = gr.File(label="Exported Files", file_count="multiple", visible=False)
                            video_export_status = gr.Textbox(
                                label="Export Status",
                                lines=4,
                                value="No export has been run yet.",
                            )

                        load_video_button.click(
                            fn=load_video_input,
                            inputs=[video_input, video_profile],
                            outputs=[
                                video_state, interactive_state, video_click_state, video_template_frame, video_info,
                                video_start_frame, video_end_frame, video_point_prompt, video_mask_dropdown,
                                video_clear_button, video_add_mask_button, video_remove_mask_button, video_matting_button,
                                video_foreground_output, video_alpha_output, video_matting_files, video_export_state,
                                video_export_group, video_export_files, video_status, video_export_status,
                            ],
                            show_progress="full",
                        )
                        video_start_frame.release(fn=select_media_frame, inputs=[video_start_frame, video_state, interactive_state], outputs=[video_template_frame, video_state, interactive_state])
                        video_end_frame.release(fn=set_track_end, inputs=[video_end_frame, video_state, interactive_state], outputs=[video_template_frame, interactive_state])
                        video_template_frame.select(fn=sam_refine, inputs=[video_state, video_point_prompt, video_click_state, interactive_state], outputs=[video_template_frame, video_state, interactive_state])
                        video_add_mask_button.click(fn=add_multi_mask, inputs=[video_state, interactive_state, video_mask_dropdown], outputs=[interactive_state, video_mask_dropdown, video_template_frame, video_click_state])
                        video_remove_mask_button.click(fn=remove_multi_mask, inputs=[interactive_state], outputs=[interactive_state, video_mask_dropdown])
                        video_mask_dropdown.change(fn=show_mask, inputs=[video_state, interactive_state, video_mask_dropdown], outputs=[video_template_frame])
                        video_clear_button.click(fn=clear_clicks, inputs=[video_state], outputs=[video_template_frame, video_click_state])
                        video_matting_button.click(
                            fn=video_matting,
                            inputs=[video_state, interactive_state, video_mask_dropdown, video_erode, video_dilate, video_model_selection, video_profile],
                            outputs=[video_foreground_output, video_alpha_output, video_matting_files, video_export_state, video_export_group, video_status],
                            show_progress="full",
                        )
                        video_export_button.click(
                            fn=export_video_results,
                            inputs=[
                                video_export_state, video_export_mode, video_export_fps, video_export_max_frames,
                                video_export_interval, video_export_size, video_export_radius, video_export_bg_preset,
                                video_export_bg_custom, video_export_bg_image,
                            ],
                            outputs=[video_export_files, video_export_status],
                            show_progress="full",
                        )
                        video_input.change(
                            fn=reset_video_tab,
                            inputs=[],
                            outputs=[
                                video_state, interactive_state, video_click_state, video_template_frame, video_info,
                                video_start_frame, video_end_frame, video_point_prompt, video_mask_dropdown,
                                video_clear_button, video_add_mask_button, video_remove_mask_button, video_matting_button,
                                video_foreground_output, video_alpha_output, video_matting_files, video_export_state,
                                video_export_group, video_export_files, video_status, video_export_status,
                            ],
                            queue=False,
                            show_progress=False,
                        )
                        video_input.clear(
                            fn=reset_video_tab,
                            inputs=[],
                            outputs=[
                                video_state, interactive_state, video_click_state, video_template_frame, video_info,
                                video_start_frame, video_end_frame, video_point_prompt, video_mask_dropdown,
                                video_clear_button, video_add_mask_button, video_remove_mask_button, video_matting_button,
                                video_foreground_output, video_alpha_output, video_matting_files, video_export_state,
                                video_export_group, video_export_files, video_status, video_export_status,
                            ],
                            queue=False,
                            show_progress=False,
                        )
                        if video_examples:
                            gr.Examples(examples=video_examples, inputs=[video_input])

                    with gr.TabItem("Image"):
                        image_state_default, image_interactive_default = reset_states(args.performance_profile)
                        image_state = gr.State(image_state_default)
                        image_interactive_state = gr.State(image_interactive_default)
                        image_click_state = gr.State([[], []])

                        with gr.Row():
                            image_model_selection = gr.Radio(choices=available_models, value=default_model, label="Model Selection")
                            image_profile = gr.Radio(choices=PROFILE_CHOICES, value=args.performance_profile, label="Performance Profile")

                        with gr.Accordion("Matting Settings", open=True):
                            with gr.Row():
                                image_erode = gr.Slider(label="Erode Kernel Size", minimum=0, maximum=30, step=1, value=10)
                                image_dilate = gr.Slider(label="Dilate Kernel Size", minimum=0, maximum=30, step=1, value=10)
                            with gr.Row():
                                image_refine_iter = gr.Slider(minimum=1, maximum=10, step=1, value=10, label="Num of Refinement Iterations", visible=False)
                                image_track_end = gr.Slider(minimum=1, maximum=1, step=1, value=1, label="Track End Frame", visible=False)
                            with gr.Row():
                                image_point_prompt = gr.Radio(choices=["Positive", "Negative"], value="Positive", label="Point Prompt", visible=False)
                                image_mask_dropdown = gr.Dropdown(multiselect=True, value=[], label="Mask Selection (after Add Mask)", visible=False)

                        with gr.Row():
                            with gr.Column(scale=2):
                                image_input = gr.Image(label="Input Image")
                                load_image_button = gr.Button("Load Image")
                                image_info = gr.Textbox(label="Image Info", lines=6)
                            with gr.Column(scale=2):
                                image_template_frame = gr.Image(type="pil", label="Interactive Image", interactive=True, visible=False)
                                with gr.Row():
                                    image_clear_button = gr.Button("Clear Clicks", visible=False)
                                    image_add_mask_button = gr.Button("Add Mask", visible=False)
                                    image_remove_mask_button = gr.Button("Remove Masks", visible=False)
                                    image_matting_button = gr.Button("Image Matting", visible=False)

                        with gr.Row():
                            image_foreground_output = gr.Image(label="Foreground Output", visible=False)
                            image_alpha_output = gr.Image(label="Alpha Output", visible=False)
                        image_files = gr.File(label="Saved Image Files", file_count="multiple", visible=False)
                        image_status = gr.Textbox(
                            label="Status",
                            lines=4,
                            value="Idle. Load an image to start mask selection and matting.",
                        )

                        load_image_button.click(
                            fn=load_image_input,
                            inputs=[image_input, image_profile],
                            outputs=[
                                image_state, image_interactive_state, image_click_state, image_template_frame, image_info,
                                image_refine_iter, image_track_end, image_point_prompt, image_mask_dropdown,
                                image_clear_button, image_add_mask_button, image_remove_mask_button, image_matting_button,
                                image_foreground_output, image_alpha_output, image_files, image_status,
                            ],
                            show_progress="full",
                        )
                        image_refine_iter.release(fn=select_image_template, inputs=[image_refine_iter, image_state, image_interactive_state], outputs=[image_template_frame, image_state, image_interactive_state])
                        image_template_frame.select(fn=sam_refine, inputs=[image_state, image_point_prompt, image_click_state, image_interactive_state], outputs=[image_template_frame, image_state, image_interactive_state])
                        image_add_mask_button.click(fn=add_multi_mask, inputs=[image_state, image_interactive_state, image_mask_dropdown], outputs=[image_interactive_state, image_mask_dropdown, image_template_frame, image_click_state])
                        image_remove_mask_button.click(fn=remove_multi_mask, inputs=[image_interactive_state], outputs=[image_interactive_state, image_mask_dropdown])
                        image_mask_dropdown.change(fn=show_mask, inputs=[image_state, image_interactive_state, image_mask_dropdown], outputs=[image_template_frame])
                        image_clear_button.click(fn=clear_clicks, inputs=[image_state], outputs=[image_template_frame, image_click_state])
                        image_matting_button.click(
                            fn=image_matting,
                            inputs=[image_state, image_interactive_state, image_mask_dropdown, image_erode, image_dilate, image_refine_iter, image_model_selection, image_profile],
                            outputs=[image_foreground_output, image_alpha_output, image_files, image_status],
                            show_progress="full",
                        )
                        image_input.change(
                            fn=reset_image_tab,
                            inputs=[],
                            outputs=[
                                image_state, image_interactive_state, image_click_state, image_template_frame, image_info,
                                image_refine_iter, image_track_end, image_point_prompt, image_mask_dropdown,
                                image_clear_button, image_add_mask_button, image_remove_mask_button, image_matting_button,
                                image_foreground_output, image_alpha_output, image_files, image_status,
                            ],
                            queue=False,
                            show_progress=False,
                        )
                        image_input.clear(
                            fn=reset_image_tab,
                            inputs=[],
                            outputs=[
                                image_state, image_interactive_state, image_click_state, image_template_frame, image_info,
                                image_refine_iter, image_track_end, image_point_prompt, image_mask_dropdown,
                                image_clear_button, image_add_mask_button, image_remove_mask_button, image_matting_button,
                                image_foreground_output, image_alpha_output, image_files, image_status,
                            ],
                            queue=False,
                            show_progress=False,
                        )
                        if image_examples:
                            gr.Examples(examples=image_examples, inputs=[image_input])

            # ========== MatAnyone2 Tab (Pure MatAnyone app.py implementation) ==========
            with gr.TabItem("Main Workflow", id="main_workflow"):
                gr.Markdown("### Main Workflow")
                gr.Markdown(
                    "Use this tab for the primary app mission: interactive MatAnyone video background removal "
                    "followed by animated `webp` / `gif` export."
                )
                gr.Markdown(
                    "The `Video` sub-tab is the main route. The other sub-tabs are advanced helpers for image work, "
                    "batch backend runs, or converting an existing foreground/alpha pair."
                )

                with gr.Tabs(selected="main_video_workflow"):
                    # Video Tab
                    with gr.TabItem("Video", id="main_video_workflow"):
                        ma2_video_click_state = gr.State([[], []])
                        ma2_video_interactive_state = gr.State({
                            "inference_times": 0,
                            "negative_click_times": 0,
                            "positive_click_times": 0,
                            "mask_save": False,
                            "multi_mask": {"mask_names": [], "masks": []},
                            "track_end_number": None,
                        })
                        ma2_video_state = gr.State({
                            "user_name": "",
                            "video_name": "",
                            "origin_images": None,
                            "painted_images": None,
                            "masks": None,
                            "inpaint_masks": None,
                            "logits": None,
                            "select_frame_number": 0,
                            "fps": 30,
                            "audio": "",
                            "source_fps": 30,
                            "frame_stride": 1,
                            "source_size": None,
                            "working_size": None,
                            "performance_profile": args.performance_profile,
                        })

                        with gr.Group():
                            with gr.Row():
                                ma2_video_model_selection = gr.Radio(
                                    choices=available_models,
                                    value=default_model,
                                    label="Model Selection",
                                    info="Choose the model to use for matting",
                                    interactive=True,
                                )
                                ma2_video_performance_profile = gr.Radio(
                                    choices=PROFILE_CHOICES,
                                    value=args.performance_profile,
                                    label="Performance Profile",
                                    info="CPU auto uses fast. Faster profiles reduce working FPS and resolution.",
                                    interactive=True,
                                )
                            with gr.Accordion("Matting Settings", open=False):
                                with gr.Row():
                                    ma2_video_erode = gr.Slider(
                                        label="Erode Kernel Size",
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info="Erosion on the added mask",
                                        interactive=True,
                                    )
                                    ma2_video_dilate = gr.Slider(
                                        label="Dilate Kernel Size",
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info="Dilation on the added mask",
                                        interactive=True,
                                    )
                                with gr.Row():
                                    ma2_video_start_frame = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label="Start Frame",
                                        info="Choose the start frame for target assignment",
                                        visible=False,
                                    )
                                    ma2_video_end_frame = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label="Track End Frame",
                                        visible=False,
                                    )
                                with gr.Row():
                                    ma2_video_point_prompt = gr.Radio(
                                        choices=["Positive", "Negative"],
                                        value="Positive",
                                        label="Point Prompt",
                                        info="Click to add positive or negative point",
                                        interactive=True,
                                        visible=False,
                                    )
                                    ma2_video_mask_dropdown = gr.Dropdown(
                                        multiselect=True,
                                        value=[],
                                        label="Mask Selection",
                                        info="Choose 1~all mask(s) added",
                                        visible=False,
                                    )

                        gr.Markdown("---")

                        with gr.Column():
                            with gr.Row():
                                with gr.Column(scale=2):
                                    gr.Markdown("## Step1: Upload video")
                                with gr.Column(scale=2):
                                    ma2_video_step2_title = gr.Markdown(
                                        "## Step2: Add masks <small>(Click then **Add Mask**)</small>",
                                        visible=False,
                                    )
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_video_input = gr.Video(label="Input Video")
                                    ma2_load_video_button = gr.Button(value="Load Video", interactive=True)
                                with gr.Column(scale=2):
                                    ma2_video_info = gr.Textbox(label="Video Info", visible=False)
                                    ma2_video_template_frame = gr.Image(
                                        type="pil",
                                        label="Interactive Frame",
                                        interactive=True,
                                        visible=False,
                                    )
                                    with gr.Row():
                                        ma2_video_clear_button = gr.Button(
                                            value="Clear Clicks", interactive=True, visible=False
                                        )
                                        ma2_video_add_mask_button = gr.Button(
                                            value="Add Mask", interactive=True, visible=False
                                        )
                                        ma2_video_remove_mask_button = gr.Button(
                                            value="Remove Masks", interactive=True, visible=False
                                        )
                                        ma2_video_matting_button = gr.Button(
                                            value="Video Matting", interactive=True, visible=False
                                        )

                            gr.Markdown("---")

                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_video_foreground_output = gr.Video(
                                        label="Foreground Output", visible=False
                                    )
                                with gr.Column(scale=2):
                                    ma2_video_alpha_output = gr.Video(
                                        label="Alpha Output", visible=False
                                    )
                            ma2_video_status = gr.Textbox(
                                label="Workflow Status",
                                lines=6,
                                value=(
                                    "Idle. Load a video, add a mask, then run Video Matting. "
                                    "This tab now auto-exports animated WebP and GIF after matting."
                                ),
                            )

                            gr.Markdown("---")
                            gr.Markdown("## Step3: Export to WebP/GIF")
                            gr.Markdown(
                                "Video Matting now auto-generates both `webp` and `gif` with the settings below. "
                                "Use the export buttons only when you want to re-render with different settings."
                            )

                            with gr.Row():
                                ma2_export_fps = gr.Slider(
                                    minimum=5,
                                    maximum=30,
                                    step=1,
                                    value=10,
                                    label="Export FPS",
                                    info="Lower FPS = smaller file size",
                                    interactive=True,
                                )
                                ma2_export_max_frames = gr.Slider(
                                    minimum=30,
                                    maximum=300,
                                    step=10,
                                    value=150,
                                    label="Max Frames",
                                    info="Limit frames for faster export",
                                    interactive=True,
                                )
                                ma2_export_bounce = gr.Checkbox(
                                    value=False,
                                    label="Bounce Loop",
                                    info="Append reversed frames for a ping-pong loop",
                                    interactive=True,
                                )
                            with gr.Row():
                                ma2_export_webp_button = gr.Button(
                                    value="Export WebP", variant="primary", interactive=True
                                )
                                ma2_export_gif_button = gr.Button(
                                    value="Export GIF", variant="secondary", interactive=True
                                )
                            with gr.Row():
                                ma2_webp_output = gr.File(label="WebP Output", visible=False)
                                ma2_gif_output = gr.File(label="GIF Output", visible=False)

                        # Event handlers for Video tab
                        ma2_load_video_button.click(
                            fn=get_frames_from_video_v2,
                            inputs=[ma2_video_input, ma2_video_state, ma2_video_performance_profile],
                            outputs=[
                                ma2_video_state,
                                ma2_video_info,
                                ma2_video_template_frame,
                                ma2_video_start_frame,
                                ma2_video_end_frame,
                                ma2_video_point_prompt,
                                ma2_video_clear_button,
                                ma2_video_add_mask_button,
                                ma2_video_remove_mask_button,
                                ma2_video_matting_button,
                                ma2_video_template_frame,
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_mask_dropdown,
                                ma2_video_step2_title,
                                ma2_video_status,
                            ],
                            show_progress="full",
                        )

                        ma2_video_start_frame.release(
                            fn=select_video_template_v2,
                            inputs=[ma2_video_start_frame, ma2_video_state, ma2_video_interactive_state],
                            outputs=[ma2_video_template_frame, ma2_video_state, ma2_video_interactive_state],
                        )

                        ma2_video_end_frame.release(
                            fn=get_end_number_v2,
                            inputs=[ma2_video_end_frame, ma2_video_state, ma2_video_interactive_state],
                            outputs=[ma2_video_template_frame, ma2_video_interactive_state],
                        )

                        ma2_video_template_frame.select(
                            fn=sam_refine_v2,
                            inputs=[
                                ma2_video_state,
                                ma2_video_point_prompt,
                                ma2_video_click_state,
                                ma2_video_interactive_state,
                            ],
                            outputs=[ma2_video_template_frame, ma2_video_state, ma2_video_interactive_state],
                        )

                        ma2_video_add_mask_button.click(
                            fn=add_multi_mask_v2,
                            inputs=[ma2_video_state, ma2_video_interactive_state, ma2_video_mask_dropdown],
                            outputs=[
                                ma2_video_interactive_state,
                                ma2_video_mask_dropdown,
                                ma2_video_template_frame,
                                ma2_video_click_state,
                            ],
                        )

                        ma2_video_remove_mask_button.click(
                            fn=remove_multi_mask_v2,
                            inputs=[ma2_video_interactive_state, ma2_video_mask_dropdown],
                            outputs=[ma2_video_interactive_state, ma2_video_mask_dropdown],
                        )

                        ma2_video_matting_button.click(
                            fn=video_matting_v2,
                            inputs=[
                                ma2_video_state,
                                ma2_video_interactive_state,
                                ma2_video_mask_dropdown,
                                ma2_video_erode,
                                ma2_video_dilate,
                                ma2_video_model_selection,
                                ma2_video_performance_profile,
                                ma2_export_fps,
                                ma2_export_max_frames,
                                ma2_export_bounce,
                            ],
                            outputs=[
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_webp_output,
                                ma2_gif_output,
                                ma2_video_status,
                            ],
                            show_progress="full",
                        )

                        ma2_export_webp_button.click(
                            fn=export_to_webp_v2,
                            inputs=[
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_export_fps,
                                ma2_export_max_frames,
                                ma2_export_bounce,
                            ],
                            outputs=[ma2_webp_output, ma2_video_status],
                            show_progress="full",
                        )

                        ma2_export_gif_button.click(
                            fn=export_to_gif_v2,
                            inputs=[
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_export_fps,
                                ma2_export_max_frames,
                                ma2_export_bounce,
                            ],
                            outputs=[ma2_gif_output, ma2_video_status],
                            show_progress="full",
                        )

                        ma2_video_mask_dropdown.change(
                            fn=show_mask_v2,
                            inputs=[ma2_video_state, ma2_video_interactive_state, ma2_video_mask_dropdown],
                            outputs=[ma2_video_template_frame],
                        )

                        ma2_video_input.change(
                            fn=restart_v2,
                            inputs=[],
                            outputs=[
                                ma2_video_state,
                                ma2_video_interactive_state,
                                ma2_video_click_state,
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_template_frame,
                                ma2_video_start_frame,
                                ma2_video_end_frame,
                                ma2_video_point_prompt,
                                ma2_video_clear_button,
                                ma2_video_add_mask_button,
                                ma2_video_matting_button,
                                ma2_video_template_frame,
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_remove_mask_button,
                                ma2_video_mask_dropdown,
                                ma2_video_info,
                                ma2_video_step2_title,
                            ],
                            queue=False,
                            show_progress=False,
                        )

                        ma2_video_input.clear(
                            fn=restart_v2,
                            inputs=[],
                            outputs=[
                                ma2_video_state,
                                ma2_video_interactive_state,
                                ma2_video_click_state,
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_template_frame,
                                ma2_video_start_frame,
                                ma2_video_end_frame,
                                ma2_video_point_prompt,
                                ma2_video_clear_button,
                                ma2_video_add_mask_button,
                                ma2_video_matting_button,
                                ma2_video_template_frame,
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_remove_mask_button,
                                ma2_video_mask_dropdown,
                                ma2_video_info,
                                ma2_video_step2_title,
                            ],
                            queue=False,
                            show_progress=False,
                        )

                        ma2_video_clear_button.click(
                            fn=clear_click_v2,
                            inputs=[ma2_video_state, ma2_video_click_state],
                            outputs=[ma2_video_template_frame, ma2_video_click_state],
                        )

                        if video_examples:
                            gr.Examples(examples=video_examples, inputs=[ma2_video_input])

                    # Image Tab
                    with gr.TabItem("Image (Advanced)"):
                        ma2_image_click_state = gr.State([[], []])
                        ma2_image_interactive_state = gr.State({
                            "inference_times": 0,
                            "negative_click_times": 0,
                            "positive_click_times": 0,
                            "mask_save": False,
                            "multi_mask": {"mask_names": [], "masks": []},
                            "track_end_number": None,
                        })
                        ma2_image_state = gr.State({
                            "user_name": "",
                            "image_name": "",
                            "origin_images": None,
                            "painted_images": None,
                            "masks": None,
                            "inpaint_masks": None,
                            "logits": None,
                            "select_frame_number": 0,
                            "fps": 30,
                            "source_fps": 30,
                            "frame_stride": 1,
                            "source_size": None,
                            "working_size": None,
                            "performance_profile": args.performance_profile,
                            "audio": "",
                        })

                        with gr.Group():
                            with gr.Row():
                                ma2_image_model_selection = gr.Radio(
                                    choices=available_models,
                                    value=default_model,
                                    label="Model Selection",
                                    info="Choose the model to use for matting",
                                    interactive=True,
                                )
                                ma2_image_performance_profile = gr.Radio(
                                    choices=PROFILE_CHOICES,
                                    value=args.performance_profile,
                                    label="Performance Profile",
                                    info="CPU auto uses fast. Faster profiles reduce working resolution.",
                                    interactive=True,
                                )
                            with gr.Accordion("Matting Settings", open=False):
                                with gr.Row():
                                    ma2_image_erode = gr.Slider(
                                        label="Erode Kernel Size",
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info="Erosion on the added mask",
                                        interactive=True,
                                    )
                                    ma2_image_dilate = gr.Slider(
                                        label="Dilate Kernel Size",
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info="Dilation on the added mask",
                                        interactive=True,
                                    )
                                with gr.Row():
                                    ma2_image_refine_iter = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=10,
                                        label="Num of Refinement Iterations",
                                        info="More iterations = More details & More time",
                                        visible=False,
                                    )
                                    ma2_image_track_end = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label="Track End Frame",
                                        visible=False,
                                    )
                                with gr.Row():
                                    ma2_image_point_prompt = gr.Radio(
                                        choices=["Positive", "Negative"],
                                        value="Positive",
                                        label="Point Prompt",
                                        info="Click to add positive or negative point",
                                        interactive=True,
                                        visible=False,
                                    )
                                    ma2_image_mask_dropdown = gr.Dropdown(
                                        multiselect=True,
                                        value=[],
                                        label="Mask Selection",
                                        info="Choose 1~all mask(s) added",
                                        visible=False,
                                    )

                        gr.Markdown("---")

                        with gr.Column():
                            with gr.Row():
                                with gr.Column(scale=2):
                                    gr.Markdown("## Step1: Upload image")
                                with gr.Column(scale=2):
                                    ma2_image_step2_title = gr.Markdown(
                                        "## Step2: Add masks <small>(Click then **Add Mask**)</small>",
                                        visible=False,
                                    )
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_image_input = gr.Image(label="Input Image")
                                    ma2_load_image_button = gr.Button(value="Load Image", interactive=True)
                                with gr.Column(scale=2):
                                    ma2_image_info = gr.Textbox(label="Image Info", visible=False)
                                    ma2_image_template_frame = gr.Image(
                                        type="pil",
                                        label="Interactive Frame",
                                        interactive=True,
                                        visible=False,
                                    )
                                    with gr.Row():
                                        ma2_image_clear_button = gr.Button(
                                            value="Clear Clicks", interactive=True, visible=False
                                        )
                                        ma2_image_add_mask_button = gr.Button(
                                            value="Add Mask", interactive=True, visible=False
                                        )
                                        ma2_image_remove_mask_button = gr.Button(
                                            value="Remove Masks", interactive=True, visible=False
                                        )
                                        ma2_image_matting_button = gr.Button(
                                            value="Image Matting", interactive=True, visible=False
                                        )

                            gr.Markdown("---")

                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_image_foreground_output = gr.Image(
                                        type="pil", label="Foreground Output", visible=False
                                    )
                                with gr.Column(scale=2):
                                    ma2_image_alpha_output = gr.Image(
                                        type="pil", label="Alpha Output", visible=False
                                    )

                        # Event handlers for Image tab
                        ma2_load_image_button.click(
                            fn=get_frames_from_image_v2,
                            inputs=[ma2_image_input, ma2_image_state, ma2_image_performance_profile],
                            outputs=[
                                ma2_image_state,
                                ma2_image_info,
                                ma2_image_template_frame,
                                ma2_image_refine_iter,
                                ma2_image_track_end,
                                ma2_image_point_prompt,
                                ma2_image_clear_button,
                                ma2_image_add_mask_button,
                                ma2_image_remove_mask_button,
                                ma2_image_matting_button,
                                ma2_image_template_frame,
                                ma2_image_foreground_output,
                                ma2_image_alpha_output,
                                ma2_image_mask_dropdown,
                                ma2_image_step2_title,
                            ],
                            show_progress="full",
                        )

                        ma2_image_refine_iter.release(
                            fn=select_image_template_v2,
                            inputs=[ma2_image_refine_iter, ma2_image_state, ma2_image_interactive_state],
                            outputs=[ma2_image_template_frame, ma2_image_state, ma2_image_interactive_state],
                        )

                        ma2_image_template_frame.select(
                            fn=sam_refine_v2,
                            inputs=[
                                ma2_image_state,
                                ma2_image_point_prompt,
                                ma2_image_click_state,
                                ma2_image_interactive_state,
                            ],
                            outputs=[ma2_image_template_frame, ma2_image_state, ma2_image_interactive_state],
                        )

                        ma2_image_add_mask_button.click(
                            fn=add_multi_mask_v2,
                            inputs=[ma2_image_state, ma2_image_interactive_state, ma2_image_mask_dropdown],
                            outputs=[
                                ma2_image_interactive_state,
                                ma2_image_mask_dropdown,
                                ma2_image_template_frame,
                                ma2_image_click_state,
                            ],
                        )

                        ma2_image_remove_mask_button.click(
                            fn=remove_multi_mask_v2,
                            inputs=[ma2_image_interactive_state, ma2_image_mask_dropdown],
                            outputs=[ma2_image_interactive_state, ma2_image_mask_dropdown],
                        )

                        ma2_image_matting_button.click(
                            fn=image_matting_v2,
                            inputs=[
                                ma2_image_state,
                                ma2_image_interactive_state,
                                ma2_image_mask_dropdown,
                                ma2_image_erode,
                                ma2_image_dilate,
                                ma2_image_refine_iter,
                                ma2_image_model_selection,
                                ma2_image_performance_profile,
                            ],
                            outputs=[ma2_image_foreground_output, ma2_image_alpha_output],
                            show_progress="full",
                        )

                        ma2_image_mask_dropdown.change(
                            fn=show_mask_v2,
                            inputs=[ma2_image_state, ma2_image_interactive_state, ma2_image_mask_dropdown],
                            outputs=[ma2_image_template_frame],
                        )

                        ma2_image_input.change(
                            fn=restart_v2,
                            inputs=[],
                            outputs=[
                                ma2_image_state,
                                ma2_image_interactive_state,
                                ma2_image_click_state,
                                ma2_image_foreground_output,
                                ma2_image_alpha_output,
                                ma2_image_template_frame,
                                ma2_image_refine_iter,
                                ma2_image_track_end,
                                ma2_image_point_prompt,
                                ma2_image_clear_button,
                                ma2_image_add_mask_button,
                                ma2_image_matting_button,
                                ma2_image_template_frame,
                                ma2_image_foreground_output,
                                ma2_image_alpha_output,
                                ma2_image_remove_mask_button,
                                ma2_image_mask_dropdown,
                                ma2_image_info,
                                ma2_image_step2_title,
                            ],
                            queue=False,
                            show_progress=False,
                        )

                        ma2_image_input.clear(
                            fn=restart_v2,
                            inputs=[],
                            outputs=[
                                ma2_image_state,
                                ma2_image_interactive_state,
                                ma2_image_click_state,
                                ma2_image_foreground_output,
                                ma2_image_alpha_output,
                                ma2_image_template_frame,
                                ma2_image_refine_iter,
                                ma2_image_track_end,
                                ma2_image_point_prompt,
                                ma2_image_clear_button,
                                ma2_image_add_mask_button,
                                ma2_image_matting_button,
                                ma2_image_template_frame,
                                ma2_image_foreground_output,
                                ma2_image_alpha_output,
                                ma2_image_remove_mask_button,
                                ma2_image_mask_dropdown,
                                ma2_image_info,
                                ma2_image_step2_title,
                            ],
                            queue=False,
                            show_progress=False,
                        )

                        ma2_image_clear_button.click(
                            fn=clear_click_v2,
                            inputs=[ma2_image_state, ma2_image_click_state],
                            outputs=[ma2_image_template_frame, ma2_image_click_state],
                        )

                        if image_examples:
                            gr.Examples(examples=image_examples, inputs=[ma2_image_input])

            # ========== End MatAnyone2 Tab ==========

                    build_cli_export_tab(
                        tab_label="Advanced backend",
                        source_mode_value="matanyone_backend",
                        description=(
                            "Advanced batch export for running a regular input through the MatAnyone backend. "
                            "Use this when you need backend settings directly instead of the main interactive video flow."
                        ),
                        manual_input_placeholder=r"D:\path\to\input.mp4",
                        examples=cli_examples_by_mode["matanyone_backend"],
                        show_matanyone_settings=True,
                    )
                    build_cli_export_tab(
                        tab_label="Advanced fg+alpha pair",
                        source_mode_value="matanyone_pair",
                        description=(
                            "Advanced converter for an existing MatAnyone foreground/alpha pair. "
                            "Use this when you already have `*_fg.mp4` and `*_alpha.mp4` and only need export rendering."
                        ),
                        manual_input_placeholder=r"D:\path\to\clip_fg.mp4 or D:\path\to\MatAnyone_dir",
                        examples=cli_examples_by_mode["matanyone_pair"],
                        show_alpha_inputs=True,
                    )

        demo.queue()
        try:
            demo.launch(
                debug=args.debug,
                server_name=args.server_name,
                server_port=args.port,
                share=args.share,
                css=css,
            )
        except KeyboardInterrupt:
            # Gradio already closes the server in block_thread(); return cleanly on Ctrl+C.
            return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_windows_event_loop_policy()
    _suppress_windows_connection_reset_noise()
    args_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(args_list)
    internal_flag_name = INTERNAL_LAUNCH_FLAG.lstrip("-").replace("-", "_")
    if getattr(args, internal_flag_name):
        return _launch_in_process(args)
    return _delegate_to_matanyone_python(args, args_list)


if __name__ == "__main__":
    raise SystemExit(main())
