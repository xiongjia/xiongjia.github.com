import { useAnimate, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'

/*
 * The two boxes below run the same visual idea through two engines:
 *
 *   CSS   @keyframes + animation shorthand, restarted by remounting the element (`key`).
 *   Motion an imperative WAAPI animation started from JavaScript, with `null` as the first
 *          keyframe, which means "start where it is right now".
 *
 * Click "kick" twice in quick succession: the CSS box jumps back to the start of its timeline, the
 * Motion box continues from its current position. That difference is the whole experiment.
 */

type Inspection = { engine: string; type: string; duration: string; state: string }

export default function Demo() {
  const [cssKey, setCssKey] = useState(0)
  const [motionHits, setMotionHits] = useState(0)
  const [inspection, setInspection] = useState<Inspection[]>([])
  const [scope, animate] = useAnimate()
  const reduced = useReducedMotion()

  useEffect(() => {
    // Print what the browser really created: a CSSAnimation for the keyframes, a plain Animation
    // (WAAPI) for Motion. Both end up on the compositor for `transform`.
    const timer = setTimeout(() => {
      setInspection(
        [...document.querySelectorAll<HTMLElement>('[data-anim-engine]')].map((element) => {
          const animation = element.getAnimations().at(0)
          return {
            engine: element.dataset['animEngine'] ?? '?',
            type: animation ? animation.constructor.name : 'none',
            duration: animation
              ? `${Math.round(Number(animation.effect?.getTiming().duration ?? 0))}ms`
              : '—',
            state: animation?.playState ?? 'idle',
          }
        }),
      )
    }, 120)
    return () => clearTimeout(timer)
  }, [cssKey, motionHits])

  const kickBoth = () => {
    setCssKey((value) => value + 1)
    setMotionHits((value) => value + 1)
    if (reduced) return
    void animate(scope.current, { y: [null, -32, 0] }, { duration: 0.9, ease: 'easeInOut' })
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={kickBoth}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Kick both
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          css remounts: {cssKey} · motion calls: {motionHits}
          {reduced ? ' · reduced motion: animation skipped' : ''}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="space-y-3 rounded-lg border border-border p-4">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            CSS keyframes
          </h3>
          <div className="grid h-28 place-items-center">
            <div
              key={cssKey}
              data-anim-engine="css"
              data-anim-target=""
              className="grid size-12 place-items-center rounded-md bg-secondary font-mono text-[10px] text-secondary-foreground animate-kick motion-reduce:animate-none"
            >
              css
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            <code className="rounded bg-muted px-1">animation: kick 900ms …</code> from
            <code className="ml-1 rounded bg-muted px-1">@keyframes</code>. Restarting means
            removing and re-adding the animation — here by remounting with <code>key</code> — so the
            timeline always begins at 0.
          </p>
        </section>

        <section className="space-y-3 rounded-lg border border-border p-4">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Motion (WAAPI)
          </h3>
          <div ref={scope} className="grid h-28 place-items-center">
            <div
              data-anim-engine="motion"
              data-anim-target=""
              className="grid size-12 place-items-center rounded-md bg-primary font-mono text-[10px] text-primary-foreground"
            >
              motion
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            <code className="rounded bg-muted px-1">
              {'animate(el, { y: [null, -32, 0] }, { duration: 0.9 })'}
            </code>
            . A <code className="rounded bg-muted px-1">null</code> first keyframe reads the current
            value, so an interrupt continues instead of restarting.
          </p>
        </section>
      </div>

      <section className="space-y-1">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          What the browser created
        </h3>
        <ul className="font-mono text-[11px] text-muted-foreground">
          {inspection.map((row) => (
            <li key={row.engine}>
              {row.engine}: {row.type} · {row.duration} · {row.state}
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          Two engines, one mechanism: `CSSAnimation` and Motion's `Animation` are both Web
          Animations objects, and `transform` animations of either kind run off the main thread.
          Motion's advantage is scheduling — springs, interruption, layout projection — not a secret
          API.
        </p>
      </section>
    </div>
  )
}
