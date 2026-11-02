import { contentGroups } from '@/generated/content-index'
import { demoGroups } from '@/generated/demo-registry'

export type NavLink = {
  label: string
  to: string
  /** Demos get a badge in the sidebar; explainer pages do not. */
  kind: 'page' | 'demo'
}

export type NavSection = {
  id: string
  title: string
  items: NavLink[]
}

/**
 * Sidebar sections.
 *
 * Content groups and demo groups share one topic tree (§ "MDX explains, components interact"): a
 * folder named `foundations` in `content/` and one in `demos/` land in the same section. Everything
 * here is generated — new MDX pages and new demo folders appear with no code change.
 */
const groupIds = [...new Set([...contentGroups, ...demoGroups].map((group) => group.id))]
  .filter((id) => id !== 'demos')
  .sort((a, b) => a.localeCompare(b))

export const navSections: NavSection[] = groupIds.map((id) => {
  const contentGroup = contentGroups.find((group) => group.id === id)
  const demoGroup = demoGroups.find((group) => group.id === id)

  return {
    id,
    title: contentGroup?.title ?? demoGroup?.title ?? id,
    items: [
      ...(contentGroup?.pages ?? []).map((page) => ({
        label: page.title,
        to: `/${page.slug}`,
        kind: 'page' as const,
      })),
      ...(demoGroup?.demos ?? []).map((demo) => ({
        label: demo.title,
        to: `/demos/${demo.slug}`,
        kind: 'demo' as const,
      })),
    ],
  }
})

/** Static tail: an index of everything interactive. */
export const extraSection: NavSection = {
  id: 'index',
  title: 'Index',
  items: [{ label: 'All demos', to: '/demos', kind: 'demo' }],
}
