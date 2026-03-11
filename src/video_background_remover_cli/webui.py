"""Gradio WebUI that reuses the MatAnyone interaction flow and adds export tools."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
import zipfile

from PIL import Image

from .bg_remover import VideoBackgroundRemover
from .cli import parse_color, parse_size
from .matanyone_bridge import resolve_matanyone_python, resolve_matanyone_root


DEFAULT_RESULTS_DIR = Path("output") / "webui"
INTERNAL_LAUNCH_FLAG = "--_internal-launch"


def build_parser() -> argparse.ArgumentParser:
    """Create the WebUI argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-background-remover-webui",
        description=(
            "Launch a Gradio app that preserves the MatAnyone interaction flow "
            "and adds animated WebP/GIF export helpers."
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
    return Path(__file__).resolve().parents[2]


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
    print("Launching WebUI with MatAnyone Python:", python_executable)
    completed = subprocess.run(command, env=env)
    return completed.returncode


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


def _launch_in_process(args: argparse.Namespace) -> int:
    """Run the actual Gradio app inside a MatAnyone-capable Python environment."""
    matanyone_root = resolve_matanyone_root(args.matanyone_root)
    _configure_matanyone_imports(matanyone_root)
    import cv2
    import gradio as gr
    import numpy as np
    import torch

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

    def load_video_input(video_input: str, performance_profile: str):
        if not video_input:
            raise gr.Error("Select a video first.")
        media_state, interactive_state = reset_states(performance_profile)
        media_state, media_info, _runtime_profile = load_video_state(
            video_input,
            device_name,
            performance_profile,
        )
        prepare_sam_frame(sam_generator, media_state, 0, force=True)
        frame_count = len(media_state["origin_images"])
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
                    "then press Add Mask."
                )
            ),
            gr.update(value=""),
        )

    def load_image_input(image_input: np.ndarray, performance_profile: str):
        if image_input is None:
            raise gr.Error("Select an image first.")
        media_state, interactive_state = reset_states(performance_profile)
        media_state, media_info, _runtime_profile = load_image_state(
            image_input,
            device_name,
            performance_profile,
        )
        prepare_sam_frame(sam_generator, media_state, 0, force=True)
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
            gr.update(value="Image loaded. Click to assign points, then press Add Mask."),
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
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load a video first.")
        sam_generator.release()
        selected_model = load_runtime_model(model_selection)
        template_mask = build_selected_mask(media_state, interactive_state, mask_dropdown)
        foreground, alpha, _runtime_profile = run_matting(
            selected_model,
            media_state,
            template_mask,
            performance_profile,
            device_name,
            erode_kernel_size=erode_kernel_size,
            dilate_kernel_size=dilate_kernel_size,
        )
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
        return (
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
    ):
        if not media_state.get("origin_images"):
            raise gr.Error("Load an image first.")
        sam_generator.release()
        selected_model = load_runtime_model(model_selection)
        template_mask = build_selected_mask(media_state, interactive_state, mask_dropdown)
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
        return (
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
    ):
        if not export_state or not export_state.get("foreground_path"):
            raise gr.Error("Run video matting first.")

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
        return gr.update(value=_collect_existing_files(exported_paths), visible=True), gr.update(value=status)

    css = """
    .gradio-container {max-width: 1280px !important; margin: 0 auto;}
    .vbr-title h1 {margin-bottom: 0.25rem; font-size: 2.5rem;}
    .vbr-hint {color: #4b5563; font-size: 0.95rem;}
    """

    with gr.Blocks(title="MatAnyone Export Studio", css=css) as demo:
        gr.HTML(
            """
            <div class="vbr-title">
              <h1>MatAnyone Export Studio</h1>
            </div>
            """
        )
        gr.Markdown(
            "MatAnyone の Video / Image ワークフローをそのまま使いながら、"
            "foreground + alpha の結果を `webp` / `gif` / `png` / `mp4` / `webm` に追加書き出しできます。"
        )
        gr.Markdown(
            f"<div class='vbr-hint'>Device: <code>{device_name}</code> / "
            f"SAM: <code>{sam_model_type}</code> / "
            f"Results: <code>{results_root}</code></div>"
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

                with gr.Accordion("Matting Settings", open=False):
                    with gr.Row():
                        video_erode = gr.Slider(label="Erode Kernel Size", minimum=0, maximum=30, step=1, value=10)
                        video_dilate = gr.Slider(label="Dilate Kernel Size", minimum=0, maximum=30, step=1, value=10)
                    with gr.Row():
                        video_start_frame = gr.Slider(minimum=1, maximum=100, step=1, value=1, label="Start Frame", visible=False)
                        video_end_frame = gr.Slider(minimum=1, maximum=100, step=1, value=1, label="Track End Frame", visible=False)
                    with gr.Row():
                        video_point_prompt = gr.Radio(choices=["Positive", "Negative"], value="Positive", label="Point Prompt", visible=False)
                        video_mask_dropdown = gr.Dropdown(multiselect=True, value=[], label="Mask Selection", visible=False)

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
                video_status = gr.Textbox(label="Status", lines=4)

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
                    video_export_status = gr.Textbox(label="Export Status", lines=4)

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
                )
                video_export_button.click(
                    fn=export_video_results,
                    inputs=[
                        video_export_state, video_export_mode, video_export_fps, video_export_max_frames,
                        video_export_interval, video_export_size, video_export_radius, video_export_bg_preset,
                        video_export_bg_custom, video_export_bg_image,
                    ],
                    outputs=[video_export_files, video_export_status],
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

                with gr.Accordion("Matting Settings", open=False):
                    with gr.Row():
                        image_erode = gr.Slider(label="Erode Kernel Size", minimum=0, maximum=30, step=1, value=10)
                        image_dilate = gr.Slider(label="Dilate Kernel Size", minimum=0, maximum=30, step=1, value=10)
                    with gr.Row():
                        image_refine_iter = gr.Slider(minimum=1, maximum=10, step=1, value=10, label="Num of Refinement Iterations", visible=False)
                        image_track_end = gr.Slider(minimum=1, maximum=1, step=1, value=1, label="Track End Frame", visible=False)
                    with gr.Row():
                        image_point_prompt = gr.Radio(choices=["Positive", "Negative"], value="Positive", label="Point Prompt", visible=False)
                        image_mask_dropdown = gr.Dropdown(multiselect=True, value=[], label="Mask Selection", visible=False)

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
                image_status = gr.Textbox(label="Status", lines=4)

                load_image_button.click(
                    fn=load_image_input,
                    inputs=[image_input, image_profile],
                    outputs=[
                        image_state, image_interactive_state, image_click_state, image_template_frame, image_info,
                        image_refine_iter, image_track_end, image_point_prompt, image_mask_dropdown,
                        image_clear_button, image_add_mask_button, image_remove_mask_button, image_matting_button,
                        image_foreground_output, image_alpha_output, image_files, image_status,
                    ],
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

        demo.queue()
        demo.launch(
            debug=args.debug,
            server_name=args.server_name,
            server_port=args.port,
            share=args.share,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(args_list)
    internal_flag_name = INTERNAL_LAUNCH_FLAG.lstrip("-").replace("-", "_")
    if getattr(args, internal_flag_name):
        return _launch_in_process(args)
    return _delegate_to_matanyone_python(args, args_list)


if __name__ == "__main__":
    raise SystemExit(main())
