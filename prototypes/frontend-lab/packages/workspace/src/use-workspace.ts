import { useContext } from 'react'
import { useStore } from 'zustand'
import type { StoreApi } from 'zustand/vanilla'

import { WorkspaceContext } from './context.ts'
import type { WorkspaceState } from './store.ts'

/** The raw store: `getState`, `setState`, `subscribe` — usable outside React too. */
export function useWorkspaceApi(): StoreApi<WorkspaceState> {
  const store = useContext(WorkspaceContext)
  if (!store) {
    throw new Error('[workspace] no provider found — wrap the tree in <WorkspaceProvider>')
  }
  return store
}

/** Subscribe to a slice of the workspace. */
export function useWorkspace<T>(selector: (state: WorkspaceState) => T): T {
  return useStore(useWorkspaceApi(), selector)
}
