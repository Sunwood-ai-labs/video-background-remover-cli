"""Gradio WebUI for video-background-remover with integrated MatAnyone workflows."""

from __future__ import annotations

import asyncio
import argparse
from datetime import datetime
import html
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote
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
APP_HEADER_PREVIEW_URL = "https://raw.githubusercontent.com/Sunwood-ai-labs/video-background-remover-cli/main/example/output_animated.webp"
DEFAULT_UI_LANGUAGE = "ja"
LANGUAGE_CHOICES = [("日本語", "ja"), ("English", "en")]

UI_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Video Background Remover Studio",
        "app_summary": (
            "This Gradio app combines the MatAnyone video/image workflow with extra "
            "export helpers for `webp` / `gif` / `png` / `mp4` / `webm`."
        ),
        "device_hint": (
            "<div class='vbr-hint'>Device: <code>{device}</code> / "
            "SAM: <code>{sam}</code> / Results: <code>{results}</code></div>"
        ),
        "mission": (
            "### Mission\n"
            "This app focuses on removing video backgrounds and exporting `webp` / `gif`.\n\n"
            "Use `MatAnyone2 > Video` for the main matting workflow. Use `MP4 -> WebP/GIF` "
            "for direct animation conversion without matting. The advanced tabs remain "
            "available for power-user export cases."
        ),
        "tab_mp4_converter": "MP4 -> WebP/GIF",
        "tab_advanced_rembg": "Advanced rembg",
        "tab_matanyone2": "MatAnyone2",
        "tab_advanced_backend": "Advanced backend",
        "tab_advanced_pair": "Advanced fg+alpha pair",
        "tab_video": "Video",
        "tab_image_advanced": "Image (Advanced)",
        "advanced_rembg_desc": (
            "Advanced rembg-based export tools. Use this when you specifically want "
            "the rembg path instead of the main MatAnyone workflow."
        ),
        "advanced_backend_desc": (
            "Advanced batch export for running a regular input through the MatAnyone backend. "
            "Use this when you need backend settings directly instead of the main interactive video flow."
        ),
        "advanced_pair_desc": (
            "Advanced converter for an existing MatAnyone foreground/alpha pair. "
            "Use this when you already have `*_fg.mp4` and `*_alpha.mp4` and only need export rendering."
        ),
        "cli_export_mode_label": "Export Mode",
        "choice_regular_video_output": "Regular Video Output",
        "choice_animated_output": "Animated Output",
        "choice_frame_extraction": "Frame Extraction",
        "input_file_label": "Input File",
        "manual_input_label": "Or Manual Input Path",
        "alpha_video_label": "Alpha Video",
        "manual_alpha_label": "Or Manual Alpha Path",
        "output_path_label": "Output Path (optional)",
        "output_path_placeholder": "Leave blank to auto-save under output\\webui\\cli_runs",
        "general_output_settings": "General Output Settings",
        "regular_video_format_label": "Regular Video Format",
        "animated_format_label": "Animated Format",
        "frame_format_label": "Frame Format",
        "video_fps_override_label": "Video FPS Override (0 = input)",
        "animated_fps_label": "Animated FPS",
        "max_frames_all_label": "Max Frames (0 = all)",
        "frame_interval_label": "Frame Interval Seconds",
        "output_size_label": "Output Size (WIDTHxHEIGHT)",
        "corner_radius_label": "Corner Radius",
        "keep_intermediate_frames_label": "Keep Intermediate Frames",
        "skip_background_removal_label": "Skip Background Removal",
        "work_dir_label": "Work Dir (optional)",
        "background_preset_label": "Background Preset",
        "custom_rgb_background_label": "Custom RGB Background",
        "background_image_label": "Background Image",
        "rembg_model_label": "rembg Model",
        "matanyone_backend_settings": "MatAnyone Backend Settings",
        "matanyone_root_label": "MatAnyone Root",
        "matanyone_python_label": "MatAnyone Python",
        "matanyone_model_label": "MatAnyone Model",
        "matanyone_device_label": "MatAnyone Device",
        "performance_profile_label": "Performance Profile",
        "sam_model_type_label": "SAM Model Type",
        "cpu_threads_label": "CPU Threads (0 = auto)",
        "frame_limit_label": "Frame Limit (0 = none)",
        "video_target_fps_label": "Video Target FPS",
        "output_fps_override_label": "Output FPS Override",
        "select_frame_label": "Select Frame",
        "end_frame_label": "End Frame (0 = none)",
        "positive_points_label": "Positive Points",
        "negative_points_label": "Negative Points",
        "cli_export_outputs_label": "CLI Export Outputs",
        "cli_export_status_label": "CLI Export Status",
        "cli_idle_status": "Idle. Choose an example or input file, then run an export.",
        "run_tab_button": "Run {tab_label}",
        "status_validating_export": "Validating input and preparing the export...",
        "progress_prepare_export_request": "Preparing export request...",
        "progress_running_selected_export": "Running the selected export...",
        "error_input_path_required": "Input path is required.",
        "error_webm_only_pair": (
            "Regular video export to .webm is only supported for MatAnyone foreground+alpha pairs."
        ),
        "status_error_prefix": "Error: {error}",
        "status_source_mode": "Source mode: {value}",
        "status_backend": "Backend: {value}",
        "status_export_mode": "Export mode: {value}",
        "status_saved_target": "Saved target: {value}",
        "source_mode_regular": "Regular input",
        "source_mode_matanyone_backend": "MatAnyone backend",
        "source_mode_matanyone_pair": "MatAnyone fg+alpha pair",
        "backend_rembg": "rembg",
        "backend_matanyone": "MatAnyone",
        "export_mode_video": "Video",
        "export_mode_animated": "Animated",
        "export_mode_interval": "Frame extraction",
        "mp4_header": "### MP4 -> WebP/GIF",
        "mp4_description": (
            "Upload a regular mp4 and convert it directly into animated `webp` and `gif`. "
            "This tab keeps the original video content as-is and skips background removal."
        ),
        "step1_upload_mp4": "## Step1: Upload mp4",
        "input_mp4_label": "Input MP4",
        "load_video_button": "Load Video",
        "video_info_label": "Video Info",
        "image_info_label": "Image Info",
        "load_mp4_info": "Load an mp4 to inspect fps and source size.",
        "resize_preview_label": "Resize Preview",
        "workflow_status_label": "Workflow Status",
        "mp4_idle_status": (
            "Idle. Upload an mp4, tune FPS and resize ratio, then convert it to animated WebP and GIF."
        ),
        "mp4_ready_status": (
            "Video ready. Adjust the export settings, then click Convert MP4 to generate "
            "animated WebP/GIF downloads."
        ),
        "step2_export_settings": "## Step2: Export Settings",
        "animated_output_settings": "Animated Output Settings",
        "mp4_settings_hint": (
            "These settings apply to direct mp4 conversion. This tab always generates both "
            "`webp` and `gif`. Use a lower FPS and smaller resize ratio for lighter files."
        ),
        "export_output_label": "Export Output",
        "always_generates_both": "Always generates: Animated WebP + GIF",
        "export_fps_label": "Export FPS",
        "lower_fps_smaller_info": "Lower FPS = smaller file size",
        "resize_ratio_label": "Resize Ratio",
        "resize_ratio_info": "1.00 = original size, 0.50 = half size",
        "convert_mp4_button": "Convert MP4",
        "step3_preview_download": "## Step3: Preview & Download",
        "mp4_preview_hint": (
            "After conversion finishes, both animated files appear here with previews and direct download buttons."
        ),
        "error_upload_mp4_first": "Upload an mp4 first.",
        "progress_reading_video_metadata": "Reading video metadata...",
        "progress_video_ready": "Video ready",
        "progress_preparing_direct_conversion": "Preparing direct MP4 conversion...",
        "progress_rendering_animated_format": "Rendering animated {format_name}...",
        "progress_direct_conversion_complete": "Direct MP4 conversion complete",
        "status_direct_conversion_done": "Done. Direct MP4 conversion finished.",
        "status_export_type_both": "Export type: webp + gif",
        "status_input": "Input: {value}",
        "status_export_fps": "Export FPS: {value}",
        "status_max_frames_all": "Max frames: all",
        "status_max_frames_value": "Max frames: {value}",
        "status_webp_output": "WebP: {value}",
        "status_gif_output": "GIF: {value}",
        "matanyone_header": "### MatAnyone2",
        "matanyone_description": (
            "Use this tab for the primary app mission: interactive MatAnyone2 video background removal "
            "followed by animated `webp` / `gif` export."
        ),
        "matanyone_description_2": (
            "The `Video` sub-tab is the main route. The other sub-tabs are advanced helpers for image work, "
            "batch backend runs, or converting an existing foreground/alpha pair."
        ),
        "matting_settings_label": "Matting Settings",
        "label_model_selection": "Model Selection",
        "info_choose_model": "Choose the model to use for matting",
        "info_profile_video": "CPU auto uses fast. Faster profiles reduce working FPS and resolution.",
        "info_profile_image": "CPU auto uses fast. Faster profiles reduce working resolution.",
        "label_erode_kernel": "Erode Kernel Size",
        "info_erode_kernel": "Erosion on the added mask",
        "label_dilate_kernel": "Dilate Kernel Size",
        "info_dilate_kernel": "Dilation on the added mask",
        "label_start_frame": "Start Frame",
        "info_start_frame": "Choose the start frame for target assignment",
        "label_track_end_frame": "Track End Frame",
        "label_point_prompt": "Point Prompt",
        "info_point_prompt": "Click to add positive or negative point",
        "point_positive": "Positive",
        "point_negative": "Negative",
        "label_mask_selection": "Mask Selection",
        "info_mask_selection": "Choose 1~all mask(s) added",
        "step1_upload_video": "## Step1: Upload video",
        "step1_upload_image": "## Step1: Upload image",
        "step2_add_masks": "## Step2: Add masks <small>(Click then **Add Mask**)</small>",
        "input_video_label": "Input Video",
        "input_image_label": "Input Image",
        "load_image_button": "Load Image",
        "interactive_frame_label": "Interactive Frame",
        "clear_clicks_button": "Clear Clicks",
        "add_mask_button": "Add Mask",
        "remove_masks_button": "Remove Masks",
        "video_matting_button": "Video Matting",
        "image_matting_button": "Image Matting",
        "foreground_output_label": "Foreground Output",
        "alpha_output_label": "Alpha Output",
        "matanyone_video_idle_status": (
            "Idle. Load a video, add a mask, then run Video Matting. Animated WebP and GIF downloads "
            "will appear here after processing."
        ),
        "matanyone_video_loaded_status": (
            "Video loaded. Add a positive point, save a mask, and run Video Matting. "
            "When matting finishes, this tab will also create animated WebP and GIF files."
        ),
        "matanyone_video_settings_hint": (
            "These settings are applied when `Video Matting` auto-generates the animated `webp` and `gif`."
        ),
        "label_max_frames_simple": "Max Frames",
        "info_limit_frames": "Limit frames for faster export",
        "label_bounce_loop": "Bounce Loop",
        "info_bounce_loop": "Append reversed frames for a ping-pong loop",
        "matanyone_video_preview_hint": (
            "After `Video Matting` finishes, both animated files appear here with previews and direct download buttons."
        ),
        "label_refine_iterations": "Num of Refinement Iterations",
        "info_refine_iterations": "More iterations = More details & More time",
        "default_video_info": "Load a video to prepare the interactive frame.",
        "progress_opening_video": "Opening video...",
        "progress_preparing_first_frame": "Preparing the first frame...",
        "progress_opening_image": "Opening image...",
        "progress_preparing_interactive_preview": "Preparing the interactive preview...",
        "error_load_video_first": "Load a video first.",
        "error_load_image_first": "Load an image first.",
        "status_preparing_matting_exports": "Preparing MatAnyone video matting and animated exports...",
        "progress_loading_selected_model": "Loading the selected model...",
        "progress_building_selected_mask": "Building the selected mask...",
        "progress_running_video_matting": "Running MatAnyone video matting...",
        "progress_encoding_foreground_alpha": "Encoding foreground and alpha videos...",
        "progress_saving_debug_artifacts": "Saving debug artifacts...",
        "progress_rendering_animated_webp_gif": "Rendering animated WebP and GIF...",
        "progress_video_matting_complete": "Video matting and animated exports complete",
        "preview_title_webp": "Animated WebP",
        "preview_title_gif": "Animated GIF",
        "status_matanyone_video_done": (
            "Done. MatAnyone video matting finished and the animated downloads are ready below.\n"
            "Foreground: {foreground}\n"
            "Alpha: {alpha}\n"
            "WebP: {webp}\n"
            "GIF: {gif}\n"
            "Debug artifacts: {debug_dir}"
        ),
        "progress_running_image_matting": "Running MatAnyone image matting...",
        "progress_saving_image_outputs": "Saving image outputs...",
        "progress_image_matting_complete": "Image matting complete",
        "resolution_label": "Resolution",
        "frames_label": "Frames",
        "source_fps_label": "Source FPS",
        "duration_label": "Duration",
        "resize_preview_idle": (
            "Resize ratio 1.00 keeps the original size. Load a video to preview the resized dimensions."
        ),
        "resize_preview_no_metadata": "Load a video to preview the resized dimensions.",
        "resize_preview_value": "Resize ratio {ratio:.2f} -> {width} x {height} (from {src_width} x {src_height})",
        "background_transparent": "Transparent",
        "background_white": "White",
        "background_black": "Black",
        "background_green": "Green",
        "background_blue": "Blue",
        "background_red": "Red",
        "background_gray": "Gray",
    },
    "ja": {
        "app_title": "Video Background Remover Studio",
        "app_summary": (
            "この Gradio アプリは、MatAnyone の Video / Image ワークフローに加えて、"
            "`webp` / `gif` / `png` / `mp4` / `webm` の追加書き出しをまとめて扱えます。"
        ),
        "device_hint": (
            "<div class='vbr-hint'>Device: <code>{device}</code> / "
            "SAM: <code>{sam}</code> / Results: <code>{results}</code></div>"
        ),
        "mission": (
            "### ミッション\n"
            "このアプリの主目的は、動画の背景を切り抜いて `webp` / `gif` に書き出すことです。\n\n"
            "`MatAnyone2 > Video` はメインのマッティング導線です。"
            "`MP4 -> WebP/GIF` はマッティングなしでアニメーション変換したいときに使います。"
            "高度なタブは、細かい書き出し設定が必要な場合のために残しています。"
        ),
        "tab_mp4_converter": "MP4 -> WebP/GIF",
        "tab_advanced_rembg": "Advanced rembg",
        "tab_matanyone2": "MatAnyone2",
        "tab_advanced_backend": "Advanced backend",
        "tab_advanced_pair": "Advanced fg+alpha pair",
        "tab_video": "動画",
        "tab_image_advanced": "画像（詳細）",
        "advanced_rembg_desc": (
            "rembg ベースの詳細書き出しタブです。メインの MatAnyone フローではなく、"
            "rembg 経由で処理したいときに使います。"
        ),
        "advanced_backend_desc": (
            "通常入力を MatAnyone backend で処理するための詳細書き出しタブです。"
            "メインの対話型動画フローではなく、backend 設定を直接触りたいときに使います。"
        ),
        "advanced_pair_desc": (
            "既存の MatAnyone foreground/alpha ペアを変換するための詳細タブです。"
            "`*_fg.mp4` と `*_alpha.mp4` がすでにあり、書き出しだけしたいときに使います。"
        ),
        "cli_export_mode_label": "出力モード",
        "choice_regular_video_output": "通常動画出力",
        "choice_animated_output": "アニメーション出力",
        "choice_frame_extraction": "フレーム抽出",
        "input_file_label": "入力ファイル",
        "manual_input_label": "または手入力パス",
        "alpha_video_label": "Alpha 動画",
        "manual_alpha_label": "または Alpha パス",
        "output_path_label": "出力パス（任意）",
        "output_path_placeholder": "空欄なら output\\webui\\cli_runs 配下へ自動保存します",
        "general_output_settings": "全体の出力設定",
        "regular_video_format_label": "通常動画フォーマット",
        "animated_format_label": "アニメーション形式",
        "frame_format_label": "フレーム形式",
        "video_fps_override_label": "動画 FPS 上書き（0 = 入力を使用）",
        "animated_fps_label": "アニメーション FPS",
        "max_frames_all_label": "最大フレーム数（0 = すべて）",
        "frame_interval_label": "フレーム抽出間隔（秒）",
        "output_size_label": "出力サイズ（幅x高さ）",
        "corner_radius_label": "角丸半径",
        "keep_intermediate_frames_label": "中間フレームを保持",
        "skip_background_removal_label": "背景除去をスキップ",
        "work_dir_label": "作業ディレクトリ（任意）",
        "background_preset_label": "背景プリセット",
        "custom_rgb_background_label": "カスタム RGB 背景",
        "background_image_label": "背景画像",
        "rembg_model_label": "rembg モデル",
        "matanyone_backend_settings": "MatAnyone Backend 設定",
        "matanyone_root_label": "MatAnyone ルート",
        "matanyone_python_label": "MatAnyone Python",
        "matanyone_model_label": "MatAnyone モデル",
        "matanyone_device_label": "MatAnyone デバイス",
        "performance_profile_label": "パフォーマンスプロファイル",
        "sam_model_type_label": "SAM モデル種別",
        "cpu_threads_label": "CPU スレッド数（0 = 自動）",
        "frame_limit_label": "フレーム上限（0 = 無制限）",
        "video_target_fps_label": "目標動画 FPS",
        "output_fps_override_label": "出力 FPS 上書き",
        "select_frame_label": "選択フレーム",
        "end_frame_label": "終了フレーム（0 = なし）",
        "positive_points_label": "Positive Points",
        "negative_points_label": "Negative Points",
        "cli_export_outputs_label": "CLI 出力ファイル",
        "cli_export_status_label": "CLI ステータス",
        "cli_idle_status": "待機中です。サンプルまたは入力ファイルを選んで書き出しを実行してください。",
        "run_tab_button": "{tab_label} を実行",
        "status_validating_export": "入力を確認して書き出しを準備しています...",
        "progress_prepare_export_request": "書き出しリクエストを組み立てています...",
        "progress_running_selected_export": "選択した書き出しを実行しています...",
        "error_input_path_required": "入力パスは必須です。",
        "error_webm_only_pair": "通常動画の .webm 出力は MatAnyone の foreground+alpha ペアにのみ対応しています。",
        "status_error_prefix": "エラー: {error}",
        "status_source_mode": "入力モード: {value}",
        "status_backend": "バックエンド: {value}",
        "status_export_mode": "出力モード: {value}",
        "status_saved_target": "保存先: {value}",
        "source_mode_regular": "通常入力",
        "source_mode_matanyone_backend": "MatAnyone backend",
        "source_mode_matanyone_pair": "MatAnyone fg+alpha ペア",
        "backend_rembg": "rembg",
        "backend_matanyone": "MatAnyone",
        "export_mode_video": "動画",
        "export_mode_animated": "アニメーション",
        "export_mode_interval": "フレーム抽出",
        "mp4_header": "### MP4 -> WebP/GIF",
        "mp4_description": (
            "通常の mp4 をそのまま animated `webp` と `gif` に変換します。"
            "このタブでは元動画の内容を保ったまま、背景除去なしで書き出します。"
        ),
        "step1_upload_mp4": "## Step1: mp4 をアップロード",
        "input_mp4_label": "入力 MP4",
        "load_video_button": "動画を読み込む",
        "video_info_label": "動画情報",
        "image_info_label": "画像情報",
        "load_mp4_info": "mp4 を読み込むと、fps と元サイズを確認できます。",
        "resize_preview_label": "リサイズ確認",
        "workflow_status_label": "ワークフローステータス",
        "mp4_idle_status": "待機中です。mp4 を読み込み、FPS とリサイズ比を調整して WebP と GIF に変換してください。",
        "mp4_ready_status": "動画の準備ができました。設定を調整して `Convert MP4` を押すと、WebP / GIF を生成します。",
        "step2_export_settings": "## Step2: 出力設定",
        "animated_output_settings": "アニメーション出力設定",
        "mp4_settings_hint": (
            "この設定は mp4 の直接変換に使われます。"
            "このタブでは常に `webp` と `gif` の両方を生成します。"
            "FPS とリサイズ比を下げるとファイルサイズを軽くできます。"
        ),
        "export_output_label": "出力内容",
        "always_generates_both": "常に生成: Animated WebP + GIF",
        "export_fps_label": "出力 FPS",
        "lower_fps_smaller_info": "FPS を下げるほどファイルサイズが小さくなります",
        "resize_ratio_label": "リサイズ比",
        "resize_ratio_info": "1.00 = 元サイズ、0.50 = 半分サイズ",
        "convert_mp4_button": "MP4 を変換",
        "step3_preview_download": "## Step3: プレビューとダウンロード",
        "mp4_preview_hint": "変換が終わると、両方のアニメーションをここでプレビューして直接ダウンロードできます。",
        "error_upload_mp4_first": "先に mp4 をアップロードしてください。",
        "progress_reading_video_metadata": "動画メタデータを読み込んでいます...",
        "progress_video_ready": "動画の準備ができました",
        "progress_preparing_direct_conversion": "MP4 の直接変換を準備しています...",
        "progress_rendering_animated_format": "animated {format_name} を生成しています...",
        "progress_direct_conversion_complete": "MP4 の直接変換が完了しました",
        "status_direct_conversion_done": "完了しました。MP4 の直接変換が終わりました。",
        "status_export_type_both": "出力形式: webp + gif",
        "status_input": "入力: {value}",
        "status_export_fps": "出力 FPS: {value}",
        "status_max_frames_all": "最大フレーム数: すべて",
        "status_max_frames_value": "最大フレーム数: {value}",
        "status_webp_output": "WebP: {value}",
        "status_gif_output": "GIF: {value}",
        "matanyone_header": "### MatAnyone2",
        "matanyone_description": (
            "このタブはメイン用途である、対話型の MatAnyone2 動画背景削除と "
            "animated `webp` / `gif` 書き出しのための導線です。"
        ),
        "matanyone_description_2": (
            "`Video` サブタブが主導線です。ほかのサブタブは画像作業や backend 実行、"
            "既存の foreground/alpha ペア変換などの詳細用途向けです。"
        ),
        "matting_settings_label": "マッティング設定",
        "label_model_selection": "モデル選択",
        "info_choose_model": "マッティングに使うモデルを選びます",
        "info_profile_video": "CPU の auto は fast を使います。軽いプロファイルほど FPS と解像度が下がります。",
        "info_profile_image": "CPU の auto は fast を使います。軽いプロファイルほど作業解像度が下がります。",
        "label_erode_kernel": "Erode カーネルサイズ",
        "info_erode_kernel": "追加したマスクに対する収縮処理です",
        "label_dilate_kernel": "Dilate カーネルサイズ",
        "info_dilate_kernel": "追加したマスクに対する膨張処理です",
        "label_start_frame": "開始フレーム",
        "info_start_frame": "ターゲット指定の開始フレームを選びます",
        "label_track_end_frame": "追跡終了フレーム",
        "label_point_prompt": "ポイント種別",
        "info_point_prompt": "クリックで positive / negative point を追加します",
        "point_positive": "Positive",
        "point_negative": "Negative",
        "label_mask_selection": "マスク選択",
        "info_mask_selection": "追加したマスクを 1 個以上選びます",
        "step1_upload_video": "## Step1: 動画をアップロード",
        "step1_upload_image": "## Step1: 画像をアップロード",
        "step2_add_masks": "## Step2: マスクを追加 <small>(クリックして **Add Mask**)</small>",
        "input_video_label": "入力動画",
        "input_image_label": "入力画像",
        "load_image_button": "画像を読み込む",
        "interactive_frame_label": "操作フレーム",
        "clear_clicks_button": "クリックをクリア",
        "add_mask_button": "マスクを追加",
        "remove_masks_button": "マスクを削除",
        "video_matting_button": "動画マッティング",
        "image_matting_button": "画像マッティング",
        "foreground_output_label": "Foreground 出力",
        "alpha_output_label": "Alpha 出力",
        "matanyone_video_idle_status": (
            "待機中です。動画を読み込み、マスクを追加してから Video Matting を実行してください。"
            "処理後に Animated WebP と GIF のダウンロードがここに表示されます。"
        ),
        "matanyone_video_loaded_status": (
            "動画を読み込みました。positive point を置いてマスクを保存し、Video Matting を実行してください。"
            "処理が終わると Animated WebP と GIF も自動生成されます。"
        ),
        "matanyone_video_settings_hint": (
            "この設定は `Video Matting` 実行後に自動生成される animated `webp` / `gif` に適用されます。"
        ),
        "label_max_frames_simple": "最大フレーム数",
        "info_limit_frames": "フレーム数を制限して高速に書き出します",
        "label_bounce_loop": "Bounce Loop",
        "info_bounce_loop": "逆順フレームを追加してピンポンループにします",
        "matanyone_video_preview_hint": (
            "`Video Matting` 完了後に、両方のアニメーションをここでプレビューして直接ダウンロードできます。"
        ),
        "label_refine_iterations": "Refinement 回数",
        "info_refine_iterations": "回数を増やすほど細部が出ますが、時間もかかります",
        "default_video_info": "動画を読み込むと操作フレームを準備します。",
        "progress_opening_video": "動画を開いています...",
        "progress_preparing_first_frame": "先頭フレームを準備しています...",
        "progress_opening_image": "画像を開いています...",
        "progress_preparing_interactive_preview": "操作用プレビューを準備しています...",
        "error_load_video_first": "先に動画を読み込んでください。",
        "error_load_image_first": "先に画像を読み込んでください。",
        "status_preparing_matting_exports": "MatAnyone の動画マッティングとアニメーション出力を準備しています...",
        "progress_loading_selected_model": "選択したモデルを読み込んでいます...",
        "progress_building_selected_mask": "選択したマスクを組み立てています...",
        "progress_running_video_matting": "MatAnyone の動画マッティングを実行しています...",
        "progress_encoding_foreground_alpha": "Foreground と Alpha 動画をエンコードしています...",
        "progress_saving_debug_artifacts": "デバッグ成果物を保存しています...",
        "progress_rendering_animated_webp_gif": "Animated WebP と GIF を生成しています...",
        "progress_video_matting_complete": "動画マッティングとアニメーション出力が完了しました",
        "preview_title_webp": "Animated WebP",
        "preview_title_gif": "Animated GIF",
        "status_matanyone_video_done": (
            "完了しました。MatAnyone の動画マッティングが終わり、アニメーションのダウンロード準備もできています。\n"
            "Foreground: {foreground}\n"
            "Alpha: {alpha}\n"
            "WebP: {webp}\n"
            "GIF: {gif}\n"
            "Debug artifacts: {debug_dir}"
        ),
        "progress_running_image_matting": "MatAnyone の画像マッティングを実行しています...",
        "progress_saving_image_outputs": "画像出力を保存しています...",
        "progress_image_matting_complete": "画像マッティングが完了しました",
        "resolution_label": "解像度",
        "frames_label": "フレーム数",
        "source_fps_label": "元 FPS",
        "duration_label": "長さ",
        "resize_preview_idle": "リサイズ比 1.00 は元サイズのままです。動画を読み込むと出力サイズの変化を確認できます。",
        "resize_preview_no_metadata": "動画を読み込むと出力サイズの変化を確認できます。",
        "resize_preview_value": "リサイズ比 {ratio:.2f} -> {width} x {height} （元: {src_width} x {src_height}）",
        "background_transparent": "透明",
        "background_white": "白",
        "background_black": "黒",
        "background_green": "緑",
        "background_blue": "青",
        "background_red": "赤",
        "background_gray": "灰",
    },
}


