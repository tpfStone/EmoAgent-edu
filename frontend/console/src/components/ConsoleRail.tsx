import styles from "./ConsoleRail.module.css";

export type ConsoleTab = "single" | "batch" | "framework";

interface ConsoleRailProps {
  activeTab: ConsoleTab;
  onTabChange: (tab: ConsoleTab) => void;
}

const tabs: Array<{ id: ConsoleTab; label: string; detail: string }> = [
  { id: "single", label: "单轮追踪", detail: "F1-F4" },
  { id: "batch", label: "批量证据", detail: "45 turns" },
  { id: "framework", label: "框架对标", detail: "Safety / SEL" },
];

export function ConsoleRail({ activeTab, onTabChange }: ConsoleRailProps) {
  return (
    <aside className={styles.rail}>
      <div className={styles.titleBlock}>
        <p className={styles.kicker}>EmoAgent Edu</p>
        <h1>研究控制台</h1>
      </div>

      <nav className={styles.nav} aria-label="Console views">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={tab.id === activeTab ? styles.activeTab : styles.tab}
            type="button"
            onClick={() => onTabChange(tab.id)}
            aria-pressed={tab.id === activeTab}
          >
            <span>{tab.label}</span>
            <small>{tab.detail}</small>
          </button>
        ))}
      </nav>
    </aside>
  );
}
