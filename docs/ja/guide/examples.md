# 使用例

## 出力サンプル

| 種類 | ファイル |
| --- | --- |
| 入力動画 | `assets/onizuka_idle_motion.mp4` |
| アニメーション WebP | `example/output_animated.webp` |
| GIF | `output/output.gif` |
| 比較 GIF | `example/onizuka_walk_motion.gif` |
| 比較 WebP | `example/onizuka_walk_motion.webp` |
| 透過フレーム | `output_frames_webp/` |

## 実験: 炎エフェクト付き動画

検証素材: `assets/onizuka_fire_motion.mp4`

使用した設定:

```bash
python main.py assets/onizuka_fire_motion.mp4 output/model.webp --animated webp --webp-fps 8 --model <model>
```

### 要点

- この素材では `silueta` が最もバランスの良い結果でした。
- `u2net` は輪郭が安定しますが、炎のオーラはかなり消えます。
- `u2net_human_seg` はエフェクトの強いこのサンプルには不向きでした。

### モデル別プレビュー

| Model | WebP | 実行時間 | メモ |
| --- | --- | ---: | --- |
| `isnet-general-use` | <img src="/experiments/onizuka_fire_motion/isnet-general-use.webp" alt="isnet-general-use result" width="180"> | 114.44s | 炎の成分を少し残す一方で、輪郭まわりにノイズも残ります。 |
| `u2net` | <img src="/experiments/onizuka_fire_motion/u2net.webp" alt="u2net result" width="180"> | 76.42s | シルエットは安定しますが、炎のオーラはほぼ消えます。 |
| `u2netp` | <img src="/experiments/onizuka_fire_motion/u2netp.webp" alt="u2netp result" width="180"> | 30.11s | 最速ですが、難しいフレームで崩れやすいです。 |
| `u2net_human_seg` | <img src="/experiments/onizuka_fire_motion/u2net_human_seg.webp" alt="u2net human seg result" width="180"> | 69.97s | このスタイライズされた動画では人物自体を大きく落とします。 |
| `silueta` | <img src="/experiments/onizuka_fire_motion/silueta.webp" alt="silueta result" width="180"> | 69.27s | 形状維持とノイズ抑制のバランスが最も良好でした。 |

### フレーム比較シート

![Comparison sheet](/experiments/onizuka_fire_motion/comparison_sheet.png)

1.0s、3.0s、5.0s、7.0s、9.0s の代表フレームを並べています。どのタイミングで炎が消えるか、どこで被写体が崩れるかをまとめて確認できます。

### マスク比較シート

![Mask comparison](/experiments/onizuka_fire_motion/comparison_masks.png)

アルファマスクを見ると、`u2net_human_seg` がこの素材では大きく崩れている一方で、`silueta`、`u2net`、`isnet-general-use` は被写体の面積を比較的維持しています。

### 実験の再実行方法

追跡している実験定義は `experiments/onizuka_fire_motion/` にあります。

- スクリプト: `experiments/onizuka_fire_motion/run_experiment.py`
- 設定: `experiments/onizuka_fire_motion/experiment_config.json`
- 手順メモ: `experiments/onizuka_fire_motion/README.md`
- 出力先: `output/model_experiments/onizuka_fire_motion/`

リポジトリのルートから実行:

```bash
python experiments/onizuka_fire_motion/run_experiment.py
```

あとでモデルを追加したい場合は `experiments/onizuka_fire_motion/experiment_config.json` の `models` に名前を追加して、同じコマンドを再実行してください。

再生成されるもの:

- `<model>_anim.webp`
- `<model>_anim_frames/`
- `results.csv`
- `alpha_stats.csv`
- `comparison_sheet.png`
- `comparison_masks.png`

## レシピ: 白背景の動画

背景を除去して白で埋めた動画を書き出します。

```bash
python main.py input.mp4 output_white.mp4 --bg-color white
```

## レシピ: 背景画像の合成

任意の背景画像へ被写体を合成します。

```bash
python main.py input.mp4 output_bg.mp4 --bg-image background.jpg
```

## レシピ: 透過アニメーション WebP

透過付きのループ WebP を 10 FPS で出力します。

```bash
python main.py input.mp4 output_animated.webp --animated webp --webp-fps 10
```

## レシピ: アニメーション GIF

GIF を出力します。GIF は半透明を保持できません。

```bash
python main.py input.mp4 output.gif --animated gif --webp-fps 8
```

## レシピ: WebP と GIF の同時出力

1 回の実行で両方の形式を書き出します。

```bash
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

## レシピ: フレーム抽出

0.5 秒ごとに透過 PNG フレームを書き出します。

```bash
python main.py input.mp4 output/frames --interval 0.5 --format png
```

1 秒ごとに透過 WebP フレームを書き出します。

```bash
python main.py input.mp4 output/frames --interval 1 --format webp
```

## レシピ: モデル指定

人物向けモデルを指定して処理します。

```bash
python main.py input.mp4 output.mp4 --model u2net_human_seg --bg-color white
```

## 注意

- モデルの初回読み込みには時間がかかることがあります。
- 長い動画を `--animated gif` で出力するとファイルサイズが大きくなりやすいです。
- 透過を使いたい場合は通常動画よりも `--animated webp` または `--interval` 出力が向いています。
