import { defineConfig } from 'vitepress'

const socialLinks = [
  {
    icon: 'github',
    link: 'https://github.com/Sunwood-ai-labs/video-background-remover-cli',
  },
]

const footer = {
  message: 'Released under the MIT License.',
  copyright: 'Copyright (c) 2024 Sunwood AI Labs',
}

export default defineConfig({
  title: 'Video Background Remover CLI',
  description: 'Remove backgrounds from videos using rembg and OpenCV',
  base: '/video-background-remover-cli/',
  lang: 'en-US',
  dir: 'ltr',

  locales: {
    root: {
      label: 'English',
      lang: 'en-US',
      title: 'Video Background Remover CLI',
      description: 'Remove backgrounds from videos using rembg and OpenCV',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/' },
          { text: 'Guide', link: '/guide/getting-started' },
        ],
        sidebar: [
          {
            text: 'Guide',
            items: [
              { text: 'Getting Started', link: '/guide/getting-started' },
              { text: 'Usage', link: '/guide/usage' },
              { text: 'Models', link: '/guide/models' },
              { text: 'Examples', link: '/guide/examples' },
            ],
          },
        ],
        socialLinks,
        footer,
      },
    },
    ja: {
      label: '\u65e5\u672c\u8a9e',
      lang: 'ja-JP',
      title: 'Video Background Remover CLI',
      description: 'rembg \u3068 OpenCV \u3092\u4f7f\u3063\u3066\u52d5\u753b\u80cc\u666f\u3092\u5207\u308a\u629c\u304f CLI \u30c4\u30fc\u30eb',
      themeConfig: {
        nav: [
          { text: '\u30db\u30fc\u30e0', link: '/ja/' },
          { text: '\u30ac\u30a4\u30c9', link: '/ja/guide/getting-started' },
        ],
        sidebar: [
          {
            text: '\u30ac\u30a4\u30c9',
            items: [
              { text: '\u306f\u3058\u3081\u306b', link: '/ja/guide/getting-started' },
              { text: '\u4f7f\u3044\u65b9', link: '/ja/guide/usage' },
              { text: '\u30e2\u30c7\u30eb', link: '/ja/guide/models' },
              { text: '\u4f7f\u7528\u4f8b', link: '/ja/guide/examples' },
            ],
          },
        ],
        socialLinks,
        footer,
      },
    },
  },

  themeConfig: {
    socialLinks,
    footer,
  },
})
