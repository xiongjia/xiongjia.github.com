import { createStore, type StateCreator, type StoreApi } from 'zustand/vanilla'

import {
  closeDocument,
  createSnapshot,
  openDocument,
  revertDocument,
  saveDocument,
  updateDraft,
  type WorkspaceFile,
  type WorkspaceSnapshot,
} from './model.ts'

/*
 * The workspace store: snapshot plus actions, no React.
 *
 * Kept separate from `context.tsx` so the integration test can drive the real store in Node — the
 * React layer is a thin provider around exactly this object. Actions are a stable nested object
 * (B11's lesson): recreating them inside `set()` would re-render every dispatcher-only component.
 */

export type WorkspaceActions = {
  open: (path: string) => void
  close: (path: string) => void
  /** Report a new draft for an open document (a keystroke, a paste, an external sync). */
  edit: (path: string, draft: string) => void
  /** Commit a draft; defaults to the active document. */
  save: (path?: string) => void
  /** Discard a draft; defaults to the active document. */
  revert: (path?: string) => void
}

export type WorkspaceState = {
  snapshot: WorkspaceSnapshot
  actions: WorkspaceActions
}

/** Selectors that keep components from reading the whole snapshot. */
export const selectSnapshot = (state: WorkspaceState) => state.snapshot
export const selectActions = (state: WorkspaceState) => state.actions
export const selectActivePath = (state: WorkspaceState) => state.snapshot.active
export const selectOpenPaths = (state: WorkspaceState) => state.snapshot.open.map((doc) => doc.path)

/** State creator, so the React provider and the test build the same store. */
export function createWorkspaceState(
  files: readonly WorkspaceFile[],
  initialPath?: string,
): StateCreator<WorkspaceState, [], []> {
  const initial = createSnapshot(files)

  return (set) => ({
    snapshot: initialPath ? openDocument(initial, initialPath) : initial,
    actions: {
      open: (path) => set((state) => ({ snapshot: openDocument(state.snapshot, path) })),
      close: (path) => set((state) => ({ snapshot: closeDocument(state.snapshot, path) })),
      edit: (path, draft) =>
        set((state) => ({ snapshot: updateDraft(state.snapshot, path, draft) })),
      save: (path) => set((state) => ({ snapshot: saveDocument(state.snapshot, path) })),
      revert: (path) => set((state) => ({ snapshot: revertDocument(state.snapshot, path) })),
    },
  })
}

/** A vanilla store — the test target, and what the provider holds in state. */
export function createWorkspaceStore(
  files: readonly WorkspaceFile[],
  initialPath?: string,
): StoreApi<WorkspaceState> {
  return createStore<WorkspaceState>()(createWorkspaceState(files, initialPath))
}
