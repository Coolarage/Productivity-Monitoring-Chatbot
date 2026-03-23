import { useRef, useState } from 'react'
import { getCsvDownloadUrl, postEvaluateCsv } from '../api'
import type { CsvBatchEvaluationResponse } from '../types'
import type { ChatMessage } from './ChatTypes'
import { ChatWindow } from './ChatWindow'
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
        'Welcome to the productivity assistant. Upload a CSV file with employee KPI records, and I will evaluate each employee, provide decline probability and recommendations, and keep this as decision support rather than a final judgment.',
      timestamp: nowTime(),
    },
  ])
  const [inputText, setInputText] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const handleUploadAndEvaluate = async () => {
    if (!selectedFile) {
      setError('Please attach a CSV file first.')
      return
    }

    setError(null)
    setLoading(true)
    const userText =
      inputText.trim() ||
      `Please evaluate uploaded CSV file: ${selectedFile.name}`
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: 'user',
        text: userText,
        timestamp: nowTime(),
      },
      {
        id: `bot-loading-${Date.now()}`,
        sender: 'bot',
        text: 'Analyzing uploaded CSV rows and sending employee-manager notifications...',
        timestamp: nowTime(),
      },
    ])

    try {
      const result: CsvBatchEvaluationResponse = await postEvaluateCsv(
        selectedFile,
      )

      setMessages((prev) => {
        const withoutLast = prev.slice(0, -1)
        const summaryText = `Processed ${result.total_rows} row(s): ${result.successful_rows} successful, ${result.failed_rows} failed.`

        const details = (
          <div className="bot-details">
            <div className="bot-section">
              <h4>Batch summary</h4>
              <p>{summaryText}</p>
            </div>

            <div className="bot-section table-scroll">
              <table className="result-table">
                <thead>
                  <tr>
                    <th>employee_id</th>
                    <th>will_decline</th>
                    <th>decline_probability</th>
                    <th>recommended_actions</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row) => (
                    <tr key={`${row.employee_id}-${row.row_index}`}>
                      <td>{row.employee_id}</td>
                      <td>
                        {row.will_decline == null
                          ? '-'
                          : String(row.will_decline)}
                      </td>
                      <td>
                        {row.decline_probability == null
                          ? '-'
                          : row.decline_probability.toFixed(4)}
                      </td>
                      <td>
                        {row.status === 'error'
                          ? `ERROR: ${row.error || 'row processing failed'}`
                          : (
                              <ol className="recommended-actions-list">
                                {row.recommended_actions.map((action, idx) => (
                                  <li key={`${row.employee_id}-action-${idx}`}>
                                    {action}
                                  </li>
                                ))}
                              </ol>
                            )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bot-section">
              <a
                className="download-link"
                href={getCsvDownloadUrl(result.download_url)}
                target="_blank"
                rel="noreferrer"
              >
                Download augmented CSV result
              </a>
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
            'I was not able to process the CSV evaluation. Please verify backend status, CSV column structure, and email credentials.',
          timestamp: nowTime(),
        },
      ])
    } finally {
      setLoading(false)
      setInputText('')
      setSelectedFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Proactive Productivity Chatbot</h1>
        <p>
          Decision-support assistant for batch productivity evaluation.
        </p>
      </header>
      <main className="app-main">
        <section className="chat-section">
          <ChatWindow messages={messages} />
        </section>
      </main>
      <footer className="chat-composer">
        <button
          type="button"
          className="attach-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          aria-label="Attach CSV file"
          title="Attach CSV"
        >
          📎
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden-file-input"
          onChange={(e) => {
            const file = e.target.files?.[0] || null
            setSelectedFile(file)
          }}
        />
        <input
          className="composer-input"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Add optional note and upload CSV with employee rows..."
          disabled={loading}
        />
        <button
          type="button"
          className="send-button"
          onClick={handleUploadAndEvaluate}
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Evaluate CSV'}
        </button>
      </footer>
      {selectedFile && (
        <div className="selected-file-banner">Attached: {selectedFile.name}</div>
      )}
      {error && <p className="error-text">{error}</p>}
    </div>
  )
}

