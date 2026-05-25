// 研究分析台左侧导航（依 ux-fig3-console-ia.svg）
import styles from './Sidebar.module.css'

export type ConsoleTab = 'single' | 'batch' | 'framework'

const TABS: { id: ConsoleTab; label: string; sub: string }[] = [
  { id: 'single',    label: '单轮追踪',   sub: 'pipeline trace' },
  { id: 'batch',     label: '批量总览',   sub: '45-sample run' },
  { id: 'framework', label: '框架对标',   sub: 'CASEL·EPITOME·C-SSRS' },
]

interface Props {
  activeTab: ConsoleTab
  onTabChange: (tab: ConsoleTab) => void
}

export function Sidebar({ activeTab, onTabChange }: Props) {
  return (
    <aside className={styles.sidebar} aria-label="分析台导航">
      <div className={styles.brand}>
        <span className={styles.brandTitle}>EmoAgent</span>
        <span className={styles.brandSub}>研究分析台</span>
      </div>

      <nav className={styles.nav}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`${styles.tabBtn} ${activeTab === tab.id ? styles.active : ''}`}
            onClick={() => onTabChange(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span className={styles.tabLabel}>{tab.label}</span>
            <span className={styles.tabSub}>{tab.sub}</span>
          </button>
        ))}
      </nav>

      <div className={styles.footer}>
        离线 · 学生端不可见
      </div>
    </aside>
  )
}
