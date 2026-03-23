import type { ReactNode } from 'react'

export type ChatSender = 'user' | 'bot'

export type ChatMessage = {
  id: string
  sender: ChatSender
  text: string
  /**
   * Optional structured section, e.g. recommendations list.
   */
  details?: ReactNode
  timestamp: string
}

