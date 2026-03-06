---
layout: home

hero:
  name: Video Background Remover CLI
  text: 動画の背景を手早く除去
  tagline: rembg と OpenCV を使って動画背景を切り抜く Python CLI ツール
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
  - icon: 🎬
    title: 動画を書き出し
    details: 動画をフレーム分解し、背景除去後に再び動画として書き出します。
  - icon: 🖼️
    title: 透過フレーム出力
    details: 一定間隔で透過 WebP / PNG フレームを書き出せます。
  - icon: 🌀
    title: アニメーション WebP / GIF
    details: 透過付きのアニメーション WebP や GIF を直接生成できます。
  - icon: 🎨
    title: 背景差し替え
    details: 単色背景や任意の背景画像への合成にも対応しています。
  - icon: 🧠
    title: 複数の AI モデル
    details: isnet-general-use、u2net、u2netp、u2net_human_seg、silueta を切り替えられます。
  - icon: ⚙️
    title: FFmpeg 不要
    details: 主要な処理は Python と依存ライブラリだけで完結します。
---

## 最新の実験結果

炎エフェクト付きの `assets/onizuka_fire_motion.mp4` で比較した結果は [使用例](/ja/guide/examples) にまとめています。このサンプルでは `silueta` が最もバランスが良く、輪郭優先なら `u2net` も安定していました。
