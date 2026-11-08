import { cn } from '@frontend-lab/ui'
import { useMemo } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { LanguageSwitch } from '../components/language-switch'
import { StylePicker } from '../components/style-picker'
import { ThemeToggle } from '../components/theme-toggle'
import { useI18n } from '../i18n/use-i18n'
import { buildExtraSection, buildNavSections, type NavLink as NavItem } from './nav'

const itemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'block rounded-md px-2.5 py-2 text-sm transition-colors outline-none',
    'focus-visible:ring-2 focus-visible:ring-ring',
    isActive
      ? 'bg-secondary font-medium text-secondary-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
  )

/**
 * One sidebar row. A translated page and a translated demo look the same; only a missing
 * translation gets an `EN` tag, so the reader knows why the label switched language.
 */
function SidebarItem({ item, missingTitle }: { item: NavItem; missingTitle: string }) {
  return (
    <NavLink to={item.to} className={itemClass}>
      <span className="flex items-center justify-between gap-2">
        <span className="truncate">{item.label}</span>
        <span className="flex shrink-0 items-center gap-1">
          {item.missing ? (
            <span
              title={missingTitle}
              className="rounded border border-dashed border-border px-1 py-0.5 text-[10px] tracking-wide text-muted-foreground uppercase"
            >
              EN
            </span>
          ) : null}
          {item.kind === 'demo' ? (
            <span className="rounded bg-muted px-1 py-0.5 text-[10px] tracking-wide text-muted-foreground uppercase">
              demo
            </span>
          ) : null}
        </span>
      </span>
    </NavLink>
  )
}

export function Layout() {
  const { locale, t } = useI18n()

  const sections = useMemo(
    () => [...buildNavSections(locale, t.groups), buildExtraSection(t.nav.index, t.nav.allDemos)],
    [locale, t],
  )

  return (
    <div className="flex h-full min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <span className="size-2.5 rounded-full bg-primary" aria-hidden="true" />
          <span className="text-sm font-semibold tracking-tight">{t.app.name}</span>
        </div>
        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto p-3" aria-label={t.app.navLabel}>
          <NavLink to="/" end className={itemClass}>
            {t.nav.home}
          </NavLink>
          {sections.map((section) => (
            <div key={section.id} className="space-y-1">
              <p className="px-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {section.title}
              </p>
              {section.items.map((item) => (
                <SidebarItem key={item.to} item={item} missingTitle={t.nav.missingTitle} />
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          {t.app.batch}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-3 border-b border-border px-4 md:px-6">
          <p className="hidden truncate text-sm text-muted-foreground sm:block">{t.app.tagline}</p>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <LanguageSwitch />
            <StylePicker />
            <ThemeToggle />
            <span className="hidden rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground 2xl:inline">
              {t.app.progress}
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 md:px-6 md:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
