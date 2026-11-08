import { contentGroups } from '@/generated/content-index'
import { demoGroups } from '@/generated/demo-registry'
import type { Locale } from '@/i18n/locales'

export type NavKind = 'page' | 'demo'

export type NavLink = {
  label: string
  to: string
  /** Demos get a badge in the sidebar; explainer pages do not. */
  kind: NavKind
  /** True when the current locale has no title of its own and English is shown instead. */
  missing: boolean
}

export type NavSection = {
  id: string
  title: string
  items: NavLink[]
}

/** The slice of a generated locale entry the sidebar needs. */
type LocalizedMeta = { title: string }

function labelFor(localized: { en: LocalizedMeta; zh?: LocalizedMeta }, locale: Locale) {
  const translated = locale === 'en' ? undefined : localized[locale]
  return {
    label: (translated ?? localized.en).title,
    missing: locale !== 'en' && translated === undefined,
  }
}

/**
 * Sidebar sections, in the reader's language.
 *
 * Content groups and demo groups share one topic tree (§ "MDX explains, components interact"): a
 * folder named `foundations` in `content/` and one in `demos/` land in the same section. Group
 * titles come from the dictionary (falling back to the generated English label); item titles come
 * from each locale's own frontmatter, so a missing translation is visible rather than silent.
 */
export function buildNavSections(
  locale: Locale,
  groupTitles: Record<string, string>,
): NavSection[] {
  const groupIds = [...new Set([...contentGroups, ...demoGroups].map((group) => group.id))]
    .filter((id) => id !== 'demos')
    .sort((a, b) => a.localeCompare(b))

  return groupIds.map((id) => {
    const contentGroup = contentGroups.find((group) => group.id === id)
    const demoGroup = demoGroups.find((group) => group.id === id)

    return {
      id,
      title: groupTitles[id] ?? contentGroup?.title ?? demoGroup?.title ?? id,
      items: [
        ...(contentGroup?.pages ?? []).map((page) => ({
          ...labelFor(page.locales, locale),
          to: `/${page.slug}`,
          kind: 'page' as const,
        })),
        ...(demoGroup?.demos ?? []).map((demo) => ({
          ...labelFor(demo.locales, locale),
          to: `/demos/${demo.slug}`,
          kind: 'demo' as const,
        })),
      ],
    }
  })
}

/** Static tail: an index of everything interactive. */
export function buildExtraSection(indexTitle: string, allDemos: string): NavSection {
  return {
    id: 'index',
    title: indexTitle,
    items: [{ label: allDemos, to: '/demos', kind: 'demo', missing: false }],
  }
}
