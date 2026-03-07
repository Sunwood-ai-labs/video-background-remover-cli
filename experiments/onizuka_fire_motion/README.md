# Fire Effect Experiment

このフォルダは追跡される実験定義です。実際の出力は `output/model_experiments/onizuka_fire_motion/` に生成します。

## ファイル

- `run_experiment.py`
  - 設定を読み込み、各モデルを順番に実行して比較結果を再生成します。
- `experiment_config.json`
  - 入力動画、出力先、モデル一覧、`webp_fps`、比較用サンプル位置を管理します。

## モデルを追加するとき

`experiment_config.json` の `models` にモデル名を追加してください。

```json
{
  "models": [
    "isnet-general-use",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
    "new-model-name"
  ]
}
```

## 実行方法

リポジトリのルートから:

```powershell
.\.venv\Scripts\python.exe .\experiments\onizuka_fire_motion\run_experiment.py
```

実験フォルダに移動して実行する場合:

```powershell
cd .\experiments\onizuka_fire_motion
..\..\.venv\Scripts\python.exe .\run_experiment.py
```

上の相対パスは見づらいので、通常はルートから実行する方が安全です。

## 一時的にモデル一覧だけ上書きする

```powershell
.\.venv\Scripts\python.exe .\experiments\onizuka_fire_motion\run_experiment.py --models isnet-general-use u2net silueta
```

## 出力先

以下を `output/model_experiments/onizuka_fire_motion/` に作成または更新します。

- `<model>_anim.webp`
- `<model>_anim_frames\`
- `results.csv`
- `alpha_stats.csv`
- `comparison_sheet.png`
- `comparison_masks.png`

## 補足

- モデルの初回ダウンロードが入ると、その回の `seconds` は長くなります。
- 同じモデル名で再実行した場合、そのモデルの `.webp` と `_frames` だけを上書きします。
- `main.py` の `--animated` 実装に合わせて、出力ベース名は拡張子なしで渡しています。
