import { contentGroups, contentPages } from '@/generated/content-index'
import { demoGroups, demos } from '@/generated/demo-registry'
import { Link } from 'react-router-dom'

import { useDocumentTitle } from '../use-document-title'

const ctaClass =
  'inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'

const secondaryCtaClass =
  'inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium text-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'

export function HomeRoute() {
  const firstPage = contentPages.at(0)
  const firstDemo = demos.at(0)

  useDocumentTitle('Frontend Lab')

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">Frontend Lab</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          An experiment lab for frontend techniques: every experiment runs, exposes its source and
          ships an MDX write-up. Built batch by batch — the roadmap lives in the prototype README.
        </p>
        <div className="flex flex-wrap gap-3">
          {firstDemo ? (
            <Link to={`/demos/${firstDemo.slug}`} className={ctaClass}>
              Open the first demo
            </Link>
          ) : null}
          {firstPage ? (
            <Link to={`/${firstPage.slug}`} className={secondaryCtaClass}>
              Start with {firstPage.title}
            </Link>
          ) : null}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold">
          Demos · {demos.length} runnable demo{demos.length === 1 ? '' : 's'}
        </h2>
        {demoGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold">{group.title}</h3>
            <ul className="mt-3 space-y-2">
              {group.demos.map((demo) => (
                <li key={demo.slug} className="text-sm">
                  <Link
                    to={`/demos/${demo.slug}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {demo.title}
                  </Link>
                  {demo.summary ? (
                    <span className="text-muted-foreground"> · {demo.summary}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold">
          Content · {contentPages.length} page{contentPages.length === 1 ? '' : 's'}
        </h2>
        {contentGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold">{group.title}</h3>
            <ul className="mt-3 space-y-2">
              {group.pages.map((page) => (
                <li key={page.slug} className="text-sm">
                  <Link
                    to={`/${page.slug}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {page.title}
                  </Link>
                  {page.summary ? (
                    <span className="text-muted-foreground"> · {page.summary}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Content comes from <code>content/**/*.mdx</code> and demos from{' '}
        <code>demos/&lt;group&gt;/&lt;name&gt;/</code> — both indexed at build time, no code change
        needed. B4 adds the quality gates (frontmatter schema, content checks, lint zones).
      </section>
    </div>
  )
}
