import {
  CommandPalette,
  useCommandShortcut,
  type PaletteCommand,
} from '@frontend-lab/command-palette'
import { useMemo, useState } from 'react'

/*
 * Command palette: the B16 composed scenario.
 *
 * The palette problem is 20% filtering and 80% keyboard and focus behaviour. The demo therefore
 * exposes the parts a screenshot cannot show:
 *
 *   - the trigger is a real button, and closing the palette puts focus back on it
 *   - ArrowUp / ArrowDown move `aria-activedescendant`, focus never leaves the input
 *   - Tab is trapped inside the dialog, Escape closes it
 *   - running a command closes the palette, records it, and reopening shows it under "Recent"
 *
 * `Mod+J` is the demo's own shortcut. The lab shell owns `Mod+K` globally, and two handlers on the
 * same window would race — so a demo that needs a shortcut picks an unused one.
 */

type Run = { title: string; at: string }

const groups = {
  actions: 'Actions',
  navigation: 'Navigation',
  messages: 'Messages',
  appearance: 'Appearance',
}

export default function Demo() {
  const [open, setOpen] = useState(false)
  const [opens, setOpens] = useState(0)
  const [lastRun, setLastRun] = useState<Run | null>(null)
  const [sidebar, setSidebar] = useState(true)

  useCommandShortcut(() => setOpen(true), { key: 'j' })

  const commands = useMemo<PaletteCommand[]>(() => {
    const run = (title: string) => () => setLastRun({ title, at: new Date().toLocaleTimeString() })

    return [
      {
        id: 'note',
        title: 'Create a note',
        group: groups.actions,
        hint: '⌘N',
        keywords: 'new write scratch',
        run: run('Create a note'),
      },
      {
        id: 'invite',
        title: 'Invite a teammate',
        group: groups.actions,
        keywords: 'share people team',
        run: run('Invite a teammate'),
      },
      {
        id: 'copy',
        title: 'Copy link',
        group: groups.actions,
        keywords: 'share clipboard url',
        run: run('Copy link'),
      },
      {
        id: 'inbox',
        title: 'Go to inbox',
        group: groups.navigation,
        hint: 'G I',
        keywords: 'mail messages',
        run: run('Go to inbox'),
      },
      {
        id: 'settings',
        title: 'Open settings',
        group: groups.navigation,
        hint: '⌘,',
        keywords: 'preferences configuration theme',
        run: run('Open settings'),
      },
      {
        id: 'send',
        title: 'Send a test message',
        group: groups.messages,
        keywords: 'mail email',
        run: run('Send a test message'),
      },
      {
        id: 'mute',
        title: 'Mute notifications',
        group: groups.messages,
        keywords: 'silence alerts dnd',
        run: run('Mute notifications'),
      },
      {
        id: 'sidebar',
        title: sidebar ? 'Hide the sidebar' : 'Show the sidebar',
        group: groups.appearance,
        keywords: 'layout panel',
        run: () => {
          setSidebar((visible) => !visible)
          setLastRun({ title: 'Toggle the sidebar', at: new Date().toLocaleTimeString() })
        },
      },
      {
        id: 'compact',
        title: 'Switch to the compact theme',
        group: groups.appearance,
        keywords: 'theme style density',
        run: run('Switch to the compact theme'),
      },
    ]
  }, [sidebar])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          id="palette-trigger"
          onClick={() => {
            setOpen(true)
            setOpens((count) => count + 1)
          }}
          aria-haspopup="dialog"
          aria-keyshortcuts="Meta+J Control+J"
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Open the palette <kbd className="ml-1 font-mono text-[10px]">⌘J</kbd>
        </button>
        <button
          type="button"
          onClick={() => {
            window.localStorage.removeItem('frontend-lab:demo-palette-recent')
            setLastRun(null)
          }}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Reset demo state
        </button>
        <p className="font-mono text-[10px] text-muted-foreground" data-testid="palette-opens">
          opened {opens} · last: {lastRun ? `${lastRun.title} @ ${lastRun.at}` : '—'}
        </p>
      </div>

      <div className="grid gap-2 text-[11px] sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Try this</p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-muted-foreground">
            <li>Open the palette, then press Tab — focus stays in the dialog.</li>
            <li>
              Type <code className="rounded bg-muted px-1">set</code>: the title match is marked and
              ranked.
            </li>
            <li>
              Arrow down twice, press Enter: the command runs and focus returns to the trigger.
            </li>
            <li>Open it again with an empty query — the command you ran is under “Recent”.</li>
          </ol>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Focus contract</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
            <li>
              The listbox is never focused; the input keeps focus and points at the active option.
            </li>
            <li>
              Tab is swallowed: a modal palette that lets Tab escape is a page-level trap bug.
            </li>
            <li>Closing restores focus to whatever opened it — the trigger button here.</li>
          </ul>
        </div>
      </div>

      {sidebar ? (
        <p className="rounded border border-dashed border-border px-2 py-1 text-[10px] text-muted-foreground">
          sidebar visible — run “Hide the sidebar” to see a command change the page.
        </p>
      ) : null}

      <CommandPalette
        open={open}
        onClose={() => setOpen(false)}
        commands={commands}
        label="Demo command palette"
        placeholder="Search the demo commands…"
        emptyLabel="No command matches that"
        recentLabel="Recent"
        storageKey="frontend-lab:demo-palette-recent"
        hint="↑↓ move · Enter run · Esc close"
      />
    </div>
  )
}
