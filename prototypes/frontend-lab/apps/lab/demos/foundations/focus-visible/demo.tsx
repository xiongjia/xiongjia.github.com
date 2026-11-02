import { cn } from '@frontend-lab/ui'
import { useEffect, useState } from 'react'

type Modality = 'keyboard' | 'pointer' | 'none'

/** Track the last input modality, so the demo can say what the browser is reacting to. */
function useLastModality(): Modality {
  const [modality, setModality] = useState<Modality>('none')

  useEffect(() => {
    const onKeyDown = () => setModality('keyboard')
    const onPointerDown = () => setModality('pointer')

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('pointerdown', onPointerDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('pointerdown', onPointerDown)
    }
  }, [])

  return modality
}

const base = 'rounded-md border border-border px-3 py-2 text-sm'

const cases = [
  {
    label: 'outline-none',
    className: cn(base, 'outline-none'),
    note: 'The default ring is removed and nothing replaces it — a keyboard user loses the cursor.',
  },
  {
    label: 'focus:ring',
    className: cn(base, 'outline-none focus:ring-2 focus:ring-ring'),
    note: 'Rings on every interaction, including plain mouse clicks.',
  },
  {
    label: 'focus-visible:ring',
    className: cn(
      base,
      'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    ),
    note: 'Rings only when the browser reports keyboard intent — the default across this lab.',
  },
] as const

export default function Demo() {
  const modality = useLastModality()
  const [focused, setFocused] = useState<string[]>([])

  const recordFocus = (label: string) => {
    setFocused((previous) => [label, ...previous.filter((entry) => entry !== label)].slice(0, 3))
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          last input
        </span>
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-xs font-medium',
            modality === 'keyboard'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground',
          )}
        >
          {modality}
        </span>
        <span className="text-xs text-muted-foreground">
          press <kbd className="rounded border border-border px-1 font-mono">Tab</kbd>, then click
        </span>
      </div>

      <ul className="space-y-3">
        {cases.map((item) => (
          <li key={item.label} className="space-y-1">
            <button
              type="button"
              className={item.className}
              onFocus={() => recordFocus(item.label)}
            >
              {item.label}
            </button>
            <p className="text-xs text-muted-foreground">{item.note}</p>
          </li>
        ))}
      </ul>

      <p className="text-xs text-muted-foreground">
        Focus log: <span className="font-mono">{focused.join(' · ') || 'nothing focused yet'}</span>
      </p>
    </div>
  )
}
