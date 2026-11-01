import { createBrowserRouter, Link, RouterProvider } from 'react-router-dom'

import { Layout } from './Layout'
import { HelloDemoRoute } from './routes/HelloDemoRoute'
import { HomeRoute } from './routes/HomeRoute'

function NotFoundRoute() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        This route is not part of the lab yet. Batches land incrementally — check the roadmap in the
        prototype README.
      </p>
      <Link to="/" className="text-sm font-medium text-primary underline underline-offset-4">
        Back to home
      </Link>
    </div>
  )
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomeRoute /> },
      { path: 'demos/hello', element: <HelloDemoRoute /> },
      { path: '*', element: <NotFoundRoute /> },
    ],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
