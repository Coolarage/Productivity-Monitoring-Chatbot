import { useMemo, useState } from 'react'
import { postEvaluate } from '../api'
import type { EvaluationResult } from '../types'
import type { ChatMessage } from './ChatTypes'
import { ChatWindow } from './ChatWindow'
import { KpiForm } from './KpiForm'
import './ChatbotLayout.css'

function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ChatbotLayout() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'welcome',
      sender: 'bot',
      text:
        'Welcome to the productivity assistant. Share your latest KPIs and I will provide a prediction and practical recommendations. These insights are decision support, not a final judgment.',
      timestamp: nowTime(),
    },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleEvaluate = async (evaluationInput: {
    payload: Parameters<typeof postEvaluate>[0]
    summaryText: string
  }) => {
    setError(null)
    setLoading(true)

    // Add user message summarizing what was sent
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: 'user',
        text: evaluationInput.summaryText,
        timestamp: nowTime(),
      },
      {
        id: `bot-loading-${Date.now()}`,
        sender: 'bot',
        text: 'Analyzing your KPIs. Please wait a moment...',
        timestamp: nowTime(),
      },
    ])

    try {
      const result: EvaluationResult = await postEvaluate(
        evaluationInput.payload,
      )

      setMessages((prev) => {
        const withoutLast = prev.slice(0, -1)

        const s = result.summary
        const summaryText =
          s.label === 'no_decline'
            ? 'The system does not predict a near-term productivity decline based on your recent indicators.'
            : 'The system indicates an elevated risk of productivity decline based on your recent indicators.'

        const details = (
          <div className="bot-details">
            <div className="bot-section">
              <h4>Summary</h4>
              <p>{s.explanation}</p>
              {s.confidence != null && (
                <p>
                  Model confidence (decline risk):{' '}
                  {s.confidence.toFixed(2)}
                </p>
              )}
            </div>
            {s.weak_areas.length > 0 && (
              <div className="bot-section">
                <h4>Focus areas</h4>
                <ul>
                  {s.weak_areas.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
            {s.recommendations.length > 0 && (
              <div className="bot-section">
                <h4>Suggested actions</h4>
                <ul>
                  {s.recommendations.map((r, idx) => (
                    <li key={`${r.area}-${idx}`}>
                      <strong>{r.area}:</strong> {r.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="bot-section">
              <p className="bot-note">
                Use these insights together with your manager’s judgment. If
                you are experiencing workload pressure, unclear tasks,
                technical blockers, personal circumstances, or insufficient
                training, consider discussing these factors directly.
              </p>
            </div>
          </div>
        )

        return [
          ...withoutLast,
          {
            id: `bot-summary-${Date.now()}`,
            sender: 'bot',
            text: summaryText,
            details,
            timestamp: nowTime(),
          },
        ]
      })
    } catch (e) {
      console.error(e)
      setError(
        e instanceof Error
          ? e.message
          : 'Unexpected error while contacting the backend.',
      )
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-error-${Date.now()}`,
          sender: 'bot',
          text:
            'I was not able to reach the evaluation service. Please check that the backend is running and try again.',
          timestamp: nowTime(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Proactive Productivity Chatbot</h1>
        <p>
          Decision-support assistant for monitoring productivity and
          suggesting next steps.
        </p>
      </header>
      <main className="app-main">
        <section className="chat-section">
          <ChatWindow messages={messages} />
        </section>
        <section className="form-section">
          <KpiForm onSubmitEvaluate={handleEvaluate} loading={loading} />
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    </div>
  )
}

