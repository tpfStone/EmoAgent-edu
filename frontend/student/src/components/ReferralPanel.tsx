// ============================================================
// ReferralPanel — 危机转介面板
// 规格: docs/frontend/frontend-cc-spec.md §5.3
//
// 安全铁律（不可更改）：
// 1. risk_level 为 yellow/red 时替换 InputArea
// 2. 号码硬编码，不经任何动态生成
// 3. red 额外显示 120/110
// 4. 输入框被禁用，禁止继续对话
// ============================================================
import type { RiskLevel } from '@emoedu/shared'
import styles from './ReferralPanel.module.css'

// ── 固定文案常量（不经动态生成，不得从后端取值）──────────────
const REFERRAL = {
  title: '我注意到你可能需要更多支持',
  empathy: '你愿意说出来，很勇敢。',
  guide: '现在，可以联系一位你信任的大人吗？',
  hotlines: [
    { label: '心理援助热线', tel: '12356' },
    { label: '青少年服务台', tel: '12355' },
  ],
  emergency: [
    { label: '急救', tel: '120' },
    { label: '警察', tel: '110' },
  ],
} as const

interface Props {
  riskLevel: RiskLevel   // yellow | red（green 时此组件不渲染）
  replyText: string      // AI 在转介前说的最后一句话
}

export function ReferralPanel({ riskLevel, replyText }: Props) {
  const isRed = riskLevel === 'red'

  return (
    <div
      className={`${styles.panel} ${isRed ? styles.panelRed : ''}`}
      role="alert"
      aria-live="assertive"
    >
      {/* AI 最后的回复（已渲染过，此处再显示一次作为过渡） */}
      {replyText && (
        <p className={styles.lastReply}>{replyText}</p>
      )}

      <div className={styles.card}>
        <h2 className={styles.title}>{REFERRAL.title}</h2>
        <p className={styles.empathy}>{REFERRAL.empathy}</p>
        <p className={styles.guide}>{REFERRAL.guide}</p>

        {/* 主要热线 */}
        <div className={styles.hotlineRow}>
          {REFERRAL.hotlines.map((h) => (
            <a
              key={h.tel}
              href={`tel:${h.tel}`}
              className={styles.hotlineBtn}
              aria-label={`拨打${h.label} ${h.tel}`}
            >
              <span className={styles.hotlineLabel}>{h.label}</span>
              <span className={styles.hotlineTel}>{h.tel}</span>
            </a>
          ))}
        </div>

        {/* red 级别额外显示紧急号码 */}
        {isRed && (
          <>
            <p className={styles.emergencyNote}>
              如果你现在有紧急危险，请立刻拨打：
            </p>
            <div className={styles.emergencyRow}>
              {REFERRAL.emergency.map((e) => (
                <a
                  key={e.tel}
                  href={`tel:${e.tel}`}
                  className={`${styles.hotlineBtn} ${styles.emergencyBtn}`}
                  aria-label={`拨打${e.label} ${e.tel}`}
                >
                  <span className={styles.hotlineLabel}>{e.label}</span>
                  <span className={styles.hotlineTel}>{e.tel}</span>
                </a>
              ))}
            </div>
          </>
        )}
      </div>

      {/* 替换 InputArea 的占位提示 */}
      <div className={styles.inputLock} aria-hidden="true">
        <span>💛 先照顾好自己</span>
      </div>
    </div>
  )
}
