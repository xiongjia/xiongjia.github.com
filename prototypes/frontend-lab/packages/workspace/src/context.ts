import { createContext } from 'react'
import type { StoreApi } from 'zustand/vanilla'

import type { WorkspaceState } from './store.ts'

/*
 * The context object lives on its own so the provider and the hooks can each live in their own
 * module — React Fast Refresh only reloads a file that exports components and nothing else.
 */

export const WorkspaceContext = createContext<StoreApi<WorkspaceState> | null>(null)
