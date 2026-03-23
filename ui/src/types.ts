export type RecommendationItem = {
  area: string
  description: string
}

export type EvaluationSummary = {
  label: 'no_decline' | 'decline_risk'
  label_human_readable: string
  confidence?: number | null
  explanation: string
  weak_areas: string[]
  recommendations: RecommendationItem[]
}

export type EvaluationResult = {
  evaluation_id: string
  employee_id: string
  manager_id: string
  summary: EvaluationSummary
}

export type EmployeeKpiInput = {
  employee_id: string
  employee_email: string
  manager_id: string
  manager_email: string
  date?: string
  department?: string
  team?: number
  targeted_productivity?: number
  actual_productivity?: number
  smv?: number
  wip?: number
  over_time?: number
  incentive?: number
  idle_time?: number
  idle_men?: number
  no_of_style_change?: number
  no_of_workers?: number
  extra_fields?: Record<string, unknown>
}

