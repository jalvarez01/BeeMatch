import type { Dashboard } from '../types'
import { apiFetch } from './client'

export async function obtenerDashboard(): Promise<Dashboard> {
  return apiFetch<Dashboard>('/dashboard/')
}