def _ui_text(language: str | None, key: str, **kwargs: Any) -> str:
    resolved_language = language if language in UI_TEXT else DEFAULT_UI_LANGUAGE
    template = UI_TEXT.get(resolved_language, {}).get(key)
    if template is None:
        template = UI_TEXT["en"].get(key, key)
    return template.format(**kwargs)


def _build_app_title_html(language: str = DEFAULT_UI_LANGUAGE) -> str:
    return (
        "<div class=\"vbr-title\">"
        "<div class=\"vbr-title-copy\">"
        f"<h1>{html.escape(_ui_text(language, 'app_title'))}</h1>"
        "</div>"
        f"<a class=\"vbr-title-preview\" href=\"{html.escape(APP_HEADER_PREVIEW_URL, quote=True)}\" "
        "target=\"_blank\" rel=\"noopener noreferrer\">"
        f"<img src=\"{html.escape(APP_HEADER_PREVIEW_URL, quote=True)}\" "
        "alt=\"Animated output preview\" />"
        "</a>"
        "</div>"
    )


def _build_device_hint_html(
    device_name: str,
    sam_model_type: str,
    results_root: Path,
    language: str = DEFAULT_UI_LANGUAGE,
) -> str:
    return _ui_text(
        language,
        "device_hint",
        device=device_name,
        sam=sam_model_type,
        results=results_root,
    )


