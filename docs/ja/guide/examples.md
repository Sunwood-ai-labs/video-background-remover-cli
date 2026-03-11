# 使用例

## 出力サンプル

| 種類 | ファイル |
| --- | --- |
| 入力動画 | `assets/onizuka_idle_motion.mp4` |
| アニメーション WebP | `example/output_animated.webp` |
| GIF | `output/output.gif` |
| MatAnyone WebP 2 FPS / 300 px | `output/matanyone_full_2fps_300.webp` |
| MatAnyone WebP 5 FPS / 300 px | `output/matanyone_full_5fps_300.webp` |
| MatAnyone WebP 10 FPS / 300 px | `output/matanyone_full_10fps_300.webp` |
| MatAnyone GIF 10 FPS / 300 px | `output/matanyone_full_10fps_300.gif` |
| 比較用 GIF | `example/onizuka_walk_motion.gif` |
| 比較用 WebP | `example/onizuka_walk_motion.webp` |
| 透過フレーム | `output_frames_webp/` |

## MatAnyone レシピ

### 前景動画 + マスク動画から透過 WebP を作る

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.webp
```

### 軽量プレビュー: 5 FPS / 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_5fps_300.webp --webp-fps 5 --size 300x300
```

### さらに軽いプレビュー: 2 FPS / 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_2fps_300.webp --webp-fps 2 --size 300x300
```

### より滑らかなプレビュー: 10 FPS / 300 px

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.webp --webp-fps 10 --size 300x300
```

### 10 FPS の GIF を作る

```bash
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.gif --animated gif --webp-fps 10 --size 300x300
```

### 白背景の MP4 にフラット化する

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.mp4 --bg-color white
```

### MatAnyone 入力に関するメモ

- マスク動画の白い部分は残り、黒い部分は透明になります。
- 半透明エッジでは、焼き付いた緑背景を軽減する補正を行っています。
- プレビュー用途では `300x300` と `5fps` の組み合わせがバランス良好です。

### 緑フリンジ補正の比較

この比較画像は `assets/MatAnyone_cat3` に対して `soft` / `balanced` / `strong` / `trim` の4段階で補正した例です。`soft` は輪郭を残しやすく、`strong` と `trim` はヒゲやしっぽの緑縁をより強く抑えます。

![MatAnyone 緑フリンジ補正の比較](/media/matanyone/green-cleanup-preview.png)

残留マップでは、補正後も `G > max(R, B)` になっている輪郭ピクセルを強調しています。見た目だけでは判断しづらい細い緑縁の確認に使えます。

![MatAnyone 緑成分の残留マップ](/media/matanyone/green-residual-map.png)

- 比較用の出力は `MatAnyone_cat3_trim_sm0_gb4_rb60_as180_am120_md255.webp` のように補正内容をファイル名へ入れると追跡しやすくなります。
- 略称は `sm=spill margin`、`gb=green bias`、`rb=red boost`、`as=alpha spill`、`am=alpha matte`、`md=max drop` です。

## 実験: 炎エフェクト付きクリップ

検証クリップ: `assets/onizuka_fire_motion.mp4`

使用した設定:

```bash
python main.py assets/onizuka_fire_motion.mp4 output/model.webp --animated webp --webp-fps 8 --model <model>
```

### まとめ

- このクリップでは `silueta` が最もバランス良く仕上がりました。
- `u2net` はシルエットの安定性は高いですが、炎のオーラがかなり消えます。
- `u2net_human_seg` はこのスタイルの強い映像には向いていません。

### モデル比較

| Model | Preview | Runtime | Notes |
| --- | --- | ---: | --- |
| `isnet-general-use` | <img src="/experiments/onizuka_fire_motion/isnet-general-use.webp" alt="isnet-general-use result" width="180"> | 114.44s | 効果表現を少し残す一方で、輪郭周辺にノイズが残ります。 |
| `u2net` | <img src="/experiments/onizuka_fire_motion/u2net.webp" alt="u2net result" width="180"> | 76.42s | シルエットは安定しますが、炎のオーラはかなり消えます。 |
| `u2netp` | <img src="/experiments/onizuka_fire_motion/u2netp.webp" alt="u2netp result" width="180"> | 30.11s | 最速ですが、難しいフレームでは品質が落ちます。 |
| `u2net_human_seg` | <img src="/experiments/onizuka_fire_motion/u2net_human_seg.webp" alt="u2net human seg result" width="180"> | 69.97s | このスタイルでは人物の保持が不十分です。 |
| `silueta` | <img src="/experiments/onizuka_fire_motion/silueta.webp" alt="silueta result" width="180"> | 69.27s | 形状保持とノイズ除去のバランスが最も良好でした。 |

### 比較シート

![Comparison sheet](/experiments/onizuka_fire_motion/comparison_sheet.png)

### マスク比較

![Mask comparison](/experiments/onizuka_fire_motion/comparison_masks.png)

### 実験の再実行

実験設定は `experiments/onizuka_fire_motion/` にあります。

- スクリプト: `experiments/onizuka_fire_motion/run_experiment.py`
- 設定: `experiments/onizuka_fire_motion/experiment_config.json`
- メモ: `experiments/onizuka_fire_motion/README.md`
- 出力先: `output/model_experiments/onizuka_fire_motion/`

リポジトリルートで次を実行します。

```bash
python experiments/onizuka_fire_motion/run_experiment.py
```

追加モデルを試す場合は、`experiments/onizuka_fire_motion/experiment_config.json` の `models` 配列に追加してから再実行してください。
