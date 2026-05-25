// ============================================================
// BreathingTool — 纯前端呼吸动画小工具
// 规格: §5.4 — 8s 一吸一呼，无后端依赖
// 对应 CASEL 自我管理
// ============================================================
import { useState } from 'react'
import styles from './BreathingTool.module.css'

export function BreathingTool() {
  const [open, setOpen] = useState(false)

  return (
    <div className={styles.container}>
      <button
        className={`${styles.trigger} ${open ? styles.triggerActive : ''}`}
        onClick={() => setOpen((v) => !v)}
        aria-label="呼吸练习"
        title="呼吸小工具"
      >
        🫁
      </button>

      {open && (
        <div className={styles.panel} role="dialog" aria-label="呼吸练习">
          <p className={styles.label}>跟着呼吸</p>
          <div className={styles.breathCircle} aria-hidden="true">
            <div className={styles.innerCircle} />
          </div>
          <p className={styles.hint}>4 秒吸气 · 4 秒呼气</p>
          <button
            className={styles.closeBtn}
            onClick={() => setOpen(false)}
            aria-label="关闭呼吸练习"
          >
            好了
          </button>
        </div>
      )}
    </div>
  )
}
