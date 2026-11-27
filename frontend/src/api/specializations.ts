import { api, type ApiClient } from './client'

export interface Specialization {
  id: string
  code: string
  name: string
}

export function getSpecializations(client: ApiClient = api): Promise<Specialization[]> {
  return client.get<Specialization[]>('/api/v1/specializations')
}
