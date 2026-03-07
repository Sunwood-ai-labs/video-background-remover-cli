---
layout: home

hero:
  name: Video Background Remover CLI
  text: Remove video backgrounds with ease
  tagline: A Python CLI tool powered by rembg and OpenCV for background removal from videos
  image:
    src: /media/output_animated.webp
    alt: Animated transparent WebP output
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/Sunwood-ai-labs/video-background-remover-cli

features:
  - icon: 🎬
    title: Full Video Export
    details: Split a video into frames, remove the background, and rebuild it as a video.
  - icon: 🖼️
    title: Transparent Frame Export
    details: Export transparent WebP / PNG frames at fixed intervals.
  - icon: 🌀
    title: Animated WebP / GIF
    details: Generate transparent animated WebP or GIF files directly from your video.
  - icon: 🎨
    title: Background Replacement
    details: Replace the removed background with a solid color or a custom background image.
  - icon: 🧠
    title: Multiple AI Models
    details: Switch between isnet-general-use, u2net, u2netp, u2net_human_seg, and silueta.
  - icon: ⚙️
    title: No FFmpeg Required
    details: All processing is done with Python and the bundled libraries.
---

## Latest Experiment

The fire-effect clip comparison is documented in [Examples](/guide/examples). For `assets/onizuka_fire_motion.mp4`, `silueta` gave the best overall balance, while `u2net` was the most stable fallback when you want a cleaner silhouette.

## Documentation Accent Prompt

This site's accent palette is based on the following prompt:

```xml
ドキュメントのアクセントで下記のカラーマップを使ってみたら？？
背景は #F2EFEB にしてもいいかも！
<palette>
<color name='イラスト-1' rgb='F22233' r='242' g='33' b='51' />
<color name='イラスト-2' rgb='F28705' r='242' g='135' b='4' />
<color name='イラスト-3' rgb='F2EFEB' r='242' g='238' b='234' />
<color name='イラスト-4' rgb='F25D27' r='242' g='93' b='38' />
<color name='イラスト-5' rgb='F20505' r='242' g='4' b='4' />
</palette>
```
