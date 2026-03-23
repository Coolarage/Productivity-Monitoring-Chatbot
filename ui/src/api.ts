import type { EmployeeKpiInput, EvaluationResult } from './types'

const API_BASE =
  import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export async function postEvaluate(
  payload: EmployeeKpiInput,
): Promise<EvaluationResult> {
  const response = await fetch(`${API_BASE}/evaluate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(
      `Backend error (${response.status}): ${text || response.statusText}`,
    )
  }

  const data = (await response.json()) as EvaluationResult
  return data
}

