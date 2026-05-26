import type { ReactNode } from "react";
import styles from "./StageBlock.module.css";

type StageTone = "f1" | "f2" | "f3" | "f4" | "final";

interface StageBlockProps {
  label: string;
  tone: StageTone;
  summary?: string;
  children: ReactNode;
}

export function StageBlock({ label, tone, summary, children }: StageBlockProps) {
  return (
    <section className={`${styles.stage} ${styles[tone]}`}>
      <header className={styles.header}>
        <h2>{label}</h2>
        {summary ? <p>{summary}</p> : null}
      </header>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
