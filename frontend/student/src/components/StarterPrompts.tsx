import styles from './StarterPrompts.module.css'

const PROMPTS = [
  { emoji: '😮‍💨', text: '今天有点累' },
  { emoji: '💬', text: '想吐槽一件事' },
  { emoji: '🤍', text: '只是想有人在' },
] as const

interface Props {
  onSelect: (text: string) => void
}

export function StarterPrompts({ onSelect }: Props) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.logoArea}>
        <div className={styles.logoRing}>
          <span className={styles.logoDot} aria-hidden="true" />
        </div>
        <p className={styles.greeting}>嗯，我在。</p>
        <p className={styles.sub}>说说今天发生了什么？</p>
      </div>

      <div className={styles.prompts} role="list">
        {PROMPTS.map((p) => (
          <button
            key={p.text}
            className={styles.promptBtn}
            onClick={() => onSelect(p.text)}
            role="listitem"
          >
            <span className={styles.emoji} aria-hidden="true">{p.emoji}</span>
            {p.text}
          </button>
        ))}
      </div>
    </div>
  )
}
