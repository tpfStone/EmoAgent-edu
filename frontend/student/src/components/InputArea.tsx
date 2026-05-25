import { useState, useRef, useEffect } from 'react'
import styles from './InputArea.module.css'

interface Props {
  onSend: (text: string) => void
  loading: boolean
  prefill?: string   // StarterPrompts 点击后填入
  onPrefillConsumed?: () => void
}

export function InputArea({ onSend, loading, prefill, onPrefillConsumed }: Props) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 收到 prefill 时填入并发送
  useEffect(() => {
    if (prefill) {
      setText(prefill)
      onPrefillConsumed?.()
      // 微任务后自动发送
      setTimeout(() => {
        onSend(prefill)
        setText('')
      }, 0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill])

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    onSend(trimmed)
    setText('')
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // 自适应高度
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [text])

  return (
    <div className={styles.wrapper}>
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="说说你的想法……"
        disabled={loading}
        rows={1}
        aria-label="输入消息"
      />
      <button
        className={styles.sendBtn}
        onClick={handleSend}
        disabled={loading || !text.trim()}
        aria-label="发送"
        title="发送（Enter）"
      >
        {loading ? (
          <span className={styles.spinner} aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M3 10L17 10M17 10L11 4M17 10L11 16"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
    </div>
  )
}
