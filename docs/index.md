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
  - icon: "🎬"
    title: Full Video Export
    details: Split a video into frames, remove the background, and rebuild it as a video.
  - icon: "🧩"
    title: Transparent Frame Export
    details: Export transparent WebP / PNG frames at fixed intervals.
  - icon: "✨"
    title: Animated WebP / GIF
    details: Generate transparent animated WebP or GIF files directly from your video.
  - icon: "🖼️"
    title: Background Replacement
    details: Replace the removed background with a solid color or a custom background image.
  - icon: "🤖"
    title: Multiple AI Models
    details: Switch between isnet-general-use, u2net, u2netp, u2net_human_seg, and silueta.
  - icon: "⚙️"
    title: No FFmpeg Required
    details: All processing is done with Python and the bundled libraries.
---

## Latest Experiment

The fire-effect clip comparison is documented in [Examples](/guide/examples). For `assets/onizuka_fire_motion.mp4`, `silueta` gave the best overall balance, while `u2net` was the most stable fallback when you want a cleaner silhouette.

## Documentation Color Map

<div class="vp-badges">
  <img src="https://img.shields.io/badge/Base_BG-%23F2EFEB-F2EFEB?style=flat-square" alt="Base BG #F2EFEB">
  <img src="https://img.shields.io/badge/Accent_1-%23F22233-F22233?style=flat-square" alt="Accent 1 #F22233">
  <img src="https://img.shields.io/badge/Accent_2-%23F28705-F28705?style=flat-square" alt="Accent 2 #F28705">
  <img src="https://img.shields.io/badge/Accent_3-%23F25D27-F25D27?style=flat-square" alt="Accent 3 #F25D27">
  <img src="https://img.shields.io/badge/Accent_4-%23F20505-F20505?style=flat-square" alt="Accent 4 #F20505">
</div>

## Social Card Check

You can preview the current social card with [OpenGraphs Debugger](https://www.opengraphs.com/tools/og-debugger).

- Test URL: `https://sunwood-ai-labs.github.io/video-background-remover-cli/`
