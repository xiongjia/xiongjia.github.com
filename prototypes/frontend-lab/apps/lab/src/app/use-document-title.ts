import { useEffect } from 'react'

/** Keep `document.title` in sync with the current route. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title
  }, [title])
}
