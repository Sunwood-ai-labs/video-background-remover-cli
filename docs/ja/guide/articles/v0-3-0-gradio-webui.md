# v0.3.0: Gradio WebUI が主役になったリリース

公開日: 2026-03-15

![Animated WebP preview](/media/output_animated.webp)

`video-background-remover-cli v0.3.0` は、このリポジトリが「便利な CLI ツール」から「背景除去とアニメーション書き出しを実用的に回せるアプリ」に大きく寄ったリリースでした。

CLI の価値はそのまま残っていますが、主役は明らかに Gradio WebUI に移っています。この変化が大きいのは、次のような作業が 1 つの画面でかなり自然に回るようになったからです。

- MatAnyone で動画を対話的にマスクする
- 結果を animated `webp` / `gif` として確認して落とす
- 2x2 / 3x3 の tiled 動画を分割して使い回せる形にする
- 目的ごとに UI の入口が分かれていて迷いにくい

## いちばん大きい変化は WebUI が主導線になったこと

このリリースでは、WebUI のタブ構成そのものがかなり整理されました。

- `MP4 -> WebP/GIF`
- `Advanced rembg`
- `MatAnyone2`
- `MatAnyone2 Tile`
- `Advanced fg+alpha pair`

この分け方の良さは、1 本の万能画面に寄せず、やりたいことごとに導線を分離している点です。

- 背景除去なしでアニメーション化したい
- MatAnyone で本格的にマスクを作りたい
- 既存の foreground / alpha ペアを再利用したい
- tiled 動画を分割して各 tile を素材化したい

それぞれの意図に対して、かなり素直な入口になりました。

## MatAnyone2 がメインの動画背景除去フローになった

いちばん分かりやすい中心は `MatAnyone2 > Video` です。

流れとしてはとてもシンプルで、

1. 動画を読み込む
2. フレーム上をクリックしてマスクを作る
3. `Video Matting` を実行する
4. animated `webp` / `gif` をその場で確認してダウンロードする

という順で完結します。

大きいのは、ただ動くだけではなく、素材を書き出すための周辺 UI もかなり整ったことです。

- プレビューカード
- ダウンロードボタン
- 出力 FPS
- 最大フレーム数
- bounce loop
- ステータス表示

このあたりがそろったことで、「試せる UI」ではなく「使える UI」に近づきました。

## MP4 -> WebP/GIF がかなり便利

背景除去を通さず、そのままアニメーション変換できる `MP4 -> WebP/GIF` タブも地味に大きい追加です。

このタブでは、

- 元動画の情報確認
- FPS 調整
- リサイズ比調整
- animated `webp` と `gif` の同時生成

ができるので、

- SNS 用に軽い素材を作りたい
- Web 掲載用の animated WebP がほしい
- 背景除去は不要だが GIF は必要

といった用途にかなりそのまま使えます。

## MatAnyone2 Tile で 2x2 / 3x3 の分割書き出しができるようになった

今回の `v0.3.0` で特に面白いのが `MatAnyone2 Tile` です。

2x2 または 3x3 に並んだ tiled 動画に対して、

1. 通常の MatAnyone フローでマスクを作る
2. foreground / alpha をまとめて出す
3. その後に tile 分割する
4. tile ごとに animated `webp` / `gif` を生成する

という流れを取れます。

![MatAnyone2 Tile preview grid](/media/matanyone2_tile/webui-preview-en.png)

これによって、

- 複数素材が 1 本に並んでいる動画
- スプライトシート的な使い方
- あとから各 tile を別素材として再利用したいケース

にかなり相性の良い workflow になりました。

しかもこの release では、Tile 専用の出力フォルダ整理、resume、auto-detect picker、Tile 用 examples まで入っていて、途中からのやり直しもかなりしやすくなっています。

## UI の日英切り替えと docs 整備も効いている

WebUI 全体で日本語 / 英語の切り替えが入ったのも大きい点です。マッティング系の UI はどうしても専門用語が多くなりがちですが、ラベルや説明が読みやすくなるだけでかなり触りやすさが変わります。

docs 側も同時に強化されました。

- README の拡充
- VitePress ガイドの更新
- Tile スクリーンショット
- sample `webp` / `gif` asset
- docs-backed release notes

この流れがあるので、release を「短い履歴」として見せつつ、こうした記事ページで「なぜ大きいのか」を別で読める形にしやすくなっています。

## 検証

この release では次の確認が通っています。

- `uv run --extra webui python -m unittest tests.test_webui`
- `uv run python -m unittest discover -s tests`
- `uv run --extra dev python -m build`
- `npm run docs:build`

## 関連リンク

- [リリースまとめページ](/ja/guide/releases)
- [GitHub release v0.3.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/releases/tag/v0.3.0)
- [Compare v0.2.0...v0.3.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/compare/v0.2.0...v0.3.0)
- [Repository](https://github.com/Sunwood-ai-labs/video-background-remover-cli)
