import { useEffect, useRef } from 'react'

/*
 * Mod+K (or another modifier key), registered once for the whole app.
 *
 * `event.key` on a keyboard layout that does not have a `k` is not always `k`, which is why the
 * check lowercases it and also accepts `K`. The handler lives in a ref so the listener is registered
 * once, not on every render of the component that owns the palette.
 */
export function useCommandShortcut(
  onTrigger: () => void,
  options: { enabled?: boolean; key?: string } = {},
): void {
  const { enabled = true, key = 'k' } = options
  const handler = useRef(onTrigger)
  handler.current = onTrigger

  useEffect(() => {
    if (!enabled) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return
      if (event.key.toLowerCase() !== key.toLowerCase()) return
      event.preventDefault()
      handler.current()
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [enabled, key])
}
