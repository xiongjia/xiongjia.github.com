export { createStoreContext } from './create-store-context'
export type { StoreContext } from './create-store-context'
// Selectors that return a new object/array need shallow comparison; zustand v5 no longer does it
// for you. Re-exported so a demo imports one package instead of two.
export { useShallow } from 'zustand/react/shallow'