def _collect_existing_example_paths(*paths: Path) -> list[str]:
    return [str(path.resolve()) for path in paths if path.exists()]


def _build_advanced_rembg_examples(cwd: Path | None = None) -> list[list[str | None]]:
    base_dir = (cwd or Path.cwd()).resolve()
    specs = [
        ("onizuka_idle_motion.mp4", "animated", "both", "webp"),
        ("onizuka_walk_motion.mp4", "interval", "webp", "png"),
        ("onizuka_fire_motion.mp4", "video", "webp", "webp"),
    ]
    examples: list[list[str | None]] = []
    for file_name, export_mode, animated_format, frame_format in specs:
        path = base_dir / "assets" / file_name
        if not path.exists():
            continue
        examples.append(
            [
                None,
                str(path.resolve()),
                "",
                export_mode,
                "mp4",
                animated_format,
                frame_format,
            ]
        )
    return examples


def _localized_export_mode_choices(language: str) -> list[tuple[str, str]]:
    return [
        (_ui_text(language, "choice_regular_video_output"), "video"),
        (_ui_text(language, "choice_animated_output"), "animated"),
        (_ui_text(language, "choice_frame_extraction"), "interval"),
    ]


def _localized_point_prompt_choices(language: str) -> list[tuple[str, str]]:
    return [
        (_ui_text(language, "point_positive"), "Positive"),
        (_ui_text(language, "point_negative"), "Negative"),
    ]


def _localized_background_preset_choices(language: str) -> list[tuple[str, str]]:
    return [
        (_ui_text(language, "background_transparent"), "transparent"),
        (_ui_text(language, "background_white"), "white"),
        (_ui_text(language, "background_black"), "black"),
        (_ui_text(language, "background_green"), "green"),
        (_ui_text(language, "background_blue"), "blue"),
        (_ui_text(language, "background_red"), "red"),
        (_ui_text(language, "background_gray"), "gray"),
    ]


def _localized_source_mode(language: str, source_mode: str) -> str:
    return _ui_text(language, f"source_mode_{source_mode}")


def _localized_backend_name(language: str, backend_name: str) -> str:
    return _ui_text(language, f"backend_{backend_name}")


def _localized_export_mode_name(language: str, export_mode: str) -> str:
    return _ui_text(language, f"export_mode_{export_mode}")


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


def _build_gradio_file_url(file_path: str | None) -> str | None:
    if not file_path:
        return None
    path = Path(file_path)
    if not path.exists():
        return None
    return f"/gradio_api/file={quote(path.resolve().as_posix(), safe='/:')}"


def _build_preview_download_html(title: str, file_path: str | None) -> str:
    file_url = _build_gradio_file_url(file_path)
    if not file_url:
        return ""
    safe_title = html.escape(title, quote=True)
    safe_name = html.escape(Path(file_path).name, quote=True)
    return (
        '<div class="ma2-preview-card">'
        f'<div class="ma2-preview-title">{safe_title}</div>'
        f'<img class="ma2-preview-media" src="{file_url}" alt="{safe_title}">'
        f'<div class="ma2-preview-name">{safe_name}</div>'
        f'<a class="ma2-download-link" href="{file_url}" download="{safe_name}">Download {safe_title}</a>'
        "</div>"
    )


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


def _read_video_metadata(video_path: str) -> dict[str, Any]:
    import cv2

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        capture.release()

    duration = frame_count / fps if fps > 0 else 0.0
    return {
        "video_path": str(Path(video_path)),
        "fps": fps,
        "frame_count": frame_count,
        "duration": duration,
        "width": width,
        "height": height,
    }


def _normalize_resize_ratio(value: float | int | None) -> float:
    if value in (None, ""):
        return 1.0
    return max(0.05, float(value))


def _compute_scaled_dimensions(
    width: int,
    height: int,
    resize_ratio: float | int | None,
) -> tuple[int, int]:
    ratio = _normalize_resize_ratio(resize_ratio)
    return (
        max(1, int(round(width * ratio))),
        max(1, int(round(height * ratio))),
    )


def _build_video_info_text(
    metadata: dict[str, Any],
    language: str = DEFAULT_UI_LANGUAGE,
) -> str:
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    frame_count = int(metadata.get("frame_count") or 0)
    fps = float(metadata.get("fps") or 0.0)
    duration = float(metadata.get("duration") or 0.0)
    return (
        f"{_ui_text(language, 'resolution_label')}: {width} x {height}\n"
        f"{_ui_text(language, 'frames_label')}: {frame_count}\n"
        f"{_ui_text(language, 'source_fps_label')}: {fps:.2f}\n"
        f"{_ui_text(language, 'duration_label')}: {duration:.2f}s"
    )


