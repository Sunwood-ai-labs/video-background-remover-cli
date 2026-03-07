import { defineConfig } from 'vitepress'

const siteTitle = 'Video Background Remover CLI'
const siteDescription = 'Remove backgrounds from videos using rembg and OpenCV'
const siteOrigin = 'https://sunwood-ai-labs.github.io'
const siteBase = '/video-background-remover-cli/'
const siteUrl = new URL(siteBase, siteOrigin).toString()
const ogImageUrl = new URL('ogp.jpg', siteUrl).toString()

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

function toPagePath(page: string): string {
  if (page === 'index.md') {
    return '/'
  }

  if (page.endsWith('/index.md')) {
    return `/${page.replace(/\/index\.md$/, '')}/`
  }

  return `/${page.replace(/\.md$/, '')}`
}

function toAbsoluteUrl(path: string): string {
  return new URL(path.replace(/^\/+/, ''), siteUrl).toString()
}

export default defineConfig({
  title: siteTitle,
  description: siteDescription,
  base: siteBase,
  lang: 'en-US',
  dir: 'ltr',
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${siteBase}favicon.svg` }],
    ['link', { rel: 'icon', href: `${siteBase}favicon.ico` }],
    ['meta', { name: 'theme-color', content: '#f25d27' }],
  ],
  sitemap: {
    hostname: siteUrl,
  },
  transformHead({ page, title, description }) {
    const pageUrl = toAbsoluteUrl(toPagePath(page))
    const locale = page.startsWith('ja/') ? 'ja_JP' : 'en_US'

    return [
      ['link', { rel: 'canonical', href: pageUrl }],
      ['meta', { property: 'og:type', content: 'website' }],
      ['meta', { property: 'og:site_name', content: siteTitle }],
      ['meta', { property: 'og:locale', content: locale }],
      ['meta', { property: 'og:title', content: title }],
      ['meta', { property: 'og:description', content: description }],
      ['meta', { property: 'og:url', content: pageUrl }],
      ['meta', { property: 'og:image', content: ogImageUrl }],
      ['meta', { property: 'og:image:type', content: 'image/jpeg' }],
      ['meta', { property: 'og:image:width', content: '1376' }],
      ['meta', { property: 'og:image:height', content: '768' }],
      [
        'meta',
        {
          property: 'og:image:alt',
          content: 'Video Background Remover CLI social preview card',
        },
      ],
      ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
      ['meta', { name: 'twitter:site', content: '@hAru_mAki_ch' }],
      ['meta', { name: 'twitter:title', content: title }],
      ['meta', { name: 'twitter:description', content: description }],
      ['meta', { name: 'twitter:image', content: ogImageUrl }],
      ['meta', { name: 'twitter:image:alt', content: 'Video Background Remover CLI social preview card' }],
    ]
  },

  locales: {
    root: {
      label: 'English',
      lang: 'en-US',
      title: siteTitle,
      description: siteDescription,
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
      title: siteTitle,
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
