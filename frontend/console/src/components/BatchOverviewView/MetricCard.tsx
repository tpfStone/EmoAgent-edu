import styles from './MetricCard.module.css'

interface Props {
  value: string | number
  label: string
  sub?: string
  accent?: boolean   // 暖红点缀（边界拦截卡）
}

export function MetricCard({ value, label, sub, accent }: Props) {
  return (
    <div className={`${styles.card} ${accent ? styles.accent : ''}`}>
      <div className={styles.value}>{value}</div>
      <div className={styles.label}>{label}</div>
      {sub && <div className={styles.sub}>{sub}</div>}
    </div>
  )
}
