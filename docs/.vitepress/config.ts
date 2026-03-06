import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Video Background Remover CLI',
  description: 'Remove backgrounds from videos using rembg and OpenCV',

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      dir: 'en',
      title: 'Video Background Remover CLI',
      description: 'Remove backgrounds from videos using rembg and OpenCV',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/en/' },
          { text: 'Guide', link: '/en/guide/getting-started' },
        ],
        sidebar: [
          {
            text: 'Guide',
            items: [
              { text: 'Getting Started', link: '/en/guide/getting-started' },
              { text: 'Usage', link: '/en/guide/usage' },
              { text: 'Models', link: '/en/guide/models' },
              { text: 'Examples', link: '/en/guide/examples' },
            ],
          },
        ],
      },
    },
    ja: {
      label: '日本語',
      lang: 'ja',
      dir: 'ja',
      title: 'Video Background Remover CLI',
      description: 'rembg と OpenCV を使って動画から背景を除去する CLI ツール',
      themeConfig: {
        nav: [
          { text: 'ホーム', link: '/ja/' },
          { text: 'ガイド', link: '/ja/guide/getting-started' },
        ],
        sidebar: [
          {
            text: 'ガイド',
            items: [
              { text: 'はじめに', link: '/ja/guide/getting-started' },
              { text: '使い方', link: '/ja/guide/usage' },
              { text: 'モデル', link: '/ja/guide/models' },
              { text: '使用例', link: '/ja/guide/examples' },
            ],
          },
        ],
      },
    },
  },

  themeConfig: {
    logo: '/logo.png',
    socialLinks: [
      {
        icon: 'github',
        link: 'https://github.com/Sunwood-ai-labs/video-background-remover-cli',
      },
    ],
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2024 Sunwood AI Labs',
    },
  },
})
