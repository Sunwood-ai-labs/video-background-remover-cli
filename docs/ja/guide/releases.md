# リリース

## v0.3.0

リリース日: 2026-03-15

このリリースは [v0.2.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/releases/tag/v0.2.0) 以降の変更をまとめたものです。Gradio アプリをリポジトリの主導線に引き上げ、MatAnyone の書き出しワークフローをより実用的な UI に広げています。

### ハイライト

- 直接 `rembg` を使う書き出しと、対話型の MatAnyone 動画・画像ワークフローをまとめた Gradio 6 WebUI を追加しました。
- メイン導線となる `MatAnyone2` 動画フローを追加し、animated `webp` / `gif`、プレビューカード、ダウンロードボタン、状態表示を強化しました。
- 背景除去なしで animated 変換だけを行う `MP4 -> WebP/GIF` を追加しました。
- 2x2 / 3x3 のタイル動画向けに `MatAnyone2 Tile` を追加し、マッティング後の分割とタイルごとの animated `webp` / `gif` 出力に対応しました。
- Tile 専用の出力フォルダから foreground / alpha を再利用できる resume 導線を追加しました。
- Gradio アプリ全体で日本語と英語の切り替えに対応しました。

### ツールと配布まわり

- CLI と WebUI の両方で使えるように、背景除去ロジックを共通モジュールへ整理しました。
- 管理された Python 環境から WebUI を起動できるように、MatAnyone runtime bridge と package entry point を追加しました。
- Windows での起動安定性と Gradio の起動処理を改善しました。
- `pyproject.toml` と package fallback version code の release version 同期を維持しました。

### ドキュメントとアセット

- README と VitePress ガイドを拡張し、新しい WebUI ワークフローを説明しました。
- Tile ワークフローのスクリーンショットと `webp` / `gif` サンプルを docs に追加しました。
- GitHub release から参照できる docs 側の要約ページとして、このリリースページを追加しました。

### 検証

このリリースでは次の確認を実施しました。

- `uv run --extra webui python -m unittest tests.test_webui`
- `uv run python -m unittest discover -s tests`
- `uv run --extra dev python -m build`
- `npm run docs:build`

### 関連リンク

- [GitHub release for v0.3.0](https://github.com/Sunwood-ai-labs/video-background-remover-cli/releases/tag/v0.3.0)
- [CHANGELOG.md](https://github.com/Sunwood-ai-labs/video-background-remover-cli/blob/main/CHANGELOG.md)
- [記事: Gradio WebUI が主役になったリリース](/ja/guide/articles/v0-3-0-gradio-webui)
