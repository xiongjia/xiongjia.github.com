import { createContext } from 'react'

import { createPref } from '@/prefs/pref'

import type { Dictionary } from './dictionary'
import { defaultLocale, locales, type Locale } from './locales'

/*
 * Locale state, as data.
 *
 * The context object lives on its own so the provider (a component) and the hook (`useI18n`) can
 * each live in their own module — React Fast Refresh only works when a file exports components and
 * nothing else.
 */

export const localePref = createPref({
  key: 'frontend-lab:locale',
  values: locales,
  fallback: defaultLocale,
})

/** A generated entry set: English plus optional translations. */
export type Localized<T> = { en: T; zh?: T }

export type Picked<T> = {
  value: T
  /** True when the current locale has no entry and the English one is being shown. */
  missing: boolean
}

export type I18nValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  /** Dictionary for the current locale. */
  t: Dictionary
  /** Pick the current locale's entry, falling back to English and reporting the fallback. */
  pick: <T>(localized: Localized<T>) => Picked<T>
}

export const I18nContext = createContext<I18nValue | null>(null)
