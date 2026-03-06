# 使用例

## 出力サンプル

| 種類 | ファイル |
| --- | --- |
| 入力動画 | `assets/onizuka_idle_motion.mp4` |
| アニメーション WebP | `example/output_animated.webp` |
| GIF | `output/output.gif` |
| 比較用 GIF | `example/onizuka_walk_motion.gif` |
| 比較用 WebP | `example/onizuka_walk_motion.webp` |
| 透過フレーム | `output_frames_webp/` |

## レシピ: 白背景の動画

背景を白で埋めた動画を出力します。

```bash
python main.py input.mp4 output_white.mp4 --bg-color white
```

## レシピ: 背景画像の合成

任意の背景画像を合成します。

```bash
python main.py input.mp4 output_bg.mp4 --bg-image background.jpg
```

## レシピ: 透過アニメーション WebP

透過付きのループ WebP を 10 FPS で出力します。

```bash
python main.py input.mp4 output_animated.webp --animated webp --webp-fps 10
```

## レシピ: アニメーション GIF

GIF を出力します（GIF は半透明をサポートしていません）。

```bash
python main.py input.mp4 output.gif --animated gif --webp-fps 8
```

## レシピ: WebP と GIF の同時出力

1 回の実行で両方のフォーマットを出力します。

```bash
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

## レシピ: フレーム抽出

0.5 秒ごとに透過 PNG フレームを抽出します。

```bash
python main.py input.mp4 output/frames --interval 0.5 --format png
```

1 秒ごとに透過 WebP フレームを抽出します。

```bash
python main.py input.mp4 output/frames --interval 1 --format webp
```

## レシピ: モデルの指定

人物セグメンテーションモデルを使用してより良い結果を得ます。

```bash
python main.py input.mp4 output.mp4 --model u2net_human_seg --bg-color white
```

## 注意事項

- モデルの初回ロードには時間がかかります。
- 長い動画を `--animated gif` で出力するとファイルサイズが大きくなります。
- 透過が必要な場合は、通常の動画書き出しよりも `--animated webp` または `--interval` の使用が適しています。
