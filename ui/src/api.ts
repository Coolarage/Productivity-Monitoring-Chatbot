import type {
  CsvBatchEvaluationResponse,
  EmployeeKpiInput,
  EvaluationResult,
} from './types'

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

export async function postEvaluateCsv(
  file: File,
): Promise<CsvBatchEvaluationResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/evaluate/csv`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(
      `Backend error (${response.status}): ${text || response.statusText}`,
    )
  }

  return (await response.json()) as CsvBatchEvaluationResponse
}

export function getCsvDownloadUrl(relativeUrl: string): string {
  if (relativeUrl.startsWith('http://') || relativeUrl.startsWith('https://')) {
    return relativeUrl
  }
  return `${API_BASE}${relativeUrl}`
}

