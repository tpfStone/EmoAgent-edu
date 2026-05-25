// ============================================================
// EmotionTimeline — 情绪轨迹面板（当前为 mock 占位）
//
// TODO: 后端画像接口未实现（emoedu-post-mvp-guide.md §P3 后续）
//   - 后端存轻量画像（情境分布、情绪基调趋势），不存原文
//   - 前端消费 GET /profile/{session_id} 返回画像数据
//   - 必须满足：对孩子透明、可删除（「让我忘记」按钮）、
//     不用于制造与可信成年人的隔离
// ============================================================
import styles from './EmotionTimeline.module.css'

// Mock 情绪数据（占位）
const MOCK_TIMELINE = [
  { date: '今天', emoji: '😮‍💨', label: '有点累' },
  { date: '昨天', emoji: '😕', label: '有些烦躁' },
  { date: '2 天前', emoji: '😶', label: '还好' },
]

interface Props {
  onClose: () => void
}

export function EmotionTimeline({ onClose }: Props) {
  return (
    <div className={styles.panel} role="dialog" aria-label="情绪轨迹">
      <div className={styles.header}>
        <span className={styles.title}>情绪轨迹</span>
        <button className={styles.closeBtn} onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      <p className={styles.notice}>
        {/* 儿童透明性要求：明示记录了什么 */}
        我记得这些关于你的事：
      </p>

      <ul className={styles.list}>
        {MOCK_TIMELINE.map((item, i) => (
          <li key={i} className={styles.item}>
            <span className={styles.emoji}>{item.emoji}</span>
            <div className={styles.info}>
              <span className={styles.itemLabel}>{item.label}</span>
              <span className={styles.itemDate}>{item.date}</span>
            </div>
          </li>
        ))}
      </ul>

      {/* 儿童可删除要求：真实调用删除接口（TODO） */}
      <button className={styles.forgetBtn} onClick={() => {
        // TODO: 调用 DELETE /profile/{session_id} 删除画像
        alert('让我忘记功能将在后端接口完成后启用')
      }}>
        让我忘记这些
      </button>

      <p className={styles.mockNote}>
        ⚠️ 当前为演示数据（TODO: 接入真实画像接口）
      </p>
    </div>
  )
}
