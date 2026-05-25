import styles from './StageCard.module.css'

export type StageId = 'F1' | 'F2' | 'F3' | 'F4'

const STAGE_META: Record<StageId, { label: string; desc: string; colorVar: string }> = {
  F1: { label: 'F1 安全门',   desc: 'Safety Gate',       colorVar: '--f1-green' },
  F2: { label: 'F2 情境识别', desc: 'Scenario + CASEL',  colorVar: '--f2-blue' },
  F3: { label: 'F3 双候选',   desc: 'Dual Candidates',   colorVar: '--f3-purple' },
  F4: { label: 'F4 打分择优', desc: 'EPITOME Critic',    colorVar: '--f4-gold' },
}

interface Props {
  stage: StageId
  revealed: boolean
  onReveal: () => void
  children: React.ReactNode
}

export function StageCard({ stage, revealed, onReveal, children }: Props) {
  const meta = STAGE_META[stage]

  return (
    <div
      className={`${styles.card} ${revealed ? styles.revealed : ''}`}
      style={{ '--stage-color': `var(${meta.colorVar})` } as React.CSSProperties}
    >
      <div className={styles.header} onClick={!revealed ? onReveal : undefined}>
        <div className={styles.stageTag}>{meta.label}</div>
        <div className={styles.stageDesc}>{meta.desc}</div>
        {!revealed && (
          <button className={styles.revealBtn} aria-label={`展开${meta.label}`}>
            揭示 →
          </button>
        )}
      </div>

      {revealed && (
        <div className={styles.body}>{children}</div>
      )}
    </div>
  )
}
