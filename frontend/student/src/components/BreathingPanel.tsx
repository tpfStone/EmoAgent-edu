import styles from "./BreathingPanel.module.css";

interface BreathingPanelProps {
  variant?: "panel" | "inline";
}

export function BreathingPanel({ variant = "panel" }: BreathingPanelProps) {
  const inline = variant === "inline";

  return (
    <section
      className={`${styles.panel} ${inline ? styles.inlinePanel : ""}`}
      aria-label="呼吸练习"
    >
      <div className={styles.breathCircle}>
        <div className={styles.breathCore} />
      </div>
      <div className={styles.copy}>
        <strong>{inline ? "先慢一点" : "呼吸"}</strong>
        <p>吸气四秒，呼气四秒。</p>
      </div>
    </section>
  );
}
