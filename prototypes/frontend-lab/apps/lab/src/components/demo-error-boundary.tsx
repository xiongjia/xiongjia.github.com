import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  /** Slug of the demo being rendered, used in the log and the message. */
  demo: string
  /** Localised strings: a class component cannot call `useI18n()`, so they arrive as props. */
  labels: { title: string; hint: string; recover: string }
  children: ReactNode
}

type State = {
  error: Error | null
}

/**
 * Isolates a crashing demo: the boundary renders an error card in place of the preview, and the rest
 * of the page (tabs, source, notes, sidebar) keeps working. Instance state means "Recover" retries
 * without a page reload.
 */
export class DemoErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[demo:${this.props.demo}] crashed`, error, info.componentStack)
  }

  private recover = () => {
    this.setState({ error: null })
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div
        className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-4"
        role="alert"
      >
        <p className="text-sm font-semibold">{this.props.labels.title}</p>
        <p className="text-xs text-muted-foreground">{this.props.labels.hint}</p>
        <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
          {error.name}: {error.message}
        </pre>
        <button
          type="button"
          onClick={this.recover}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          {this.props.labels.recover}
        </button>
      </div>
    )
  }
}
