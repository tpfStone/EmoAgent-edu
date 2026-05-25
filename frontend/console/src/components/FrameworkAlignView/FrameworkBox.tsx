import styles from './FrameworkBox.module.css'

interface Props {
  title: string
  subtitle: string
  colorVar: string   // CSS 变量名，如 '--cssrs-green'
  children: React.ReactNode
}

export function FrameworkBox({ title, subtitle, colorVar, children }: Props) {
  return (
    <div
      className={styles.box}
      style={{ '--fw-color': `var(${colorVar})` } as React.CSSProperties}
    >
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        <span className={styles.subtitle}>{subtitle}</span>
      </div>
      <div className={styles.body}>{children}</div>
    </div>
  )
}
