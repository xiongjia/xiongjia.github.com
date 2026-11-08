import { SegmentedControl } from '@frontend-lab/ui'

import { useI18n } from '@/i18n/use-i18n'
import { localeLabels, locales, type Locale } from '@/i18n/locales'

/**
 * `EN` / `中文`. The choice persists and is applied to `<html lang>` by the provider; the bootstrap
 * script in `index.html` sets the same attribute before first paint.
 */
export function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n()

  return (
    <SegmentedControl
      label={t.controls.language}
      value={locale}
      onChange={(value) => setLocale(value as Locale)}
      options={locales.map((value) => ({ value, label: localeLabels[value] }))}
    />
  )
}