def _build_resize_ratio_text(
    metadata: dict[str, Any] | None,
    resize_ratio: float | int | None,
    language: str = DEFAULT_UI_LANGUAGE,
) -> str:
    if not metadata:
        return _ui_text(language, "resize_preview_idle")

    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width <= 0 or height <= 0:
        return _ui_text(language, "resize_preview_no_metadata")

    ratio = _normalize_resize_ratio(resize_ratio)
    resized_width, resized_height = _compute_scaled_dimensions(width, height, ratio)
    return _ui_text(
        language,
        "resize_preview_value",
        ratio=ratio,
        width=resized_width,
        height=resized_height,
        src_width=width,
        src_height=height,
    )


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

    assets_root = Path.cwd().resolve() / "assets"
    mp4_converter_examples = _collect_existing_example_paths(
        assets_root / "star-cat2.mp4",
        assets_root / "jetclaw2.mp4",
        assets_root / "onizuka_release_v010_motion.mp4",
        assets_root / "onizuka_idle_motion.mp4",
    )
    matanyone_video_examples = [
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
    matanyone_image_examples = [
        matanyone_root / "hugging_face" / "test_sample" / name
        for name in [
            "test-sample-0.jpg",
            "test-sample-1.jpg",
            "test-sample-2.jpg",
            "test-sample-3.jpg",
        ]
    ]
    matanyone_video_examples = [str(path) for path in matanyone_video_examples if path.exists()]
    matanyone_image_examples = [str(path) for path in matanyone_image_examples if path.exists()]
    advanced_rembg_examples = _build_advanced_rembg_examples(Path.cwd())
    cli_examples_by_mode = build_cli_examples_by_mode(Path.cwd())
    default_language = DEFAULT_UI_LANGUAGE
    language_update_targets: list[tuple[Any, Any]] = []

    def register_language_target(component: Any, builder: Any) -> Any:
        language_update_targets.append((component, builder))
        return component

    def apply_ui_language(
        language: str,
        mp4_metadata: dict[str, Any] | None,
        mp4_resize_ratio: float,
    ):
        updates = []
        for _component, builder in language_update_targets:
            updates.append(builder(language, mp4_metadata or {}, mp4_resize_ratio))
        return updates

    def load_runtime_model(display_name: str):
        return runtime_models.load_model(display_name)

    # ========== MatAnyone2 Tab Functions (from MatAnyone app.py) ==========

    def get_frames_from_video_v2(
        video_input: str,
        video_state: dict,
        performance_profile: str,
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Extract frames from uploaded video - MatAnyone2 version."""
        _push_progress(progress, 0.05, _ui_text(language, "progress_opening_video"))
        video_state, video_info, _runtime_profile = load_video_state(
            video_input, device_name, performance_profile
        )
        _push_progress(progress, 0.7, _ui_text(language, "progress_preparing_first_frame"))
        prepare_sam_frame(sam_generator, video_state, 0, force=True)
        frame_count = len(video_state["origin_images"])
        _push_progress(progress, 1.0, _ui_text(language, "progress_video_ready"))
        return (
            video_state,
            gr.update(value=video_info, visible=True),
            gr.update(value=video_state["origin_images"][0], visible=True),
            gr.update(visible=True, maximum=frame_count, value=1),
            gr.update(visible=False, maximum=frame_count, value=frame_count),
            gr.update(visible=True, interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=True, interactive=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True, interactive=True, choices=[], value=[]),
            gr.update(visible=True),
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(
                value=_ui_text(language, "matanyone_video_loaded_status")
            ),
        )

    def get_frames_from_image_v2(
        image_input: np.ndarray,
        image_state: dict,
        performance_profile: str,
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Extract frames from uploaded image - MatAnyone2 version."""
        _push_progress(progress, 0.05, _ui_text(language, "progress_opening_image"))
        image_state, image_info, _runtime_profile = load_image_state(
            image_input, device_name, performance_profile
        )
        _push_progress(
            progress,
            0.7,
            _ui_text(language, "progress_preparing_interactive_preview"),
        )
        prepare_sam_frame(sam_generator, image_state, 0, force=True)
        frame_count = len(image_state["origin_images"])
        _push_progress(progress, 1.0, _ui_text(language, "progress_video_ready"))
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
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Video matting - MatAnyone2 version using generate_video_from_frames."""
        if not video_state.get("origin_images"):
            raise gr.Error(_ui_text(language, "error_load_video_first"))

        yield (
            gr.update(),
            gr.update(),
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(value=_ui_text(language, "status_preparing_matting_exports")),
        )
        _push_progress(progress, 0.05, _ui_text(language, "progress_loading_selected_model"))
        sam_generator.release()
        try:
            selected_model = load_runtime_model(model_selection)
        except (FileNotFoundError, ValueError) as e:
            if available_models:
                print(f"Warning: {str(e)}. Using {available_models[0]} instead.")
                selected_model = load_runtime_model(available_models[0])
            else:
                raise ValueError("No models are available! Please check if the model files exist.")

        _push_progress(progress, 0.2, _ui_text(language, "progress_building_selected_mask"))
        template_mask = compose_selected_mask(
            video_state["masks"][video_state["select_frame_number"]],
            interactive_state["multi_mask"]["masks"],
            mask_dropdown,
        )
        if interactive_state["multi_mask"]["masks"]:
            video_state["masks"][video_state["select_frame_number"]] = template_mask

        fps = video_state["fps"]
        audio_path = video_state.get("audio", "")

        _push_progress(progress, 0.35, _ui_text(language, "progress_running_video_matting"))
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

        _push_progress(progress, 0.8, _ui_text(language, "progress_encoding_foreground_alpha"))
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
        _push_progress(progress, 0.94, _ui_text(language, "progress_saving_debug_artifacts"))
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
        _push_progress(progress, 0.97, _ui_text(language, "progress_rendering_animated_webp_gif"))

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
        _push_progress(progress, 1.0, _ui_text(language, "progress_video_matting_complete"))
        yield (
            gr.update(value=foreground_output, visible=True),
            gr.update(value=alpha_output, visible=True),
            gr.update(
                value=_build_preview_download_html(_ui_text(language, "preview_title_webp"), webp_output),
                visible=True,
            ),
            gr.update(
                value=_build_preview_download_html(_ui_text(language, "preview_title_gif"), gif_output),
                visible=True,
            ),
            gr.update(
                value=_ui_text(
                    language,
                    "status_matanyone_video_done",
                    foreground=foreground_output,
                    alpha=alpha_output,
                    webp=webp_output,
                    gif=gif_output,
                    debug_dir=debug_dir,
                )
            ),
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
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        """Image matting - MatAnyone2 version."""
        if not image_state.get("origin_images"):
            raise gr.Error(_ui_text(language, "error_load_image_first"))

        _push_progress(progress, 0.05, _ui_text(language, "progress_loading_selected_model"))
        sam_generator.release()
        try:
            selected_model = load_runtime_model(model_selection)
        except (FileNotFoundError, ValueError) as e:
            if available_models:
                print(f"Warning: {str(e)}. Using {available_models[0]} instead.")
                selected_model = load_runtime_model(available_models[0])
            else:
                raise ValueError("No models are available! Please check if the model files exist.")

        _push_progress(progress, 0.2, _ui_text(language, "progress_building_selected_mask"))
        template_mask = compose_selected_mask(
            image_state["masks"][image_state["select_frame_number"]],
            interactive_state["multi_mask"]["masks"],
            mask_dropdown,
        )
        if interactive_state["multi_mask"]["masks"]:
            image_state["masks"][image_state["select_frame_number"]] = template_mask

        _push_progress(progress, 0.4, _ui_text(language, "progress_running_image_matting"))
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

        _push_progress(progress, 0.82, _ui_text(language, "progress_saving_image_outputs"))
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
        _push_progress(progress, 1.0, _ui_text(language, "progress_image_matting_complete"))
        return foreground_output, alpha_output

    def restart_video_v2(language: str):
        """Reset the MatAnyone2 video tab for a new input."""
        media_state, interactive_state = create_empty_media_state(args.performance_profile, False)
        return (
            media_state,
            interactive_state,
            [[], []],
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=True),
            gr.update(value=1, minimum=1, maximum=100, visible=False),
            gr.update(value=1, minimum=1, maximum=100, visible=False),
            gr.update(value="Positive", visible=True, interactive=False),
            gr.update(visible=True, interactive=False),
            gr.update(visible=True, interactive=False),
            gr.update(visible=True, interactive=False),
            gr.update(visible=True, interactive=False),
            gr.update(visible=True, interactive=False, choices=[], value=[]),
            gr.update(value=_ui_text(language, "default_video_info"), visible=True),
            gr.update(
                value=_ui_text(language, "step2_add_masks"),
                visible=True,
            ),
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(value=_ui_text(language, "matanyone_video_idle_status")),
        )

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

    def restart_mp4_converter(language: str):
        return (
            {},
            gr.update(
                value=_ui_text(language, "load_mp4_info"),
                visible=True,
            ),
            gr.update(
                value=_build_resize_ratio_text(None, 1.0, language),
                visible=True,
            ),
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(value=_ui_text(language, "mp4_idle_status")),
            gr.update(interactive=False),
        )

    def load_mp4_converter_video(
        video_input: str,
        resize_ratio: float,
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not video_input:
            raise gr.Error(_ui_text(language, "error_upload_mp4_first"))

        _push_progress(progress, 0.1, _ui_text(language, "progress_reading_video_metadata"))
        try:
            metadata = _read_video_metadata(video_input)
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc
        _push_progress(progress, 1.0, _ui_text(language, "progress_video_ready"))
        return (
            metadata,
            gr.update(value=_build_video_info_text(metadata, language), visible=True),
            gr.update(
                value=_build_resize_ratio_text(metadata, resize_ratio, language),
                visible=True,
            ),
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(value=_ui_text(language, "mp4_ready_status")),
            gr.update(interactive=True),
        )

    def update_mp4_resize_preview(
        metadata: dict[str, Any],
        resize_ratio: float,
        language: str,
    ):
        return gr.update(
            value=_build_resize_ratio_text(metadata, resize_ratio, language),
            visible=True,
        )

    def convert_mp4_to_animated(
        video_input: str,
        metadata: dict[str, Any],
        export_fps: int | float,
        resize_ratio: float,
        max_frames: int | float | None,
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        if not video_input:
            raise gr.Error(_ui_text(language, "error_upload_mp4_first"))

        yield (
            gr.update(value="", visible=False),
            gr.update(value="", visible=False),
            gr.update(value=_ui_text(language, "progress_preparing_direct_conversion")),
        )

        if (
            not metadata
            or Path(metadata.get("video_path", "")).resolve() != Path(video_input).resolve()
        ):
            try:
                metadata = _read_video_metadata(video_input)
            except ValueError as exc:
                raise gr.Error(str(exc)) from exc

        width = int(metadata.get("width") or 0)
        height = int(metadata.get("height") or 0)
        output_size = None
        if width > 0 and height > 0:
            scaled_width, scaled_height = _compute_scaled_dimensions(
                width,
                height,
                resize_ratio,
            )
            if (scaled_width, scaled_height) != (width, height):
                output_size = (scaled_width, scaled_height)

        format_names = ["webp", "gif"]
        output_dir = results_root / "mp4_converter" / _timestamp_token()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_root = output_dir / f"{Path(video_input).stem}_animated"
        remover = VideoBackgroundRemover()
        export_fps_value = max(1, int(export_fps or 10))
        max_frames_value = _safe_max_frames(max_frames)

        for index, format_name in enumerate(format_names):
            progress_base = 0.1 + index * 0.4
            _push_progress(
                progress,
                progress_base,
                _ui_text(
                    language,
                    "progress_rendering_animated_format",
                    format_name=format_name.upper(),
                ),
            )
            remover.to_animated(
                video_path=video_input,
                output_path=str(output_root.with_suffix(f".{format_name}")),
                fps=export_fps_value,
                max_frames=max_frames_value,
                format=format_name,
                output_size=output_size,
                remove_background=False,
            )

        webp_output = str(output_root.with_suffix(".webp"))
        gif_output = str(output_root.with_suffix(".gif"))
        resize_text = _build_resize_ratio_text(metadata, resize_ratio, language)
        status_lines = [
            _ui_text(language, "status_direct_conversion_done"),
            _ui_text(language, "status_input", value=video_input),
            _ui_text(language, "status_export_type_both"),
            _ui_text(language, "status_export_fps", value=export_fps_value),
            resize_text,
        ]
        if max_frames_value is None:
            status_lines.append(_ui_text(language, "status_max_frames_all"))
        else:
            status_lines.append(_ui_text(language, "status_max_frames_value", value=max_frames_value))
        if Path(webp_output).exists():
            status_lines.append(_ui_text(language, "status_webp_output", value=webp_output))
        if Path(gif_output).exists():
            status_lines.append(_ui_text(language, "status_gif_output", value=gif_output))

        _push_progress(progress, 1.0, _ui_text(language, "progress_direct_conversion_complete"))
        yield (
            gr.update(
                value=_build_preview_download_html(_ui_text(language, "preview_title_webp"), webp_output),
                visible=Path(webp_output).exists(),
            ),
            gr.update(
                value=_build_preview_download_html(_ui_text(language, "preview_title_gif"), gif_output),
                visible=Path(gif_output).exists(),
            ),
            gr.update(value="\n".join(status_lines)),
        )

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
        language: str,
        progress=gr.Progress(track_tqdm=True),
    ):
        yield (
            gr.update(value=""),
            gr.update(value=_ui_text(language, "status_validating_export")),
        )
        _push_progress(progress, 0.05, _ui_text(language, "progress_prepare_export_request"))
        input_path = _resolve_preferred_path(upload_input_path, manual_input_path)
        if not input_path:
            raise gr.Error(_ui_text(language, "error_input_path_required"))

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
            raise gr.Error(_ui_text(language, "error_webm_only_pair"))

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
            _push_progress(progress, 0.2, _ui_text(language, "progress_running_selected_export"))
            execute_export(request, context=context)
        except Exception as exc:
            yield (
                gr.update(value=""),
                gr.update(value=_ui_text(language, "status_error_prefix", error=exc)),
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
            _ui_text(
                language,
                "status_source_mode",
                value=_localized_source_mode(language, source_mode),
            ),
            _ui_text(
                language,
                "status_backend",
                value=_localized_backend_name(language, request.backend_name),
            ),
            _ui_text(
                language,
                "status_export_mode",
                value=_localized_export_mode_name(language, export_mode),
            ),
            _ui_text(language, "status_saved_target", value=request.output_path),
        ]
        _push_progress(progress, 1.0, _ui_text(language, "progress_direct_conversion_complete"))
        yield (
            gr.update(value="\n".join(_collect_existing_files(collected_paths))),
            gr.update(value="\n".join(status_lines)),
        )

    default_matanyone_python = str(resolve_matanyone_python(matanyone_root, args.matanyone_python))

    def build_cli_export_tab(
        *,
        tab_label_key: str,
        source_mode_value: str,
        description_key: str,
        manual_input_placeholder: str,
        examples: list[list[Any]],
        show_alpha_inputs: bool = False,
        manual_alpha_placeholder: str = r"D:\path\to\clip_alpha.mp4",
        show_matanyone_settings: bool = False,
    ) -> None:
        with gr.TabItem(_ui_text(default_language, tab_label_key)) as cli_tab_item:
            cli_description = gr.Markdown(_ui_text(default_language, description_key))
            register_language_target(
                cli_tab_item,
                lambda lang, _meta, _ratio, key=tab_label_key: gr.update(label=_ui_text(lang, key)),
            )
            register_language_target(
                cli_description,
                lambda lang, _meta, _ratio, key=description_key: gr.update(value=_ui_text(lang, key)),
            )

            source_mode_state = gr.State(source_mode_value)

            with gr.Row():
                cli_export_mode = gr.Radio(
                    choices=_localized_export_mode_choices(default_language),
                    value="video",
                    label=_ui_text(default_language, "cli_export_mode_label"),
                )
                register_language_target(
                    cli_export_mode,
                    lambda lang, _meta, _ratio: gr.update(
                        choices=_localized_export_mode_choices(lang),
                        label=_ui_text(lang, "cli_export_mode_label"),
                    ),
                )

            with gr.Row():
                cli_input_upload = gr.File(
                    type="filepath",
                    label=_ui_text(default_language, "input_file_label"),
                )
                cli_input_path = gr.Textbox(
                    label=_ui_text(default_language, "manual_input_label"),
                    placeholder=manual_input_placeholder,
                )
                register_language_target(
                    cli_input_upload,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "input_file_label")),
                )
                register_language_target(
                    cli_input_path,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "manual_input_label")),
                )

            if show_alpha_inputs:
                with gr.Row():
                    cli_alpha_upload: Any = gr.File(
                        type="filepath",
                        label=_ui_text(default_language, "alpha_video_label"),
                    )
                    cli_alpha_path: Any = gr.Textbox(
                        label=_ui_text(default_language, "manual_alpha_label"),
                        placeholder=manual_alpha_placeholder,
                    )
                    register_language_target(
                        cli_alpha_upload,
                        lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "alpha_video_label")),
                    )
                    register_language_target(
                        cli_alpha_path,
                        lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "manual_alpha_label")),
                    )
            else:
                cli_alpha_upload = gr.State(None)
                cli_alpha_path = gr.State("")

            cli_output_path = gr.Textbox(
                label=_ui_text(default_language, "output_path_label"),
                placeholder=_ui_text(default_language, "output_path_placeholder"),
            )
            register_language_target(
                cli_output_path,
                lambda lang, _meta, _ratio: gr.update(
                    label=_ui_text(lang, "output_path_label"),
                    placeholder=_ui_text(lang, "output_path_placeholder"),
                ),
            )

            with gr.Accordion(_ui_text(default_language, "general_output_settings"), open=True) as cli_general_output_settings:
                with gr.Row():
                    cli_video_format = gr.Dropdown(
                        choices=["mp4", "webm"],
                        value="mp4",
                        label=_ui_text(default_language, "regular_video_format_label"),
                    )
                    cli_animated_format = gr.Dropdown(
                        choices=["webp", "gif", "both"],
                        value="webp",
                        label=_ui_text(default_language, "animated_format_label"),
                    )
                    cli_frame_format = gr.Dropdown(
                        choices=["webp", "png"],
                        value="webp",
                        label=_ui_text(default_language, "frame_format_label"),
                    )
                with gr.Row():
                    cli_regular_fps = gr.Number(value=0, precision=0, label=_ui_text(default_language, "video_fps_override_label"))
                    cli_animated_fps = gr.Number(value=10, precision=0, label=_ui_text(default_language, "animated_fps_label"))
                    cli_max_frames = gr.Number(value=0, precision=0, label=_ui_text(default_language, "max_frames_all_label"))
                    cli_interval = gr.Number(value=1.0, label=_ui_text(default_language, "frame_interval_label"))
                with gr.Row():
                    cli_size = gr.Textbox(value="", label=_ui_text(default_language, "output_size_label"))
                    cli_corner_radius = gr.Slider(minimum=0, maximum=128, step=1, value=0, label=_ui_text(default_language, "corner_radius_label"))
                    cli_keep_frames = gr.Checkbox(value=False, label=_ui_text(default_language, "keep_intermediate_frames_label"))
                    cli_no_bg_removal = gr.Checkbox(value=False, label=_ui_text(default_language, "skip_background_removal_label"))
                cli_work_dir = gr.Textbox(
                    value="",
                    label=_ui_text(default_language, "work_dir_label"),
                    placeholder=r"D:\path\to\temp",
                )
                with gr.Row():
                    cli_bg_preset = gr.Dropdown(
                        choices=_localized_background_preset_choices(default_language),
                        value="white",
                        label=_ui_text(default_language, "background_preset_label"),
                    )
                    cli_bg_custom = gr.Textbox(value="", label=_ui_text(default_language, "custom_rgb_background_label"))
                    cli_bg_image = gr.File(type="filepath", file_types=["image"], label=_ui_text(default_language, "background_image_label"))
                cli_rembg_model = gr.Dropdown(
                    choices=cli_module.MODEL_CHOICES,
                    value=cli_module.MODEL_CHOICES[0],
                    label=_ui_text(default_language, "rembg_model_label"),
                )
            register_language_target(
                cli_general_output_settings,
                lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "general_output_settings")),
            )
            for component, key in [
                (cli_video_format, "regular_video_format_label"),
                (cli_animated_format, "animated_format_label"),
                (cli_frame_format, "frame_format_label"),
                (cli_regular_fps, "video_fps_override_label"),
                (cli_animated_fps, "animated_fps_label"),
                (cli_max_frames, "max_frames_all_label"),
                (cli_interval, "frame_interval_label"),
                (cli_size, "output_size_label"),
                (cli_corner_radius, "corner_radius_label"),
                (cli_keep_frames, "keep_intermediate_frames_label"),
                (cli_no_bg_removal, "skip_background_removal_label"),
                (cli_work_dir, "work_dir_label"),
                (cli_bg_custom, "custom_rgb_background_label"),
                (cli_bg_image, "background_image_label"),
                (cli_rembg_model, "rembg_model_label"),
            ]:
                register_language_target(
                    component,
                    lambda lang, _meta, _ratio, text_key=key: gr.update(label=_ui_text(lang, text_key)),
                )
            register_language_target(
                cli_bg_preset,
                lambda lang, _meta, _ratio: gr.update(
                    label=_ui_text(lang, "background_preset_label"),
                    choices=_localized_background_preset_choices(lang),
                ),
            )

            if show_matanyone_settings:
                with gr.Accordion(_ui_text(default_language, "matanyone_backend_settings"), open=False) as cli_matanyone_settings:
                    with gr.Row():
                        cli_matanyone_root: Any = gr.Textbox(
                            value=str(matanyone_root),
                            label=_ui_text(default_language, "matanyone_root_label"),
                        )
                        cli_matanyone_python: Any = gr.Textbox(
                            value=default_matanyone_python,
                            label=_ui_text(default_language, "matanyone_python_label"),
                        )
                    with gr.Row():
                        cli_matanyone_model: Any = gr.Dropdown(
                            choices=MATANYONE_MODEL_CHOICES,
                            value="MatAnyone 2",
                            label=_ui_text(default_language, "matanyone_model_label"),
                        )
                        cli_matanyone_device: Any = gr.Dropdown(
                            choices=MATANYONE_DEVICE_CHOICES,
                            value=args.device,
                            label=_ui_text(default_language, "matanyone_device_label"),
                        )
                        cli_matanyone_profile: Any = gr.Dropdown(
                            choices=MATANYONE_PROFILE_CHOICES,
                            value=args.performance_profile,
                            label=_ui_text(default_language, "performance_profile_label"),
                        )
                        cli_matanyone_sam: Any = gr.Dropdown(
                            choices=MATANYONE_SAM_MODEL_CHOICES,
                            value=args.sam_model_type,
                            label=_ui_text(default_language, "sam_model_type_label"),
                        )
                    with gr.Row():
                        cli_matanyone_cpu_threads: Any = gr.Number(value=0, precision=0, label=_ui_text(default_language, "cpu_threads_label"))
                        cli_matanyone_frame_limit: Any = gr.Number(value=0, precision=0, label=_ui_text(default_language, "frame_limit_label"))
                        cli_matanyone_video_target_fps: Any = gr.Number(value=0.0, label=_ui_text(default_language, "video_target_fps_label"))
                        cli_matanyone_output_fps: Any = gr.Number(value=0.0, label=_ui_text(default_language, "output_fps_override_label"))
                    with gr.Row():
                        cli_matanyone_select_frame: Any = gr.Number(value=0, precision=0, label=_ui_text(default_language, "select_frame_label"))
                        cli_matanyone_end_frame: Any = gr.Number(value=0, precision=0, label=_ui_text(default_language, "end_frame_label"))
                    with gr.Row():
                        cli_positive_points: Any = gr.Textbox(
                            value="",
                            lines=4,
                            label=_ui_text(default_language, "positive_points_label"),
                            placeholder="320,180",
                        )
                        cli_negative_points: Any = gr.Textbox(
                            value="",
                            lines=4,
                            label=_ui_text(default_language, "negative_points_label"),
                            placeholder="16,16",
                        )
                    register_language_target(
                        cli_matanyone_settings,
                        lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "matanyone_backend_settings")),
                    )
                    for component, key in [
                        (cli_matanyone_root, "matanyone_root_label"),
                        (cli_matanyone_python, "matanyone_python_label"),
                        (cli_matanyone_model, "matanyone_model_label"),
                        (cli_matanyone_device, "matanyone_device_label"),
                        (cli_matanyone_profile, "performance_profile_label"),
                        (cli_matanyone_sam, "sam_model_type_label"),
                        (cli_matanyone_cpu_threads, "cpu_threads_label"),
                        (cli_matanyone_frame_limit, "frame_limit_label"),
                        (cli_matanyone_video_target_fps, "video_target_fps_label"),
                        (cli_matanyone_output_fps, "output_fps_override_label"),
                        (cli_matanyone_select_frame, "select_frame_label"),
                        (cli_matanyone_end_frame, "end_frame_label"),
                        (cli_positive_points, "positive_points_label"),
                        (cli_negative_points, "negative_points_label"),
                    ]:
                        register_language_target(
                            component,
                            lambda lang, _meta, _ratio, text_key=key: gr.update(label=_ui_text(lang, text_key)),
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

            cli_run_button = gr.Button(
                _ui_text(
                    default_language,
                    "run_tab_button",
                    tab_label=_ui_text(default_language, tab_label_key),
                )
            )
            cli_export_files = gr.Textbox(
                label=_ui_text(default_language, "cli_export_outputs_label"),
                lines=6,
                interactive=False,
                elem_classes=["vbr-output-box"],
            )
            cli_export_status = gr.Textbox(
                label=_ui_text(default_language, "cli_export_status_label"),
                lines=6,
                value=_ui_text(default_language, "cli_idle_status"),
                elem_classes=["vbr-status-box"],
            )
            register_language_target(
                cli_run_button,
                lambda lang, _meta, _ratio, key=tab_label_key: gr.update(
                    value=_ui_text(lang, "run_tab_button", tab_label=_ui_text(lang, key))
                ),
            )
            register_language_target(
                cli_export_files,
                lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "cli_export_outputs_label")),
            )
            register_language_target(
                cli_export_status,
                lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "cli_export_status_label")),
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
                    ui_language,
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

    theme = gr.themes.Soft(
        primary_hue="orange",
        secondary_hue="amber",
        neutral_hue="stone",
    )

    css = """
    body {
      background:
        radial-gradient(circle at top left, rgba(245, 158, 11, 0.08), transparent 30%),
        linear-gradient(180deg, #fffdf9 0%, #f8f5ef 100%);
      font-family: "Segoe UI Variable Text", "Yu Gothic UI", "Segoe UI", sans-serif;
    }
    .gradio-container {
      max-width: 1280px !important;
      margin: 0 auto;
      padding-bottom: 40px !important;
    }
    .gradio-container .block.hide-container {
      padding-left: 0 !important;
      padding-right: 0 !important;
    }
    .vbr-hero {
      margin-bottom: 0.9rem;
      padding: 24px 26px !important;
      border-radius: 28px !important;
      border: 1px solid rgba(217, 119, 6, 0.18) !important;
      background: linear-gradient(135deg, rgba(255, 252, 247, 0.98) 0%, rgba(255, 247, 237, 0.95) 100%) !important;
      box-shadow: 0 18px 40px rgba(28, 25, 23, 0.06);
    }
    .vbr-hero-copy,
    .vbr-mission {
      margin-bottom: 0.55rem;
      padding: 0 4px;
    }
    .vbr-device-hint {
      margin-bottom: 0.9rem;
    }
    .vbr-device-hint .prose {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(214, 211, 209, 0.9);
      background: rgba(255, 255, 255, 0.78);
    }
    .vbr-language-switch {
      margin: 0.85rem 0 1.2rem;
    }
    .vbr-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      flex-wrap: wrap;
      margin-bottom: 0.15rem;
    }
    .vbr-title-copy {
      flex: 1 1 360px;
      min-width: 250px;
    }
    .vbr-title h1 {
      margin: 0;
      font-size: clamp(2.3rem, 4vw, 3.3rem);
      line-height: 1.02;
      letter-spacing: -0.05em;
    }
    .vbr-title-preview {
      flex: 0 0 auto;
      width: min(250px, 100%);
      padding: 8px;
      border-radius: 24px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid rgba(217, 119, 6, 0.16);
      box-shadow: 0 14px 30px rgba(28, 25, 23, 0.07);
      display: block;
    }
    .vbr-title-preview img {
      width: 100%;
      max-height: 170px;
      object-fit: cover;
      border-radius: 16px;
      display: block;
    }
    .vbr-info-box textarea,
    .vbr-status-box textarea,
    .vbr-output-box textarea {
      background: rgba(255, 252, 247, 0.88) !important;
    }
    .vbr-status-box textarea {
      border-color: rgba(217, 119, 6, 0.22) !important;
    }
    .ma2-preview-card {
      border: 1px solid rgba(217, 119, 6, 0.14);
      border-radius: 22px;
      padding: 16px;
      background: linear-gradient(180deg, #fffdf9 0%, #fff7ed 100%);
      box-shadow: 0 14px 28px rgba(28, 25, 23, 0.05);
    }
    .ma2-preview-title {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 12px;
    }
    .ma2-preview-media {
      width: 100%;
      max-height: 320px;
      object-fit: contain;
      border-radius: 14px;
      background: #fffaf3;
      display: block;
    }
    .ma2-preview-name {
      margin-top: 12px;
      color: #57534e;
      font-size: 0.92rem;
      word-break: break-all;
    }
    .ma2-download-link {
      display: inline-block;
      margin-top: 12px;
      padding: 10px 14px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
      color: #fff !important;
      box-shadow: 0 10px 20px rgba(234, 88, 12, 0.18);
    }
    .gradio-container .gallery {
      gap: 12px !important;
    }
    .gradio-container .gallery-item {
      min-height: 90px;
      border-radius: 18px !important;
      box-shadow: 0 10px 18px rgba(28, 25, 23, 0.05);
    }
    @media (max-width: 720px) {
      .gradio-container {
        padding-bottom: 28px !important;
      }
      .vbr-title-preview {
        width: 100%;
      }
      .vbr-title-preview img {
        max-height: 220px;
      }
    }
    """

    with gr.Blocks(title=_ui_text(default_language, "app_title"), theme=theme) as demo:
        app_title_html = gr.HTML(_build_app_title_html(default_language), elem_classes=["vbr-hero"])
        app_summary_markdown = gr.Markdown(
            _ui_text(default_language, "app_summary"),
            elem_classes=["vbr-hero-copy"],
        )
        device_hint_markdown = gr.Markdown(
            _build_device_hint_html(
                device_name,
                sam_model_type,
                results_root,
                default_language,
            ),
            elem_classes=["vbr-device-hint"],
        )
        mission_markdown = gr.Markdown(
            _ui_text(default_language, "mission"),
            elem_classes=["vbr-mission"],
        )
        with gr.Row():
            ui_language = gr.Radio(
                choices=LANGUAGE_CHOICES,
                value=default_language,
                label="Language / 言語",
                elem_classes=["vbr-language-switch"],
            )
        register_language_target(
            app_title_html,
            lambda lang, _meta, _ratio: gr.update(value=_build_app_title_html(lang)),
        )
        register_language_target(
            app_summary_markdown,
            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "app_summary")),
        )
        register_language_target(
            device_hint_markdown,
            lambda lang, _meta, _ratio: gr.update(
                value=_build_device_hint_html(
                    device_name,
                    sam_model_type,
                    results_root,
                    lang,
                )
            ),
        )
        register_language_target(
            mission_markdown,
            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "mission")),
        )

        with gr.Tabs(selected="matanyone2"):
            with gr.TabItem(_ui_text(default_language, "tab_mp4_converter"), id="mp4_converter") as mp4_converter_tab:
                mp4_header_markdown = gr.Markdown(_ui_text(default_language, "mp4_header"))
                mp4_description_markdown = gr.Markdown(_ui_text(default_language, "mp4_description"))
                register_language_target(
                    mp4_converter_tab,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "tab_mp4_converter")),
                )
                register_language_target(
                    mp4_header_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "mp4_header")),
                )
                register_language_target(
                    mp4_description_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "mp4_description")),
                )

                mp4_converter_state = gr.State({})

                with gr.Row():
                    with gr.Column(scale=2):
                        mp4_step1_markdown = gr.Markdown(_ui_text(default_language, "step1_upload_mp4"))
                        mp4_converter_input = gr.Video(label=_ui_text(default_language, "input_mp4_label"))
                        mp4_converter_load_button = gr.Button(
                            value=_ui_text(default_language, "load_video_button"),
                            interactive=True,
                        )
                    with gr.Column(scale=2):
                        mp4_converter_info = gr.Textbox(
                            label=_ui_text(default_language, "video_info_label"),
                            lines=4,
                            value=_ui_text(default_language, "load_mp4_info"),
                            elem_classes=["vbr-info-box"],
                        )
                        mp4_converter_resize_preview = gr.Textbox(
                            label=_ui_text(default_language, "resize_preview_label"),
                            lines=2,
                            value=_build_resize_ratio_text(None, 1.0, default_language),
                            elem_classes=["vbr-info-box"],
                        )
                        mp4_converter_status = gr.Textbox(
                            label=_ui_text(default_language, "workflow_status_label"),
                            lines=7,
                            value=_ui_text(default_language, "mp4_idle_status"),
                            elem_classes=["vbr-status-box"],
                        )
                register_language_target(
                    mp4_step1_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step1_upload_mp4")),
                )
                register_language_target(
                    mp4_converter_input,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "input_mp4_label")),
                )
                register_language_target(
                    mp4_converter_load_button,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "load_video_button")),
                )
                register_language_target(
                    mp4_converter_info,
                    lambda lang, meta, _ratio: gr.update(
                        label=_ui_text(lang, "video_info_label"),
                        value=_build_video_info_text(meta, lang) if meta else _ui_text(lang, "load_mp4_info"),
                    ),
                )
                register_language_target(
                    mp4_converter_resize_preview,
                    lambda lang, meta, ratio: gr.update(
                        label=_ui_text(lang, "resize_preview_label"),
                        value=_build_resize_ratio_text(meta, ratio, lang),
                    ),
                )
                register_language_target(
                    mp4_converter_status,
                    lambda lang, meta, _ratio: gr.update(
                        label=_ui_text(lang, "workflow_status_label"),
                        value=_ui_text(lang, "mp4_ready_status") if meta else _ui_text(lang, "mp4_idle_status"),
                    ),
                )

                gr.Markdown("---")
                mp4_step2_markdown = gr.Markdown(_ui_text(default_language, "step2_export_settings"))
                with gr.Accordion(_ui_text(default_language, "animated_output_settings"), open=True) as mp4_output_settings:
                    mp4_settings_hint_markdown = gr.Markdown(
                        _ui_text(default_language, "mp4_settings_hint")
                    )
                    with gr.Row():
                        mp4_output_summary = gr.Textbox(
                            value=_ui_text(default_language, "always_generates_both"),
                            label=_ui_text(default_language, "export_output_label"),
                            interactive=False,
                        )
                        mp4_converter_fps = gr.Slider(
                            minimum=1,
                            maximum=30,
                            step=1,
                            value=10,
                            label=_ui_text(default_language, "export_fps_label"),
                            info=_ui_text(default_language, "lower_fps_smaller_info"),
                        )
                        mp4_converter_resize_ratio = gr.Slider(
                            minimum=0.1,
                            maximum=1.0,
                            step=0.05,
                            value=1.0,
                            label=_ui_text(default_language, "resize_ratio_label"),
                            info=_ui_text(default_language, "resize_ratio_info"),
                        )
                    with gr.Row():
                        mp4_converter_max_frames = gr.Number(
                            value=150,
                            precision=0,
                            label=_ui_text(default_language, "max_frames_all_label"),
                        )
                        mp4_converter_convert_button = gr.Button(
                            value=_ui_text(default_language, "convert_mp4_button"),
                            interactive=False,
                            variant="primary",
                        )
                register_language_target(
                    mp4_step2_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step2_export_settings")),
                )
                register_language_target(
                    mp4_output_settings,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "animated_output_settings")),
                )
                register_language_target(
                    mp4_settings_hint_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "mp4_settings_hint")),
                )
                register_language_target(
                    mp4_output_summary,
                    lambda lang, _meta, _ratio: gr.update(
                        label=_ui_text(lang, "export_output_label"),
                        value=_ui_text(lang, "always_generates_both"),
                    ),
                )
                register_language_target(
                    mp4_converter_fps,
                    lambda lang, _meta, _ratio: gr.update(
                        label=_ui_text(lang, "export_fps_label"),
                        info=_ui_text(lang, "lower_fps_smaller_info"),
                    ),
                )
                register_language_target(
                    mp4_converter_resize_ratio,
                    lambda lang, _meta, _ratio: gr.update(
                        label=_ui_text(lang, "resize_ratio_label"),
                        info=_ui_text(lang, "resize_ratio_info"),
                    ),
                )
                register_language_target(
                    mp4_converter_max_frames,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "max_frames_all_label")),
                )
                register_language_target(
                    mp4_converter_convert_button,
                    lambda lang, meta, _ratio: gr.update(
                        value=_ui_text(lang, "convert_mp4_button"),
                        interactive=bool(meta),
                    ),
                )

                gr.Markdown("---")
                mp4_step3_markdown = gr.Markdown(_ui_text(default_language, "step3_preview_download"))
                mp4_preview_hint_markdown = gr.Markdown(_ui_text(default_language, "mp4_preview_hint"))
                with gr.Row():
                    mp4_converter_webp_preview = gr.HTML(visible=False)
                    mp4_converter_gif_preview = gr.HTML(visible=False)
                register_language_target(
                    mp4_step3_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step3_preview_download")),
                )
                register_language_target(
                    mp4_preview_hint_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "mp4_preview_hint")),
                )

                mp4_converter_reset_outputs = [
                    mp4_converter_state,
                    mp4_converter_info,
                    mp4_converter_resize_preview,
                    mp4_converter_webp_preview,
                    mp4_converter_gif_preview,
                    mp4_converter_status,
                    mp4_converter_convert_button,
                ]

                mp4_converter_load_button.click(
                    fn=load_mp4_converter_video,
                    inputs=[mp4_converter_input, mp4_converter_resize_ratio, ui_language],
                    outputs=mp4_converter_reset_outputs,
                    show_progress="full",
                )

                mp4_converter_resize_ratio.change(
                    fn=update_mp4_resize_preview,
                    inputs=[mp4_converter_state, mp4_converter_resize_ratio, ui_language],
                    outputs=[mp4_converter_resize_preview],
                    queue=False,
                    show_progress=False,
                )

                mp4_converter_convert_button.click(
                    fn=convert_mp4_to_animated,
                    inputs=[
                        mp4_converter_input,
                        mp4_converter_state,
                        mp4_converter_fps,
                        mp4_converter_resize_ratio,
                        mp4_converter_max_frames,
                        ui_language,
                    ],
                    outputs=[
                        mp4_converter_webp_preview,
                        mp4_converter_gif_preview,
                        mp4_converter_status,
                    ],
                    show_progress="full",
                )

                mp4_converter_input.change(
                    fn=restart_mp4_converter,
                    inputs=[ui_language],
                    outputs=mp4_converter_reset_outputs,
                    queue=False,
                    show_progress=False,
                )

                mp4_converter_input.clear(
                    fn=restart_mp4_converter,
                    inputs=[ui_language],
                    outputs=mp4_converter_reset_outputs,
                    queue=False,
                    show_progress=False,
                )

                if mp4_converter_examples:
                    gr.Examples(examples=mp4_converter_examples, inputs=[mp4_converter_input])

            build_cli_export_tab(
                tab_label_key="tab_advanced_rembg",
                source_mode_value="regular",
                description_key="advanced_rembg_desc",
                manual_input_placeholder=r"D:\path\to\input.mp4",
                examples=advanced_rembg_examples,
            )

            # ========== MatAnyone2 Tab (Pure MatAnyone app.py implementation) ==========
            with gr.TabItem(_ui_text(default_language, "tab_matanyone2"), id="matanyone2") as matanyone_tab:
                matanyone_header_markdown = gr.Markdown(_ui_text(default_language, "matanyone_header"))
                matanyone_description_markdown = gr.Markdown(_ui_text(default_language, "matanyone_description"))
                matanyone_description2_markdown = gr.Markdown(_ui_text(default_language, "matanyone_description_2"))
                register_language_target(
                    matanyone_tab,
                    lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "tab_matanyone2")),
                )
                register_language_target(
                    matanyone_header_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "matanyone_header")),
                )
                register_language_target(
                    matanyone_description_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "matanyone_description")),
                )
                register_language_target(
                    matanyone_description2_markdown,
                    lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "matanyone_description_2")),
                )

                with gr.Tabs(selected="matanyone2_video"):
                    # Video Tab
                    with gr.TabItem(_ui_text(default_language, "tab_video"), id="matanyone2_video") as matanyone_video_tab:
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
                                    label=_ui_text(default_language, "label_model_selection"),
                                    info=_ui_text(default_language, "info_choose_model"),
                                    interactive=True,
                                )
                                ma2_video_performance_profile = gr.Radio(
                                    choices=PROFILE_CHOICES,
                                    value=args.performance_profile,
                                    label=_ui_text(default_language, "performance_profile_label"),
                                    info=_ui_text(default_language, "info_profile_video"),
                                    interactive=True,
                                )
                            with gr.Accordion(_ui_text(default_language, "matting_settings_label"), open=False) as ma2_video_matting_settings:
                                with gr.Row():
                                    ma2_video_erode = gr.Slider(
                                        label=_ui_text(default_language, "label_erode_kernel"),
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info=_ui_text(default_language, "info_erode_kernel"),
                                        interactive=True,
                                    )
                                    ma2_video_dilate = gr.Slider(
                                        label=_ui_text(default_language, "label_dilate_kernel"),
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info=_ui_text(default_language, "info_dilate_kernel"),
                                        interactive=True,
                                    )
                                with gr.Row():
                                    ma2_video_start_frame = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label=_ui_text(default_language, "label_start_frame"),
                                        info=_ui_text(default_language, "info_start_frame"),
                                        visible=False,
                                    )
                                    ma2_video_end_frame = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label=_ui_text(default_language, "label_track_end_frame"),
                                        visible=False,
                                    )
                                with gr.Row():
                                    ma2_video_point_prompt = gr.Radio(
                                        choices=_localized_point_prompt_choices(default_language),
                                        value="Positive",
                                        label=_ui_text(default_language, "label_point_prompt"),
                                        info=_ui_text(default_language, "info_point_prompt"),
                                        interactive=False,
                                    )
                                    ma2_video_mask_dropdown = gr.Dropdown(
                                        multiselect=True,
                                        value=[],
                                        label=_ui_text(default_language, "label_mask_selection"),
                                        info=_ui_text(default_language, "info_mask_selection"),
                                        interactive=False,
                                    )

                        gr.Markdown("---")

                        with gr.Column():
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_video_step1_markdown = gr.Markdown(_ui_text(default_language, "step1_upload_video"))
                                with gr.Column(scale=2):
                                    ma2_video_step2_title = gr.Markdown(
                                        _ui_text(default_language, "step2_add_masks"),
                                    )
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_video_input = gr.Video(label=_ui_text(default_language, "input_video_label"))
                                    ma2_load_video_button = gr.Button(value=_ui_text(default_language, "load_video_button"), interactive=True)
                                with gr.Column(scale=2):
                                    ma2_video_info = gr.Textbox(
                                        label=_ui_text(default_language, "video_info_label"),
                                        value=_ui_text(default_language, "default_video_info"),
                                        elem_classes=["vbr-info-box"],
                                    )
                                    ma2_video_template_frame = gr.Image(
                                        type="pil",
                                        label=_ui_text(default_language, "interactive_frame_label"),
                                        interactive=True,
                                    )
                                    with gr.Row():
                                        ma2_video_clear_button = gr.Button(
                                            value=_ui_text(default_language, "clear_clicks_button"), interactive=False
                                        )
                                        ma2_video_add_mask_button = gr.Button(
                                            value=_ui_text(default_language, "add_mask_button"), interactive=False
                                        )
                                        ma2_video_remove_mask_button = gr.Button(
                                            value=_ui_text(default_language, "remove_masks_button"), interactive=False
                                        )
                                        ma2_video_matting_button = gr.Button(
                                            value=_ui_text(default_language, "video_matting_button"), interactive=False
                                        )

                            gr.Markdown("---")
                            with gr.Accordion(_ui_text(default_language, "animated_output_settings"), open=True) as ma2_animated_output_settings:
                                ma2_video_settings_hint_markdown = gr.Markdown(
                                    _ui_text(default_language, "matanyone_video_settings_hint")
                                )
                                with gr.Row():
                                    ma2_export_fps = gr.Slider(
                                        minimum=5,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        label=_ui_text(default_language, "export_fps_label"),
                                        info=_ui_text(default_language, "lower_fps_smaller_info"),
                                        interactive=True,
                                    )
                                    ma2_export_max_frames = gr.Slider(
                                        minimum=30,
                                        maximum=300,
                                        step=10,
                                        value=150,
                                        label=_ui_text(default_language, "label_max_frames_simple"),
                                        info=_ui_text(default_language, "info_limit_frames"),
                                        interactive=True,
                                    )
                                    ma2_export_bounce = gr.Checkbox(
                                        value=False,
                                        label=_ui_text(default_language, "label_bounce_loop"),
                                        info=_ui_text(default_language, "info_bounce_loop"),
                                        interactive=True,
                                    )

                            gr.Markdown("---")

                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_video_foreground_output = gr.Video(
                                        label=_ui_text(default_language, "foreground_output_label"), visible=False
                                    )
                                with gr.Column(scale=2):
                                    ma2_video_alpha_output = gr.Video(
                                        label=_ui_text(default_language, "alpha_output_label"), visible=False
                                    )
                            ma2_video_status = gr.Textbox(
                                label=_ui_text(default_language, "workflow_status_label"),
                                lines=6,
                                value=_ui_text(default_language, "matanyone_video_idle_status"),
                                elem_classes=["vbr-status-box"],
                            )

                            gr.Markdown("---")
                            ma2_step3_markdown = gr.Markdown(_ui_text(default_language, "step3_preview_download"))
                            ma2_video_preview_hint_markdown = gr.Markdown(_ui_text(default_language, "matanyone_video_preview_hint"))
                            with gr.Row():
                                ma2_webp_preview = gr.HTML(visible=False)
                                ma2_gif_preview = gr.HTML(visible=False)
                        register_language_target(
                            matanyone_video_tab,
                            lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "tab_video")),
                        )
                        register_language_target(
                            ma2_video_matting_settings,
                            lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "matting_settings_label")),
                        )
                        register_language_target(
                            ma2_video_step1_markdown,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step1_upload_video")),
                        )
                        register_language_target(
                            ma2_video_step2_title,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step2_add_masks")),
                        )
                        for component, key in [
                            (ma2_video_model_selection, "label_model_selection"),
                            (ma2_video_performance_profile, "performance_profile_label"),
                            (ma2_video_erode, "label_erode_kernel"),
                            (ma2_video_dilate, "label_dilate_kernel"),
                            (ma2_video_start_frame, "label_start_frame"),
                            (ma2_video_end_frame, "label_track_end_frame"),
                            (ma2_video_mask_dropdown, "label_mask_selection"),
                            (ma2_video_input, "input_video_label"),
                            (ma2_video_info, "video_info_label"),
                            (ma2_video_template_frame, "interactive_frame_label"),
                            (ma2_video_foreground_output, "foreground_output_label"),
                            (ma2_video_alpha_output, "alpha_output_label"),
                            (ma2_video_status, "workflow_status_label"),
                            (ma2_export_fps, "export_fps_label"),
                            (ma2_export_max_frames, "label_max_frames_simple"),
                        ]:
                            register_language_target(
                                component,
                                lambda lang, _meta, _ratio, text_key=key: gr.update(label=_ui_text(lang, text_key)),
                            )
                        register_language_target(
                            ma2_video_model_selection,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_model_selection"),
                                info=_ui_text(lang, "info_choose_model"),
                            ),
                        )
                        register_language_target(
                            ma2_video_performance_profile,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "performance_profile_label"),
                                info=_ui_text(lang, "info_profile_video"),
                            ),
                        )
                        register_language_target(
                            ma2_video_erode,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_erode_kernel"),
                                info=_ui_text(lang, "info_erode_kernel"),
                            ),
                        )
                        register_language_target(
                            ma2_video_dilate,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_dilate_kernel"),
                                info=_ui_text(lang, "info_dilate_kernel"),
                            ),
                        )
                        register_language_target(
                            ma2_video_start_frame,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_start_frame"),
                                info=_ui_text(lang, "info_start_frame"),
                            ),
                        )
                        register_language_target(
                            ma2_video_point_prompt,
                            lambda lang, _meta, _ratio: gr.update(
                                choices=_localized_point_prompt_choices(lang),
                                label=_ui_text(lang, "label_point_prompt"),
                                info=_ui_text(lang, "info_point_prompt"),
                            ),
                        )
                        register_language_target(
                            ma2_video_mask_dropdown,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_mask_selection"),
                                info=_ui_text(lang, "info_mask_selection"),
                            ),
                        )
                        for component, key in [
                            (ma2_load_video_button, "load_video_button"),
                            (ma2_video_clear_button, "clear_clicks_button"),
                            (ma2_video_add_mask_button, "add_mask_button"),
                            (ma2_video_remove_mask_button, "remove_masks_button"),
                            (ma2_video_matting_button, "video_matting_button"),
                        ]:
                            register_language_target(
                                component,
                                lambda lang, _meta, _ratio, text_key=key: gr.update(value=_ui_text(lang, text_key)),
                            )
                        register_language_target(
                            ma2_animated_output_settings,
                            lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "animated_output_settings")),
                        )
                        register_language_target(
                            ma2_video_settings_hint_markdown,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "matanyone_video_settings_hint")),
                        )
                        register_language_target(
                            ma2_export_fps,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "export_fps_label"),
                                info=_ui_text(lang, "lower_fps_smaller_info"),
                            ),
                        )
                        register_language_target(
                            ma2_export_max_frames,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_max_frames_simple"),
                                info=_ui_text(lang, "info_limit_frames"),
                            ),
                        )
                        register_language_target(
                            ma2_export_bounce,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_bounce_loop"),
                                info=_ui_text(lang, "info_bounce_loop"),
                            ),
                        )
                        register_language_target(
                            ma2_step3_markdown,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step3_preview_download")),
                        )
                        register_language_target(
                            ma2_video_preview_hint_markdown,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "matanyone_video_preview_hint")),
                        )

                        ma2_video_reset_outputs = [
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
                            ma2_video_remove_mask_button,
                            ma2_video_mask_dropdown,
                            ma2_video_info,
                            ma2_video_step2_title,
                            ma2_webp_preview,
                            ma2_gif_preview,
                            ma2_video_status,
                        ]

                        # Event handlers for Video tab
                        ma2_load_video_button.click(
                            fn=get_frames_from_video_v2,
                            inputs=[ma2_video_input, ma2_video_state, ma2_video_performance_profile, ui_language],
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
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_video_mask_dropdown,
                                ma2_video_step2_title,
                                ma2_webp_preview,
                                ma2_gif_preview,
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
                                ui_language,
                            ],
                            outputs=[
                                ma2_video_foreground_output,
                                ma2_video_alpha_output,
                                ma2_webp_preview,
                                ma2_gif_preview,
                                ma2_video_status,
                            ],
                            show_progress="full",
                        )

                        ma2_video_mask_dropdown.change(
                            fn=show_mask_v2,
                            inputs=[ma2_video_state, ma2_video_interactive_state, ma2_video_mask_dropdown],
                            outputs=[ma2_video_template_frame],
                        )

                        ma2_video_input.change(
                            fn=restart_video_v2,
                            inputs=[ui_language],
                            outputs=ma2_video_reset_outputs,
                            queue=False,
                            show_progress=False,
                        )

                        ma2_video_input.clear(
                            fn=restart_video_v2,
                            inputs=[ui_language],
                            outputs=ma2_video_reset_outputs,
                            queue=False,
                            show_progress=False,
                        )

                        ma2_video_clear_button.click(
                            fn=clear_click_v2,
                            inputs=[ma2_video_state, ma2_video_click_state],
                            outputs=[ma2_video_template_frame, ma2_video_click_state],
                        )

                        if matanyone_video_examples:
                            gr.Examples(examples=matanyone_video_examples, inputs=[ma2_video_input])

                    # Image Tab
                    with gr.TabItem(_ui_text(default_language, "tab_image_advanced")) as matanyone_image_tab:
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
                                    label=_ui_text(default_language, "label_model_selection"),
                                    info=_ui_text(default_language, "info_choose_model"),
                                    interactive=True,
                                )
                                ma2_image_performance_profile = gr.Radio(
                                    choices=PROFILE_CHOICES,
                                    value=args.performance_profile,
                                    label=_ui_text(default_language, "performance_profile_label"),
                                    info=_ui_text(default_language, "info_profile_image"),
                                    interactive=True,
                                )
                            with gr.Accordion(_ui_text(default_language, "matting_settings_label"), open=False) as ma2_image_matting_settings:
                                with gr.Row():
                                    ma2_image_erode = gr.Slider(
                                        label=_ui_text(default_language, "label_erode_kernel"),
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info=_ui_text(default_language, "info_erode_kernel"),
                                        interactive=True,
                                    )
                                    ma2_image_dilate = gr.Slider(
                                        label=_ui_text(default_language, "label_dilate_kernel"),
                                        minimum=0,
                                        maximum=30,
                                        step=1,
                                        value=10,
                                        info=_ui_text(default_language, "info_dilate_kernel"),
                                        interactive=True,
                                    )
                                with gr.Row():
                                    ma2_image_refine_iter = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=10,
                                        label=_ui_text(default_language, "label_refine_iterations"),
                                        info=_ui_text(default_language, "info_refine_iterations"),
                                        visible=False,
                                    )
                                    ma2_image_track_end = gr.Slider(
                                        minimum=1,
                                        maximum=100,
                                        step=1,
                                        value=1,
                                        label=_ui_text(default_language, "label_track_end_frame"),
                                        visible=False,
                                    )
                                with gr.Row():
                                    ma2_image_point_prompt = gr.Radio(
                                        choices=_localized_point_prompt_choices(default_language),
                                        value="Positive",
                                        label=_ui_text(default_language, "label_point_prompt"),
                                        info=_ui_text(default_language, "info_point_prompt"),
                                        interactive=True,
                                        visible=False,
                                    )
                                    ma2_image_mask_dropdown = gr.Dropdown(
                                        multiselect=True,
                                        value=[],
                                        label=_ui_text(default_language, "label_mask_selection"),
                                        info=_ui_text(default_language, "info_mask_selection"),
                                        visible=False,
                                    )

                        gr.Markdown("---")

                        with gr.Column():
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_image_step1_markdown = gr.Markdown(_ui_text(default_language, "step1_upload_image"))
                                with gr.Column(scale=2):
                                    ma2_image_step2_title = gr.Markdown(
                                        _ui_text(default_language, "step2_add_masks"),
                                        visible=False,
                                    )
                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_image_input = gr.Image(label=_ui_text(default_language, "input_image_label"))
                                    ma2_load_image_button = gr.Button(value=_ui_text(default_language, "load_image_button"), interactive=True)
                                with gr.Column(scale=2):
                                    ma2_image_info = gr.Textbox(
                                        label=_ui_text(default_language, "image_info_label"),
                                        visible=False,
                                        elem_classes=["vbr-info-box"],
                                    )
                                    ma2_image_template_frame = gr.Image(
                                        type="pil",
                                        label=_ui_text(default_language, "interactive_frame_label"),
                                        interactive=True,
                                        visible=False,
                                    )
                                    with gr.Row():
                                        ma2_image_clear_button = gr.Button(
                                            value=_ui_text(default_language, "clear_clicks_button"), interactive=True, visible=False
                                        )
                                        ma2_image_add_mask_button = gr.Button(
                                            value=_ui_text(default_language, "add_mask_button"), interactive=True, visible=False
                                        )
                                        ma2_image_remove_mask_button = gr.Button(
                                            value=_ui_text(default_language, "remove_masks_button"), interactive=True, visible=False
                                        )
                                        ma2_image_matting_button = gr.Button(
                                            value=_ui_text(default_language, "image_matting_button"), interactive=True, visible=False
                                        )

                            gr.Markdown("---")

                            with gr.Row():
                                with gr.Column(scale=2):
                                    ma2_image_foreground_output = gr.Image(
                                        type="pil", label=_ui_text(default_language, "foreground_output_label"), visible=False
                                    )
                                with gr.Column(scale=2):
                                    ma2_image_alpha_output = gr.Image(
                                        type="pil", label=_ui_text(default_language, "alpha_output_label"), visible=False
                                    )
                        register_language_target(
                            matanyone_image_tab,
                            lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "tab_image_advanced")),
                        )
                        register_language_target(
                            ma2_image_matting_settings,
                            lambda lang, _meta, _ratio: gr.update(label=_ui_text(lang, "matting_settings_label")),
                        )
                        register_language_target(
                            ma2_image_step1_markdown,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step1_upload_image")),
                        )
                        register_language_target(
                            ma2_image_step2_title,
                            lambda lang, _meta, _ratio: gr.update(value=_ui_text(lang, "step2_add_masks")),
                        )
                        for component, key in [
                            (ma2_image_model_selection, "label_model_selection"),
                            (ma2_image_performance_profile, "performance_profile_label"),
                            (ma2_image_erode, "label_erode_kernel"),
                            (ma2_image_dilate, "label_dilate_kernel"),
                            (ma2_image_refine_iter, "label_refine_iterations"),
                            (ma2_image_track_end, "label_track_end_frame"),
                            (ma2_image_mask_dropdown, "label_mask_selection"),
                            (ma2_image_input, "input_image_label"),
                            (ma2_image_info, "image_info_label"),
                            (ma2_image_template_frame, "interactive_frame_label"),
                            (ma2_image_foreground_output, "foreground_output_label"),
                            (ma2_image_alpha_output, "alpha_output_label"),
                        ]:
                            register_language_target(
                                component,
                                lambda lang, _meta, _ratio, text_key=key: gr.update(label=_ui_text(lang, text_key)),
                            )
                        register_language_target(
                            ma2_image_model_selection,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_model_selection"),
                                info=_ui_text(lang, "info_choose_model"),
                            ),
                        )
                        register_language_target(
                            ma2_image_performance_profile,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "performance_profile_label"),
                                info=_ui_text(lang, "info_profile_image"),
                            ),
                        )
                        register_language_target(
                            ma2_image_erode,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_erode_kernel"),
                                info=_ui_text(lang, "info_erode_kernel"),
                            ),
                        )
                        register_language_target(
                            ma2_image_dilate,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_dilate_kernel"),
                                info=_ui_text(lang, "info_dilate_kernel"),
                            ),
                        )
                        register_language_target(
                            ma2_image_refine_iter,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_refine_iterations"),
                                info=_ui_text(lang, "info_refine_iterations"),
                            ),
                        )
                        register_language_target(
                            ma2_image_point_prompt,
                            lambda lang, _meta, _ratio: gr.update(
                                choices=_localized_point_prompt_choices(lang),
                                label=_ui_text(lang, "label_point_prompt"),
                                info=_ui_text(lang, "info_point_prompt"),
                            ),
                        )
                        register_language_target(
                            ma2_image_mask_dropdown,
                            lambda lang, _meta, _ratio: gr.update(
                                label=_ui_text(lang, "label_mask_selection"),
                                info=_ui_text(lang, "info_mask_selection"),
                            ),
                        )
                        for component, key in [
                            (ma2_load_image_button, "load_image_button"),
                            (ma2_image_clear_button, "clear_clicks_button"),
                            (ma2_image_add_mask_button, "add_mask_button"),
                            (ma2_image_remove_mask_button, "remove_masks_button"),
                            (ma2_image_matting_button, "image_matting_button"),
                        ]:
                            register_language_target(
                                component,
                                lambda lang, _meta, _ratio, text_key=key: gr.update(value=_ui_text(lang, text_key)),
                            )

                        # Event handlers for Image tab
                        ma2_load_image_button.click(
                            fn=get_frames_from_image_v2,
                            inputs=[ma2_image_input, ma2_image_state, ma2_image_performance_profile, ui_language],
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
                                ui_language,
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

                        if matanyone_image_examples:
                            gr.Examples(examples=matanyone_image_examples, inputs=[ma2_image_input])

            # ========== End MatAnyone2 Tab ==========

                    build_cli_export_tab(
                        tab_label_key="tab_advanced_pair",
                        source_mode_value="matanyone_pair",
                        description_key="advanced_pair_desc",
                        manual_input_placeholder=r"D:\path\to\clip_fg.mp4 or D:\path\to\MatAnyone_dir",
                        examples=cli_examples_by_mode["matanyone_pair"],
                        show_alpha_inputs=True,
                    )

        ui_language.change(
            fn=apply_ui_language,
            inputs=[ui_language, mp4_converter_state, mp4_converter_resize_ratio],
            outputs=[component for component, _builder in language_update_targets],
            queue=False,
            show_progress=False,
        )

        demo.queue()
        try:
            demo.launch(
                debug=args.debug,
                server_name=args.server_name,
                server_port=args.port,
                share=args.share,
                allowed_paths=[str(results_root.resolve())],
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
