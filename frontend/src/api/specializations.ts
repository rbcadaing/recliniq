import { api, type ApiClient } from './client'
import type { components } from './generated/schema'

export type Specialization = components['schemas']['SpecializationResponse']

export function getSpecializations(client: ApiClient = api): Promise<Specialization[]> {
  return client.get<Specialization[]>('/api/v1/specializations')
}
