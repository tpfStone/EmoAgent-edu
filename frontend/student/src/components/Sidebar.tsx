import type { SessionRecord } from '../hooks/useSession'
import styles from './Sidebar.module.css'

interface Props {
  sessions: SessionRecord[]
  currentId: string
  onSwitch: (id: string) => void
  onNew: () => void
  onClose: () => void
}

export function Sidebar({ sessions, currentId, onSwitch, onNew, onClose }: Props) {
  return (
    <aside className={styles.sidebar} aria-label="历史对话">
      <div className={styles.header}>
        <span className={styles.brand}>
          <span className={styles.brandDot} />
          EmoAgent
        </span>
        <button
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="关闭侧边栏"
        >
          ✕
        </button>
      </div>

      <button className={styles.newBtn} onClick={onNew}>
        + 开启新对话
      </button>

      <nav className={styles.list}>
        {sessions.length === 0 && (
          <p className={styles.empty}>还没有历史对话</p>
        )}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            className={`${styles.item} ${
              s.session_id === currentId ? styles.active : ''
            }`}
            onClick={() => onSwitch(s.session_id)}
            title={s.title}
          >
            <span className={styles.itemTitle}>{s.title || '新对话'}</span>
            <span className={styles.itemTime}>
              {formatTime(s.createdAt)}
            </span>
          </button>
        ))}
      </nav>
    </aside>
  )
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
