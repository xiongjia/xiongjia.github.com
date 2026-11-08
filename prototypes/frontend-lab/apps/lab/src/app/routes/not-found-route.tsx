import { Link } from 'react-router-dom'

import { useI18n } from '../../i18n/use-i18n'

export function NotFoundRoute() {
  const { t } = useI18n()

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">{t.notFound.title}</h1>
      <p className="text-sm text-muted-foreground">{t.notFound.body}</p>
      <Link to="/" className="text-sm font-medium text-primary underline underline-offset-4">
        {t.notFound.back}
      </Link>
    </div>
  )
}
