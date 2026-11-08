import { SegmentedControl } from '@frontend-lab/ui'

import { useI18n } from '@/i18n/use-i18n'
import { themeValues, useTheme } from '@/prefs/theme'

/**
 * Light / dark / system. The choice persists in `localStorage` (see `prefs/theme.ts`); `System`
 * keeps following the OS, which is the default so a first visit matches the rest of the desktop.
 */
export function ThemeToggle() {
  const { mode, setMode } = useTheme()
  const { t } = useI18n()

  return (
    <SegmentedControl
      label={t.controls.colorMode}
      value={mode}
      onChange={setMode}
      options={themeValues.map((value) => ({ value, label: t.controls.modes[value] }))}
    />
  )
}
