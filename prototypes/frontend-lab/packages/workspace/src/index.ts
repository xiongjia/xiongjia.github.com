/*
 * A workspace contract, not an editor: files + open documents + the dirty rule.
 *
 * The module split is deliberate — `model.ts` is pure, `store.ts` is the same model behind
 * zustand, `context.tsx` is the React binding. Anything that needs the buffer rule (an integration
 * test, a second editor, a command palette) talks to the model or the store, never to a component.
 */

export * from './model.ts'
export {
  createWorkspaceState,
  createWorkspaceStore,
  selectActions,
  selectActivePath,
  selectOpenPaths,
  selectSnapshot,
} from './store.ts'
export type { WorkspaceActions, WorkspaceState } from './store.ts'
export { WorkspaceProvider } from './provider.tsx'
export type { WorkspaceProviderProps } from './provider.tsx'
export { useWorkspace, useWorkspaceApi } from './use-workspace.ts'
