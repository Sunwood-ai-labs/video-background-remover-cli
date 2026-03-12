# はじめに

## 必要環境

- Python 3.10 以上
- FFmpeg は不要
- モデルは初回実行時に自動でダウンロードされます

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

### 白背景の動画を書き出す

```bash
python main.py assets/onizuka_idle_motion.mp4 --bg-color white
```

### 透過付きアニメーション WebP を書き出す

```bash
python main.py assets/onizuka_idle_motion.mp4 --animated webp --webp-fps 10
```

### 1秒ごとに透過フレームを書き出す

```bash
python main.py assets/onizuka_idle_motion.mp4 --interval 1 --format webp
```

### MP4 縺ｮ蜃ｺ蜉帙Δ繝ｼ繝峨ｒ譌･譎る俣縺吶ｋ

```bash
python main.py assets/onizuka_idle_motion.mp4 --format mp4 --bg-color white
```

### `300x300` 縺ｫ繝ｪ繧ｵ繧､繧ｺ縺励※蜃ｺ蜉帙☆繧・

```bash
python main.py assets/onizuka_idle_motion.mp4 --animated webp --size 300x300
```

### MatAnyone の前景動画 + マスク動画から透過 WebP を作る

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.webp
```

### MatAnyone の軽量プレビューを作る

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_5fps_300.webp --webp-fps 5 --size 300x300
```
