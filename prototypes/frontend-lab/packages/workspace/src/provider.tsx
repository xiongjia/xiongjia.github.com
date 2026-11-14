import { useState, type ReactNode } from 'react'

import { WorkspaceContext } from './context.ts'
import { createWorkspaceStore } from './store.ts'

/*
 * One workspace per provider, built from props.
 *
 * This is the same shape as B11's `createStoreContext`, with one difference that matters for a
 * composed scenario: the initial files are data, not a module constant, so the state creator has to
 * run per mount. The lazy `useState` initialiser is still what guarantees exactly one store per
 * provider — a `useRef(createWorkspaceStore(...))` call would rebuild it on every render.
 */

export type WorkspaceProviderProps = {
  files: Parameters<typeof createWorkspaceStore>[0]
  /** Tab to open on mount; omit to start on an empty strip. */
  initialPath?: string
  children: ReactNode
}

export function WorkspaceProvider({ files, initialPath, children }: WorkspaceProviderProps) {
  const [store] = useState(() => createWorkspaceStore(files, initialPath))
  return <WorkspaceContext.Provider value={store}>{children}</WorkspaceContext.Provider>
}
