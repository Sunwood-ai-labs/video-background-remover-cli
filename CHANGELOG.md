# Changelog

## 0.2.0 - 2026-03-07

`0.1.1` から `0.1.6` はデプロイ確認やリリース同期のためのマイナーバージョンとして扱い、このリリースノートでは `0.1.0` から蓄積した実質的な変更点をまとめています。

### Added

- PyPI 配布を前提にしたパッケージ構成を追加し、`video-background-remover` / `vbr` コマンドと `python -m video_background_remover_cli` 実行をサポート
- `README.pypi.md`、`project.scripts`、`project.urls` などの配布メタデータを追加し、インストール後の利用導線を整理
- VitePress ベースのドキュメントサイトを追加し、英語・日本語のガイド、使用例、モデル説明を公開
- 火炎エフェクト付きサンプル動画のモデル比較実験を追加し、比較用 WebP・マスク画像・再実行スクリプトを同梱
- CLI の挙動とリリース用バージョン同期を検証するテストを追加

### Changed

- README をパッケージ利用前提の構成に更新し、`pip install video-background-remover` と `uv sync --extra dev` を案内
- ドキュメントのテーマ、OGP、favicon、X Card メタデータを整備し、GitHub Pages 公開向けの見た目と共有体験を改善
- リリース時にタグから `pyproject.toml`、`src/video_background_remover_cli/__init__.py`、`uv.lock` を同期する仕組みを導入

### Internal

- PyPI Trusted Publishing 用の GitHub Actions ワークフローを追加
- GitHub Pages へのドキュメントデプロイを自動化
- 既存の `main.py` エントリーポイントを薄くし、パッケージ側 CLI へ責務を集約
