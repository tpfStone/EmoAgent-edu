import { useState, useCallback } from 'react'
import type { StudentChatView } from '@emoedu/shared'

// ----------------------------------------------------------------
// 会话消息（前端内部类型，不出学生端）
// ----------------------------------------------------------------
export type MessageRole = 'user' | 'ai'

export interface ChatMessage {
  id: string
  role: MessageRole
  text: string
  timestamp: number
}

// ----------------------------------------------------------------
// 持久化会话记录（存 localStorage）
// ----------------------------------------------------------------
export interface SessionRecord {
  session_id: string
  title: string           // 取首条用户消息，截断 20 字
  messages: ChatMessage[]
  createdAt: number
}

const STORAGE_KEY = 'emoedu_sessions'

function loadSessions(): SessionRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as SessionRecord[]) : []
  } catch {
    return []
  }
}

function saveSessions(sessions: SessionRecord[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
}

function newSessionId(): string {
  return crypto.randomUUID()
}

function makeTitle(text: string): string {
  return text.slice(0, 20) + (text.length > 20 ? '…' : '')
}

// ----------------------------------------------------------------
// Hook
// ----------------------------------------------------------------
export function useSession() {
  const [sessions, setSessions] = useState<SessionRecord[]>(loadSessions)
  const [currentId, setCurrentId] = useState<string>(() => {
    const existing = loadSessions()
    return existing.length > 0 ? existing[0].session_id : newSessionId()
  })

  const currentSession = sessions.find((s) => s.session_id === currentId) ?? null

  // 追加一条用户消息 —— 同时建立 session record（如不存在）
  const appendUserMessage = useCallback(
    (text: string) => {
      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        text,
        timestamp: Date.now(),
      }
      setSessions((prev) => {
        const next = [...prev]
        const idx = next.findIndex((s) => s.session_id === currentId)
        if (idx >= 0) {
          next[idx] = {
            ...next[idx],
            messages: [...next[idx].messages, msg],
          }
        } else {
          next.unshift({
            session_id: currentId,
            title: makeTitle(text),
            messages: [msg],
            createdAt: Date.now(),
          })
        }
        saveSessions(next)
        return next
      })
      return msg.id
    },
    [currentId]
  )

  // 追加 AI 回复（只取 StudentChatView 里的 reply_text）
  const appendAiMessage = useCallback(
    (view: StudentChatView) => {
      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'ai',
        text: view.reply_text,
        timestamp: Date.now(),
      }
      setSessions((prev) => {
        const next = [...prev]
        const idx = next.findIndex((s) => s.session_id === currentId)
        if (idx >= 0) {
          next[idx] = {
            ...next[idx],
            messages: [...next[idx].messages, msg],
          }
          saveSessions(next)
        }
        return next
      })
    },
    [currentId]
  )

  // 开启新对话
  const newSession = useCallback(() => {
    const id = newSessionId()
    setCurrentId(id)
    // 不提前 push，等有第一条消息时再建
  }, [])

  // 切换到历史会话
  const switchSession = useCallback((id: string) => {
    setCurrentId(id)
  }, [])

  return {
    sessions,
    currentId,
    currentSession,
    appendUserMessage,
    appendAiMessage,
    newSession,
    switchSession,
  }
}
