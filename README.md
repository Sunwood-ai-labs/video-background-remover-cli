# Video Background Remover

動画から背景を自動除去するツールです。

**RMBG-1.4 モデル使用**（[Xenova/remove-background-web](https://huggingface.co/spaces/Xenova/remove-background-web) と同じ）

## 処理フロー

```
動画 → フレーム分割 → 背景除去 → 動画再構成
```

1. 動画をフレーム画像に分割
2. 各フレームから背景を除去（RMBG-1.4）
3. 処理済みフレームから動画を再構成

## インストール

```bash
cd video-background-remover
pip install -r requirements.txt
```

## 使い方

```bash
# 基本的な使い方（透明背景）
python main.py input.mp4 output.mp4

# 背景色を指定
python main.py input.mp4 output.mp4 --bg-color white
python main.py input.mp4 output.mp4 --bg-color green
python main.py input.mp4 output.mp4 --bg-color "255,128,0"

# 背景画像を指定
python main.py input.mp4 output.mp4 --bg-image background.jpg

# 中間フレームを保持
python main.py input.mp4 output.mp4 --keep-frames
```

## オプション

| オプション | 説明 |
|-----------|------|
| `--model` | 背景除去モデル (デフォルト: `isnet-general-use`) |
| `--fps` | 出力FPS (デフォルト: 元動画と同じ) |
| `--bg-color` | 背景色 (white, black, green, blue, red, gray) |
| `--bg-image` | 背景画像のパス |
| `--keep-frames` | 中間フレーム画像を保持 |
| `--work-dir` | 作業ディレクトリ |

## モデル選択

| モデル | 説明 |
|--------|------|
| `isnet-general-use` | 汎用（デフォルト、Xenova と同等） |
| `u2net` | サリエントオブジェクト検出 |
| `u2netp` | 軽量版 |
| `u2net_human_seg` | 人物セグメンテーション |
| `silueta` | 高品質（遅い） |
