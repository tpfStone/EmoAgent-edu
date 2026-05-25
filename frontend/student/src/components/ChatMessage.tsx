import type { ChatMessage as ChatMessageType } from '../hooks/useSession'
import styles from './ChatMessage.module.css'

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  if (message.role === 'ai') {
    return (
      <div className={styles.aiWrapper}>
        <div className={styles.aiLabel}>
          <span className={styles.aiDot} aria-hidden="true" />
          EmoAgent
        </div>
        <div className={styles.aiBubble}>
          {message.text.split('\n').map((line, i) =>
            line ? <p key={i}>{line}</p> : <br key={i} />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.userWrapper}>
      <div className={styles.userBubble}>{message.text}</div>
    </div>
  )
}
