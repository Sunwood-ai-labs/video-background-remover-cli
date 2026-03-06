# 使い方

```bash
python main.py INPUT OUTPUT [options]
```

## 通常の動画出力

通常の動画出力ではアルファ付き動画は生成しません。背景を明示したい場合は `--bg-color` または `--bg-image` を指定してください。

```bash
python main.py input.mp4 output.mp4 --bg-color white
python main.py input.mp4 output.mp4 --bg-image background.jpg
python main.py input.mp4 output.mp4 --fps 30
```

## 透過フレームの書き出し

`--interval` を指定すると、`OUTPUT` はファイルではなく出力先ディレクトリ名として扱われます。

```bash
python main.py input.mp4 output/frames --interval 0.5 --format webp
python main.py input.mp4 output/frames --interval 1 --format png
```

## アニメーション WebP / GIF 出力

`--animated both` を指定すると、同じベース名で `.webp` と `.gif` の両方を出力します。

```bash
python main.py input.mp4 output/output_animated.webp --animated webp
python main.py input.mp4 output/output.gif --animated gif --webp-fps 8
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

## オプション一覧

| オプション | 説明 |
| --- | --- |
| `--model` | 背景除去モデル。デフォルトは `isnet-general-use` |
| `--fps` | 通常の動画出力時の FPS。未指定なら入力動画を使用 |
| `--bg-color` | 背景色。`white` / `black` / `green` / `blue` / `red` / `gray` / `transparent` または `255,128,0` 形式 |
| `--bg-image` | 背景に合成する画像パス |
| `--keep-frames` | 中間フレームを削除せず保持 |
| `--work-dir` | 作業用フレームの保存先 |
| `--interval` | 指定秒数ごとにフレームを抽出 |
| `--format` | `--interval` モードの出力形式。`webp` または `png` |
| `--animated` | アニメーション出力。`webp` / `gif` / `both` |
| `--webp-fps` | アニメーション出力時の FPS |
| `--max-frames` | アニメーション出力時の最大フレーム数 |
