import { cn } from '@frontend-lab/ui'
import { NavLink, Outlet } from 'react-router-dom'

import { navItems } from './nav'

export function Layout() {
  return (
    <div className="flex h-full min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <span className="size-2.5 rounded-full bg-primary" aria-hidden="true" />
          <span className="text-sm font-semibold tracking-tight">Frontend Lab</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3" aria-label="Lab">
          <p className="px-2 pt-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Learn
          </p>
          {navItems.map((item) =>
            item.status === 'ready' ? (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-2.5 py-2 text-sm transition-colors outline-none',
                    'focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'bg-secondary font-medium text-secondary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ) : (
              <span
                key={item.to}
                className="flex items-center justify-between rounded-md px-2.5 py-2 text-sm text-muted-foreground/60"
                aria-disabled="true"
              >
                {item.label}
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] tracking-wide uppercase">
                  soon
                </span>
              </span>
            ),
          )}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          Batch B1 · shell
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-4 border-b border-border px-4 md:px-6">
          <p className="truncate text-sm text-muted-foreground">
            MDX explains · React components interact · experiments prove
          </p>
          <span className="shrink-0 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
            B1 / B17
          </span>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 md:px-6 md:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
