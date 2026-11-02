import { Link } from 'react-router-dom'

export function NotFoundRoute() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        There is no page at this path. Content pages are generated from <code>content/</code>, so a
        missing page usually means a typo in the URL or a deleted <code>.mdx</code> file.
      </p>
      <Link to="/" className="text-sm font-medium text-primary underline underline-offset-4">
        Back to home
      </Link>
    </div>
  )
}
