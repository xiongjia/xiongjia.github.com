import { useI18n } from '@/i18n/use-i18n'
import { styleValues, useStyle, type StylePreset } from '@/prefs/style'

/**
 * Style preset switcher. A native `<select>` on purpose: four options, one selected, keyboard and
 * screen-reader behaviour for free, and the popup is styled by the browser according to
 * `color-scheme` — which is itself part of the theme work.
 */
export function StylePicker() {
  const { preset, setPreset } = useStyle()
  const { t } = useI18n()

  return (
    <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className="sr-only">{t.controls.stylePreset}</span>
      <select
        value={preset}
        onChange={(event) => setPreset(event.target.value as StylePreset)}
        className="h-7 rounded-full border border-border bg-card px-2.5 text-xs font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {styleValues.map((value) => (
          <option key={value} value={value}>
            {t.controls.styles[value]}
          </option>
        ))}
      </select>
    </label>
  )
}
