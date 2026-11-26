import { api, type ApiClient } from './client'

export interface Liveness {
  status: string
  name: string
  version: string
}

export function getHealth(client: ApiClient = api): Promise<Liveness> {
  return client.get<Liveness>('/api/v1/health')
}
