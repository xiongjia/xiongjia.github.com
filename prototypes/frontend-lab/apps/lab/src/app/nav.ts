export type NavItem = {
  label: string
  to: string
  status: 'ready' | 'planned'
}

/**
 * Placeholder navigation for B1. From B2 on this list is generated from the
 * content index (see `apps/lab/src/generated/`).
 */
export const navItems: NavItem[] = [
  { label: 'Home', to: '/', status: 'ready' },
  { label: 'Hello demo', to: '/demos/hello', status: 'ready' },
  { label: 'Foundations', to: '/foundations', status: 'planned' },
  { label: 'Interactions', to: '/interactions', status: 'planned' },
  { label: 'Recipes', to: '/recipes', status: 'planned' },
]
