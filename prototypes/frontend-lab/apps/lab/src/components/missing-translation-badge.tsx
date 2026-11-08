/**
 * Marks content that has no translation for the current locale: the reader is seeing English, and
 * the UI says so instead of pretending the page is translated.
 *
 * The compact form is the `EN` tag used inside lists and the sidebar, where a full sentence would
 * not fit; both carry the explanation as a tooltip.
 */
export function MissingTranslationBadge({
  message,
  compact = false,
}: {
  message: string
  compact?: boolean
}) {
  if (compact) {
    return (
      <span
        title={message}
        className="rounded border border-dashed border-border px-1 py-0.5 text-[10px] tracking-wide text-muted-foreground uppercase"
      >
        EN
      </span>
    )
  }

  return (
    <span
      className="inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-[11px] text-muted-foreground"
      title={message}
    >
      {message}
    </span>
  )
}
