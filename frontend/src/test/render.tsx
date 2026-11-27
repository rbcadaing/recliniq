import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { StrictMode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { routes } from '../routes'

/**
 * Render the real route tree at a given URL (optionally with router state) with an isolated,
 * non-retrying query client, inside StrictMode like the real app.
 */
export function renderAt(path: string, state?: unknown) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(routes, {
    initialEntries: [{ ...toEntry(path), state }],
  })
  const view = render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
  return { ...view, router }
}

function toEntry(path: string) {
  const url = new URL(path, 'http://localhost')
  return { pathname: url.pathname, search: url.search }
}
