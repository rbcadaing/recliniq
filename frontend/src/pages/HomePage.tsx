import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../api/health'

export function HomePage() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => getHealth() })

  return (
    <section>
      <h1>Welcome to RecliniQ</h1>
      <p>Doctor schedules, consultation booking, live queues, and medical records.</p>

      <output className="status" aria-live="polite">
        <span className="status__label">Backend:</span> {health.isPending && <span>checking…</span>}
        {health.isSuccess && (
          <span className="status__value status__value--online">
            online · v{health.data.version}
          </span>
        )}
        {health.isError && <span className="status__value status__value--offline">offline</span>}
      </output>
    </section>
  )
}
