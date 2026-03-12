---
layout: home

hero:
  name: Video Background Remover CLI
  text: 動画の背景を手軽に切り抜く
  tagline: rembg と OpenCV を使った、背景除去・透過アニメーション出力・MatAnyone 合成に対応する Python CLI ツール
  image:
    src: /media/output_animated.webp
    alt: 透過アニメーション WebP の出力例
  actions:
    - theme: brand
      text: はじめに
      link: /ja/guide/getting-started
    - theme: alt
      text: GitHub
      link: https://github.com/Sunwood-ai-labs/video-background-remover-cli

features:
  - icon: "🎞️"
    title: "通常動画の書き出し"
    details: "動画をフレーム分解し、背景除去後に通常動画として再構成できます。"
  - icon: "🧩"
    title: "透過フレーム出力"
    details: "一定間隔で透過 WebP / PNG フレームを書き出せます。"
  - icon: "✨"
    title: "アニメーション WebP / GIF"
    details: "透過付きのアニメーション WebP や GIF を直接生成できます。"
  - icon: "🫥"
    title: "MatAnyone 対応"
    details: "`*_fg.*` と `*_alpha.*` を組み合わせて透過 WebP や GIF を作成できます。"
  - icon: "🧼"
    title: "緑フリンジ低減"
    details: "MatAnyone の半透明エッジに残る緑背景を軽減してから出力します。"
  - icon: "🤖"
    title: "複数モデル対応"
    details: "isnet-general-use、u2net、u2netp、u2net_human_seg、silueta を切り替えられます。"
---

## 最新の追加機能

MatAnyone 向けの透過 WebP / GIF / PNG フレーム出力、`300x300` と `5fps` を使った軽量プレビュー例、エッジの緑フリンジ低減をドキュメントに追加しました。

## 最新の実験

炎エフェクト付きの `assets/onizuka_fire_motion.mp4` 比較は [使用例](/ja/guide/examples) にまとめています。今回の比較では `silueta` が最もバランス良く、`u2net` は安定した代替候補でした。
