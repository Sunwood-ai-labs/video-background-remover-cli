# はじめに

## 必要な環境

- Python 3.10 以上
- FFmpeg は**不要**です
- AI モデルは初回実行時に自動でダウンロードされます

## インストール

### `pip` を使う場合

```bash
pip install -r requirements.txt
```

### `uv` を使う場合

```bash
uv sync
```

## クイックスタート

### 1. 背景を白で埋めた動画を出力

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_white.mp4 --bg-color white
```

### 2. 透過付きアニメーション WebP を出力

```bash
python main.py assets/onizuka_idle_motion.mp4 output/output_animated.webp --animated webp --webp-fps 10
```

### 3. 1 秒ごとに透過フレームを書き出し

```bash
python main.py assets/onizuka_idle_motion.mp4 output/frames --interval 1 --format webp
```

## 基本的な使い方

```bash
python main.py INPUT OUTPUT [options]
```

| 引数 | 説明 |
| --- | --- |
| `INPUT` | 入力動画ファイルのパス |
| `OUTPUT` | 出力ファイルまたはディレクトリのパス |

オプションの全一覧は[使い方](./usage)のページをご覧ください。
