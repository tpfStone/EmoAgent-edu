import type { GeneratorCandidate } from '@emoedu/shared'
import styles from './CandidateCard.module.css'

interface Props {
  candidate: GeneratorCandidate
  isBest: boolean
}

export function CandidateCard({ candidate, isBest }: Props) {
  const isEmpathy = candidate.orientation === '共情型'

  return (
    <div className={`${styles.card} ${isBest ? styles.best : ''}`}>
      <div className={styles.header}>
        <span className={`${styles.tag} ${isEmpathy ? styles.empathyTag : styles.reflectTag}`}>
          {candidate.orientation}
        </span>
        <span className={styles.id}>{candidate.candidate_id}</span>
        {isBest && <span className={styles.bestBadge}>✓ 最优</span>}
      </div>
      <p className={styles.text}>{candidate.text}</p>
    </div>
  )
}
