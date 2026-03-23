import type { ChatMessage } from './ChatTypes'
import './ChatWindow.css'

type ChatWindowProps = {
  messages: ChatMessage[]
}

export function ChatWindow({ messages }: ChatWindowProps) {
  return (
    <div className="chat-window">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`chat-message chat-message-${m.sender}`}
        >
          <div className="chat-bubble">
            <p className="chat-text">{m.text}</p>
            {m.details && <div className="chat-details">{m.details}</div>}
            <span className="chat-timestamp">{m.timestamp}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

