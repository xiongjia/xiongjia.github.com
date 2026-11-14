import { contentPages } from '@/generated/content-index'
import { demos } from '@/generated/demo-registry'
import {
  CommandPalette,
  useCommandShortcut,
  type PaletteCommand,
} from '@frontend-lab/command-palette'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { format } from '../i18n/dictionary'
import { localeLabels, locales } from '../i18n/locales'
import { useI18n } from '../i18n/use-i18n'
import { styleValues, useStyle } from '../prefs/style'
import { themeValues, useTheme } from '../prefs/theme'

/*
 * The shell's command palette.
 *
 * The same component the demo uses, fed from the generated indexes: every content page, every demo,
 * and the display preferences. Nothing is hard-coded, so adding an `.mdx` file adds a command, and
 * the palette cannot drift from the sidebar.
 *
 * `Mod+K` opens it from anywhere. Recents persist under their own key — a palette that always starts
 * from the same alphabetical list wastes the best slot it has.
 */

const RECENT_KEY = 'frontend-lab:palette-recent'

export function CommandMenu() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { t, setLocale, pick } = useI18n()
  const { setMode } = useTheme()
  const { setPreset } = useStyle()

  useCommandShortcut(() => setOpen(true))

  const commands = useMemo<PaletteCommand[]>(() => {
    const sectionTitle = (group: string) => t.groups[group] ?? group

    const navigation: PaletteCommand[] = [
      {
        id: 'nav:home',
        title: t.nav.home,
        group: t.palette.groups.navigate,
        keywords: 'start index',
        run: () => navigate('/'),
      },
      {
        id: 'nav:demos',
        title: t.nav.allDemos,
        group: t.palette.groups.navigate,
        keywords: 'index prototypes',
        run: () => navigate('/demos'),
      },
      ...contentPages.map((page) => ({
        id: `page:${page.slug}`,
        title: pick(page.locales).value.title,
        group: sectionTitle(page.group),
        // A page and a demo can share a title ("Kanban board"); the badge is what tells them apart.
        hint: t.nav.pageBadge,
        keywords: page.slug.replaceAll('/', ' ').replaceAll('-', ' '),
        run: () => navigate(`/${page.slug}`),
      })),
      ...demos.map((demo) => ({
        id: `demo:${demo.slug}`,
        title: pick(demo.locales).value.title,
        group: sectionTitle(demo.group),
        hint: t.nav.demoBadge,
        keywords: `${demo.slug.replaceAll('/', ' ').replaceAll('-', ' ')} demo`,
        run: () => navigate(`/demos/${demo.slug}`),
      })),
    ]

    const appearance: PaletteCommand[] = [
      ...themeValues.map((mode) => ({
        id: `theme:${mode}`,
        title: format(t.palette.commands.theme, { mode: t.controls.modes[mode] }),
        group: t.palette.groups.appearance,
        keywords: `theme color mode ${mode}`,
        run: () => setMode(mode),
      })),
      ...styleValues.map((preset) => ({
        id: `style:${preset}`,
        title: format(t.palette.commands.style, { style: t.controls.styles[preset] }),
        group: t.palette.groups.appearance,
        keywords: `style preset ${preset}`,
        run: () => setPreset(preset),
      })),
    ]

    const language: PaletteCommand[] = locales.map((entry) => ({
      id: `locale:${entry}`,
      title: format(t.palette.commands.locale, { locale: localeLabels[entry] }),
      group: t.palette.groups.language,
      keywords: `language locale ${entry}`,
      run: () => setLocale(entry),
    }))

    return [...navigation, ...appearance, ...language]
  }, [navigate, pick, setLocale, setMode, setPreset, t])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-keyshortcuts="Meta+K Control+K"
        aria-haspopup="dialog"
        title={`${t.palette.trigger} · ⌘K`}
        className="flex h-8 items-center gap-1.5 rounded-full border border-border bg-card px-2.5 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span aria-hidden="true">⌘</span>
        <span>{t.palette.trigger}</span>
        <kbd className="hidden rounded border border-border px-1 font-mono text-[10px] sm:inline">
          K
        </kbd>
      </button>

      <CommandPalette
        open={open}
        onClose={() => setOpen(false)}
        commands={commands}
        label={t.palette.label}
        placeholder={t.palette.placeholder}
        emptyLabel={t.palette.empty}
        recentLabel={t.palette.recent}
        storageKey={RECENT_KEY}
        hint={t.palette.hint}
      />
    </>
  )
}
