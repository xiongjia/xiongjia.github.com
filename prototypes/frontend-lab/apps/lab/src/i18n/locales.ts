/*
 * Locales.
 *
 * This list must match `locales` in `apps/lab/plugins/frontmatter.ts`; `pnpm content:check` compares
 * the two and fails on drift, so the generated registry and the dictionary can never disagree about
 * which languages exist.
 */

export const locales = ['en', 'zh'] as const

export type Locale = (typeof locales)[number]

export const defaultLocale: Locale = 'en'

/** Compact labels for the language switch. */
export const localeLabels: Record<Locale, string> = {
  en: 'EN',
  zh: '中文',
}

/** Full BCP 47 tags for `<html lang>`. */
export const htmlLang: Record<Locale, string> = {
  en: 'en',
  zh: 'zh-CN',
}
