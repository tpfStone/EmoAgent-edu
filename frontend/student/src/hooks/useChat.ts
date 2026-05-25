import { useState, useCallback } from 'react'
import { fetchChatStudent } from '@emoedu/shared'
import type { StudentChatView, RiskLevel } from '@emoedu/shared'

// 来自 app/config.py CHAT_FALLBACK_MESSAGE
const FALLBACK_TEXT = '我现在有点没反应过来，要不你再说一次？'

export interface ChatState {
  loading: boolean
  lastRiskLevel: RiskLevel
  referralActive: boolean  // yellow/red 时 true，锁住输入框
}

export function useChat(sessionId: string) {
  const [loading, setLoading] = useState(false)
  const [lastRiskLevel, setLastRiskLevel] = useState<RiskLevel>('green')
  const [referralActive, setReferralActive] = useState(false)

  const sendMessage = useCallback(
    async (
      text: string,
      onSuccess: (view: StudentChatView) => void
    ): Promise<void> => {
      setLoading(true)
      try {
        const view = await fetchChatStudent({
          session_id: sessionId,
          current_message: text,
        })
        setLastRiskLevel(view.risk_level)
        if (view.risk_level !== 'green') {
          setReferralActive(true)
        }
        onSuccess(view)
      } catch {
        // 绝不向学生暴露原始错误或 failure_reason
        onSuccess({
          session_id: sessionId,
          reply_text: FALLBACK_TEXT,
          risk_level: 'green',
        })
      } finally {
        setLoading(false)
      }
    },
    [sessionId]
  )

  // 重置危机面板（新对话时调用）
  const resetReferral = useCallback(() => {
    setReferralActive(false)
    setLastRiskLevel('green')
  }, [])

  return { loading, lastRiskLevel, referralActive, sendMessage, resetReferral }
}
