# 使い方

## コマンド形式

```bash
python main.py INPUT [OUTPUT] [options]
```

`OUTPUT` を省略すると、`./output/<入力名>_<timestamp>/` が自動作成され、モードに応じた名前で保存されます。

## 通常動画を書き出す

```bash
python main.py input.mp4 --bg-color white
python main.py input.mov --format mp4 --bg-color white
python main.py input.mp4 output.mp4 --bg-image background.jpg
python main.py input.mp4 output.mp4 --fps 30
python main.py input.mp4 output.mp4 --size 300x300 --bg-color white
```

通常の動画出力ではアルファ透過は保持されません。背景を見せたい場合は `--bg-color` または `--bg-image` を指定してください。

## 透過フレームを書き出す

```bash
python main.py input.mp4 --interval 0.5 --format webp
python main.py input.mp4 output/frames --interval 1 --format png
python main.py input.mp4 output/frames --interval 1 --format webp --size 300x300
```

`--interval` を指定すると、`OUTPUT` はファイルではなくディレクトリとして扱われます。

## アニメーション WebP / GIF を書き出す

```bash
python main.py input.mp4 --animated webp
python main.py input.mp4 --animated webp --size 300x300
python main.py input.mp4 output/output_animated.webp --animated webp --webp-fps 10
python main.py input.mp4 output/output.gif --animated gif --webp-fps 8
python main.py input.mp4 output/output --animated both --webp-fps 8 --max-frames 120
```

`--animated both` を使うと、同じベース名で `.webp` と `.gif` の両方を書き出します。

## MatAnyone の前景 + マスク動画を書き出す

`--matanyone` は次のどちらかを `INPUT` に渡すと使えます。

- `*_fg.*` と対応する `*_alpha.*` を含むディレクトリ
- `clip_fg.mp4` のような前景動画ファイル

使用例:

```bash
python main.py assets/MatAnyone --matanyone output/matanyone.webp
python main.py assets/MatAnyone --matanyone output/matanyone_2fps_300.webp --webp-fps 2 --size 300x300
python main.py assets/MatAnyone --matanyone output/matanyone_5fps_300.webp --webp-fps 5 --size 300x300
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.webp --webp-fps 10 --size 300x300
python main.py assets/MatAnyone --matanyone output/matanyone_10fps_300.gif --animated gif --webp-fps 10 --size 300x300
python main.py assets/MatAnyone --matanyone output/matanyone.mp4 --bg-color white
python main.py assets/MatAnyone --matanyone output/matanyone_frames --interval 0.5 --format png
```

補足:

- 透過アルファはアニメーション `webp`、アニメーション `gif`、間引きフレーム出力で保持されます。
- `.webp` 出力では、与えられたマスク動画を使って透明部分を作成します。
- 半透明の縁では、焼き付いた緑背景を軽減する補正を入れています。
- コンパクトなプレビュー用途なら `--size 300x300` と `--webp-fps 5` の組み合わせがおすすめです。
- 通常の `mp4` は透過を保持できないため、`--bg-color`、`--bg-image`、または黒背景へ合成して保存します。

補正違いを複数書き出して比較するときは、`MatAnyone_cat3_trim_sm0_gb4_rb60_as180_am120_md255.webp` のように補正プロファイルや調整値をファイル名へ含めておくと再確認しやすくなります。

## MatAnyone2 Tile WebUI

`MatAnyone2 Tile` タブは、入力が 2x2 / 3x3 のタイル動画になっているときのための WebUI 導線です。通常の MatAnyone マスク操作で foreground / alpha を作ったあと、完成した結果をタイルごとに分割し、animated `webp` と `gif` を両方出力します。

![MatAnyone2 Tile の再開 picker](/media/matanyone2_tile/webui-resume-en.png)

### Tile workflow

1. `MatAnyone2 Tile` でタイル動画を読み込みます。
2. `2x2` または `3x3` を選び、マスクを追加して `Tile Video Matting` を実行します。
3. 途中から始めたい場合は `既存出力から再開` を開き、自動検出された Tile run folder を選んで読み込みます。
4. `出力 FPS`、`最大フレーム数`、`Bounce Loop` を調整してから、分割 tile 出力を生成します。

### 出力フォルダ構成

- 最初から実行した場合も、既存出力から再開した場合も、成果物は `output/webui/matanyone2_tile/<run-dir>/` にまとまります。
- 分割アニメーションは `tiles_2x2/` または `tiles_3x3/` に保存されます。
- 自動検出一覧は Tile 用 run folder だけに絞っているので見やすく、必要なら絶対パスで任意の run dir や `*_fg.mp4` を直接指定できます。

```text
output/webui/matanyone2_tile/<run-dir>/
├─ <source>.mp4_fg.mp4
├─ <source>.mp4_alpha.mp4
├─ metadata.json
└─ tiles_3x3/
   ├─ tile_01_animated.webp
   ├─ tile_01_animated.gif
   └─ ...
```

![MatAnyone2 Tile の preview grid](/media/matanyone2_tile/webui-preview-en.png)

## オプション一覧

| オプション | 説明 |
| --- | --- |
| `--model` | 背景除去モデル。既定値は `isnet-general-use` |
| `--matanyone` | `INPUT` を MatAnyone ディレクトリまたは `*_fg.*` 前景動画として扱い、対応する `*_alpha.*` を使用します |
| `--alpha-video` | `--matanyone` モード用の明示的なアルファ or マスク動画パス |
| `--fps` | 通常動画出力時の FPS。未指定時は入力動画の FPS |
| `--bg-color` | 背景色。`white`、`black`、`green`、`blue`、`red`、`gray`、`transparent`、または `255,128,0` 形式 |
| `--bg-image` | 背景画像のパス |
| `--size` | 出力サイズ。`WIDTHxHEIGHT` 形式。例: `300x300` |
| `--keep-frames` | 中間フレームを削除せず残します |
| `--work-dir` | 中間フレームの作業ディレクトリ |
| `--interval` | 指定秒ごとにフレームを書き出します |
| `--format` | 透過フレームや MatAnyone WebP には `webp` / `png`、通常動画には `mp4` を使います |
| `--animated` | アニメーション出力モード。`webp`、`gif`、`both` |
| `--webp-fps` | アニメーション出力の FPS |
| `--max-frames` | アニメーション出力時の最大フレーム数 |
