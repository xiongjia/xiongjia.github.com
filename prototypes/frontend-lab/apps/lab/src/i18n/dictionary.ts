/*
 * Typed dictionaries.
 *
 * `en` is the source of truth: its shape becomes the `Dictionary` type, so `zh` fails to compile
 * when a key is missing. Values are plain strings (no JSX, no functions) — anything with a number
 * in it is a template plus `format()` below, which keeps translations reviewable as text.
 *
 * Content and demo labels are *not* here: those live in each locale's own MDX frontmatter.
 */

import type { Locale } from './locales'

export const en = {
  app: {
    name: 'Frontend Lab',
    tagline: 'MDX explains · React components interact · experiments prove',
    progress: 'B7 / B17',
    batch: 'Batch B7 · i18n',
    navLabel: 'Lab',
  },
  nav: {
    home: 'Home',
    index: 'Index',
    allDemos: 'All demos',
    pageBadge: 'page',
    demoBadge: 'demo',
    missingBadge: 'EN',
    missingTitle: 'No translation yet — showing English',
  },
  groups: {
    foundations: 'Foundations',
    interactions: 'Interactions',
    general: 'General',
  } as Record<string, string>,
  home: {
    intro:
      'An experiment lab for frontend techniques: every experiment runs, exposes its source and ships an MDX write-up. Built batch by batch — the roadmap lives in the prototype README.',
    openFirstDemo: 'Open the first demo',
    startWith: 'Start with {title}',
    demosHeading: 'Demos · {count} runnable',
    contentHeading: 'Content · {count} pages',
    footnote:
      'Content comes from content/**/*.mdx and demos from demos/<group>/<name>/ — both indexed at build time, no code change needed.',
  },
  demos: {
    title: 'Demos',
    intro:
      '{count} runnable demos. Each one is a folder under demos/ with a demo.tsx component and a notes.mdx write-up; the registry, the source view and the sidebar entry are generated from it.',
  },
  demo: {
    views: 'Demo views',
    preview: 'Preview',
    source: 'Source',
    notes: 'Notes',
    loading: 'Loading demo…',
    loadingSource: 'Loading source…',
    loadingNotes: 'Loading notes…',
    copy: 'Copy',
    copied: 'Copied',
    copyFailed: 'Copy failed',
    copyTarget: 'source of the demo',
    crashed: 'This demo crashed',
    crashedHint:
      'The error is contained in {slug} — the tabs, the source and every other demo keep working.',
    recover: 'Recover',
    notTranslated: 'The write-up is not translated yet — showing English.',
  },
  content: {
    loading: 'Loading page…',
    notTranslated: 'This page is not translated yet — showing English.',
  },
  notFound: {
    title: 'Page not found',
    body: 'There is no page at this path. Content pages are generated from content/, so a missing page usually means a typo in the URL or a deleted .mdx file.',
    back: 'Back to home',
  },
  controls: {
    colorMode: 'Color mode',
    stylePreset: 'Style preset',
    language: 'Language',
    modes: { light: 'Light', dark: 'Dark', system: 'System' },
    styles: { default: 'Default', sharp: 'Sharp', warm: 'Warm', mono: 'Mono' },
  },
}

export type Dictionary = typeof en

export const zh: Dictionary = {
  app: {
    name: '前端实验室',
    tagline: 'MDX 讲原理 · 组件做交互 · 实验给结论',
    progress: 'B7 / B17',
    batch: '批次 B7 · 国际化',
    navLabel: '实验室',
  },
  nav: {
    home: '首页',
    index: '索引',
    allDemos: '全部示例',
    pageBadge: '文章',
    demoBadge: '示例',
    missingBadge: 'EN',
    missingTitle: '暂无中文译文，显示英文原文',
  },
  groups: {
    foundations: '基础',
    interactions: '交互',
    general: '通用',
  },
  home: {
    intro:
      '一个面向前端技术的实验场：每个实验都能运行、能看到源码，并附一篇 MDX 说明。按批次推进，路线图见原型 README。',
    openFirstDemo: '打开第一个示例',
    startWith: '从「{title}」开始',
    demosHeading: '示例 · {count} 个可运行',
    contentHeading: '文章 · {count} 篇',
    footnote:
      '文章来自 content/**/*.mdx，示例来自 demos/<group>/<name>/——两者都在构建时生成索引，新增文件无需改代码。',
  },
  demos: {
    title: '示例',
    intro:
      '共 {count} 个可运行示例。每个示例都是 demos/ 下的一个目录，包含 demo.tsx 组件和 notes.mdx 说明；注册表、源码视图和侧边栏条目都由它生成。',
  },
  demo: {
    views: '示例视图',
    preview: '预览',
    source: '源码',
    notes: '说明',
    loading: '正在加载示例…',
    loadingSource: '正在加载源码…',
    loadingNotes: '正在加载说明…',
    copy: '复制',
    copied: '已复制',
    copyFailed: '复制失败',
    copyTarget: '示例源码',
    crashed: '示例崩溃了',
    crashedHint: '错误被限制在 {slug} 内——标签页、源码和其他示例都不受影响。',
    recover: '恢复',
    notTranslated: '说明尚未翻译，当前显示英文原文。',
  },
  content: {
    loading: '正在加载页面…',
    notTranslated: '此页尚未翻译，当前显示英文原文。',
  },
  notFound: {
    title: '页面不存在',
    body: '该路径下没有页面。文章由 content/ 生成，缺页通常是 URL 拼写错误或 .mdx 文件已被删除。',
    back: '返回首页',
  },
  controls: {
    colorMode: '配色模式',
    stylePreset: '样式预设',
    language: '语言',
    modes: { light: '浅色', dark: '深色', system: '跟随系统' },
    styles: { default: '默认', sharp: '方正', warm: '暖色', mono: '单色' },
  },
}

export const dictionaries: Record<Locale, Dictionary> = { en, zh }

/** Fill `{name}` placeholders; unknown placeholders are left alone so a typo is visible. */
export function format(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = values[key]
    return value === undefined ? match : String(value)
  })
}
