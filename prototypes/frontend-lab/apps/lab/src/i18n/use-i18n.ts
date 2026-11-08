import { useContext } from 'react'

import { I18nContext, type I18nValue } from './context'

/** Read the current locale, dictionary and picker. Throws outside `I18nProvider`. */
export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}
