import { api, type ApiClient } from './client'
import type { components } from './generated/schema'

export type Liveness = components['schemas']['LivenessResponse']

export function getHealth(client: ApiClient = api): Promise<Liveness> {
  return client.get<Liveness>('/api/v1/health')
}
