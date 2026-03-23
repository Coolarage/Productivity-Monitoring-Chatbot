import { useState } from 'react'
import type { EmployeeKpiInput } from '../types'
import './KpiForm.css'

type KpiFormProps = {
  onSubmitEvaluate: (args: {
    payload: EmployeeKpiInput
    summaryText: string
  }) => void
  loading: boolean
}

const defaultEmployee: Pick<
  EmployeeKpiInput,
  'employee_id' | 'employee_email' | 'manager_id' | 'manager_email'
> = {
  employee_id: 'EMP123',
  employee_email: 'employee@example.com',
  manager_id: 'MGR456',
  manager_email: 'manager@example.com',
}

export function KpiForm({ onSubmitEvaluate, loading }: KpiFormProps) {
  const [form, setForm] = useState<EmployeeKpiInput>({
    ...defaultEmployee,
    date: '',
    department: 'sewing',
    team: 8,
    targeted_productivity: 0.8,
    actual_productivity: 0.65,
    smv: 26.16,
    wip: 1100,
    over_time: 4200,
    incentive: 50,
    idle_time: 30,
    idle_men: 2,
    no_of_style_change: 1,
    no_of_workers: 57,
    extra_fields: {},
  })

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target
    setForm((prev) => {
      if (
        [
          'team',
          'targeted_productivity',
          'actual_productivity',
          'smv',
          'wip',
          'over_time',
          'incentive',
          'idle_time',
          'idle_men',
          'no_of_style_change',
          'no_of_workers',
        ].includes(name)
      ) {
        const num = value === '' ? undefined : Number(value)
        return { ...prev, [name]: Number.isNaN(num) ? undefined : num }
      }
      return { ...prev, [name]: value }
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (
      form.targeted_productivity == null ||
      form.actual_productivity == null ||
      form.smv == null ||
      form.no_of_workers == null
    ) {
      alert(
        'Please provide at least targeted productivity, actual productivity, SMV, and number of workers.',
      )
      return
    }

    const summaryText = `Here are my latest KPIs: targeted productivity ${
      form.targeted_productivity
    }, actual productivity ${form.actual_productivity}, idle time ${
      form.idle_time ?? 0
    } minutes, overtime ${form.over_time ?? 0} minutes.`

    onSubmitEvaluate({
      payload: form,
      summaryText,
    })
  }

  return (
    <form className="kpi-form" onSubmit={handleSubmit}>
      <h2>Employee KPIs</h2>
      <p className="kpi-form-description">
        Provide the most recent indicators for this employee. These values
        will be preprocessed and sent to the AI model.
      </p>

      <div className="kpi-grid">
        <label>
          Employee ID
          <input
            name="employee_id"
            value={form.employee_id}
            onChange={handleChange}
          />
        </label>
        <label>
          Employee Email
          <input
            type="email"
            name="employee_email"
            value={form.employee_email}
            onChange={handleChange}
          />
        </label>
        <label>
          Manager ID
          <input
            name="manager_id"
            value={form.manager_id}
            onChange={handleChange}
          />
        </label>
        <label>
          Manager Email
          <input
            type="email"
            name="manager_email"
            value={form.manager_email}
            onChange={handleChange}
          />
        </label>

        <label>
          Date
          <input
            type="date"
            name="date"
            value={form.date || ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Department
          <select
            name="department"
            value={form.department}
            onChange={handleChange}
          >
            <option value="sewing">Sewing</option>
            <option value="finishing">Finishing</option>
            <option value="cutting">Cutting</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Team
          <input
            type="number"
            name="team"
            value={form.team ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Targeted Productivity
          <input
            type="number"
            step="0.01"
            name="targeted_productivity"
            value={form.targeted_productivity ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Actual Productivity
          <input
            type="number"
            step="0.01"
            name="actual_productivity"
            value={form.actual_productivity ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          SMV
          <input
            type="number"
            step="0.01"
            name="smv"
            value={form.smv ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          WIP
          <input
            type="number"
            name="wip"
            value={form.wip ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Overtime (minutes)
          <input
            type="number"
            name="over_time"
            value={form.over_time ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Incentive
          <input
            type="number"
            name="incentive"
            value={form.incentive ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Idle Time (minutes)
          <input
            type="number"
            name="idle_time"
            value={form.idle_time ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Idle Men
          <input
            type="number"
            name="idle_men"
            value={form.idle_men ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Style Changes
          <input
            type="number"
            name="no_of_style_change"
            value={form.no_of_style_change ?? ''}
            onChange={handleChange}
          />
        </label>
        <label>
          Number of Workers
          <input
            type="number"
            name="no_of_workers"
            value={form.no_of_workers ?? ''}
            onChange={handleChange}
          />
        </label>
      </div>

      <button type="submit" className="kpi-submit" disabled={loading}>
        {loading ? 'Analyzing…' : 'Analyze productivity'}
      </button>
    </form>
  )
}

