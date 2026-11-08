import { useEffect, useMemo, type ReactNode } from 'react'

import { usePref } from '@/prefs/pref'

import { I18nContext, localePref, type I18nValue, type Localized, type Picked } from './context'
import { dictionaries } from './dictionary'
import { defaultLocale, htmlLang } from './locales'

/**
 * Locale provider: the locale is a persisted preference like the theme. UI strings come from the
 * typed dictionaries; page and demo titles come from their own locale files, so `pick()` handles
 * the fallback and tells the caller when the reader is looking at English.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = usePref(localePref)

  useEffect(() => {
    // `lang` drives hyphenation, screen-reader pronunciation and font fallback — not a decoration.
    if (document.documentElement.lang !== htmlLang[locale]) {
      document.documentElement.lang = htmlLang[locale]
    }
  }, [locale])

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      setLocale,
      t: dictionaries[locale],
      pick<T>(localized: Localized<T>): Picked<T> {
        const translated = locale === defaultLocale ? undefined : localized[locale]
        return translated === undefined
          ? { value: localized.en, missing: locale !== defaultLocale }
          : { value: translated, missing: false }
      },
    }),
    [locale, setLocale],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
