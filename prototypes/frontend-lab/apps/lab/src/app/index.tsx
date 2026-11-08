import { I18nProvider } from '@/i18n/provider'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import { Layout } from './layout'
import { ContentRoute } from './routes/content-route'
import { DemoRoute } from './routes/demo-route'
import { DemosIndexRoute } from './routes/demos-index-route'
import { HomeRoute } from './routes/home-route'

/**
 * Content pages and demos are both resolved from generated registries, so adding files never means
 * touching this file. Static routes win over the splat during ranking, which keeps `/demos/*` out of
 * the content resolver.
 */
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomeRoute /> },
      { path: 'demos', element: <DemosIndexRoute /> },
      { path: 'demos/:group/:name', element: <DemoRoute /> },
      { path: '*', element: <ContentRoute /> },
    ],
  },
])

/** The provider wraps the router, so every route (and the shell) can read the locale. */
export function App() {
  return (
    <I18nProvider>
      <RouterProvider router={router} />
    </I18nProvider>
  )
}
