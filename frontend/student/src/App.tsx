import { useRef, useEffect, useState } from 'react'
import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import { ChatMessage } from './components/ChatMessage'
import { InputArea } from './components/InputArea'
import { ReferralPanel } from './components/ReferralPanel'
import { Sidebar } from './components/Sidebar'
import { StarterPrompts } from './components/StarterPrompts'
import { BreathingTool } from './components/BreathingTool'
import { EmotionTimeline } from './components/EmotionTimeline'
import styles from './App.module.css'

export default function App() {
  const {
    sessions,
    currentId,
    currentSession,
    appendUserMessage,
    appendAiMessage,
    newSession,
    switchSession,
  } = useSession()

  const {
    loading,
    lastRiskLevel,
    referralActive,
    sendMessage,
    resetReferral,
  } = useChat(currentId)

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [timelineOpen, setTimelineOpen] = useState(false)
  const [prefill, setPrefill] = useState<string | undefined>()

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentSession?.messages.length])

  const handleSend = async (text: string) => {
    appendUserMessage(text)
    await sendMessage(text, (view) => {
      appendAiMessage(view)
    })
  }

  const handleNew = () => {
    newSession()
    resetReferral()
    setSidebarOpen(false)
  }

  const handleSwitch = (id: string) => {
    switchSession(id)
    resetReferral()
    setSidebarOpen(false)
  }

  const messages = currentSession?.messages ?? []
  const hasMessages = messages.length > 0

  // 危机场景下展示的最后一条 AI 回复文本
  const lastAiText =
    messages.filter((m) => m.role === 'ai').at(-1)?.text ?? ''

  return (
    <div className={styles.root}>
      {/* 侧边栏 */}
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          currentId={currentId}
          onSwitch={handleSwitch}
          onNew={handleNew}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      {/* 主区域 */}
      <div className={styles.main}>
        {/* 顶栏 */}
        <header className={styles.topbar}>
          <button
            className={styles.menuBtn}
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="打开历史对话"
          >
            ☰
          </button>
          <div className={styles.topTitle}>
            <span className={styles.topDot} aria-hidden="true" />
            EmoAgent
          </div>
          {/* 情绪轨迹按钮 */}
          <div className={styles.topActions}>
            <div className={styles.actionWrapper}>
              <button
                className={styles.iconBtn}
                onClick={() => setTimelineOpen((v) => !v)}
                aria-label="情绪轨迹"
                title="情绪轨迹"
              >
                📈
              </button>
              {timelineOpen && (
                <EmotionTimeline onClose={() => setTimelineOpen(false)} />
              )}
            </div>
            <div className={styles.actionWrapper}>
              <BreathingTool />
            </div>
          </div>
        </header>

        {/* 消息区 */}
        <div className={styles.messageArea} role="log" aria-live="polite">
          {!hasMessages ? (
            <StarterPrompts onSelect={(text) => setPrefill(text)} />
          ) : (
            <div className={styles.messageList}>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入区 / 危机面板 */}
        {referralActive ? (
          <ReferralPanel
            riskLevel={lastRiskLevel}
            replyText={lastAiText}
          />
        ) : (
          <InputArea
            onSend={handleSend}
            loading={loading}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill(undefined)}
          />
        )}
      </div>
    </div>
  )
}

// AI 思考中的打点动画
function TypingIndicator() {
  return (
    <div className={styles.typing} aria-label="EmoAgent 正在输入">
      <span className={styles.typingDot} />
      <span className={styles.typingDot} />
      <span className={styles.typingDot} />
    </div>
  )
}
