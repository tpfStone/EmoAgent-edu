import type { SessionRecord } from "../hooks/useStudentSessions";
import styles from "./EmotionMemoryPanel.module.css";

interface EmotionMemoryPanelProps {
  sessions: SessionRecord[];
  onClearSessions: () => void;
}

const notice =
  "我现在只在这台设备上保留会话标题和消息，用来帮你回到刚才的话题。跨会话情绪画像还没有接入后端。";

function summarize(session: SessionRecord): string {
  const latest = session.messages.at(-1);

  if (!latest) {
    return "还没有消息";
  }

  const text = latest.text.replace(/\s+/g, " ").trim();
  return text.length > 48 ? `${text.slice(0, 48)}...` : text;
}

export function EmotionMemoryPanel({
  sessions,
  onClearSessions,
}: EmotionMemoryPanelProps) {
  const storedSessions = sessions.filter((session) => session.messages.length > 0);

  return (
    <section className={styles.panel} aria-label="情绪轨迹">
      <div className={styles.header}>
        <span className={styles.dot} />
        <strong>情绪轨迹</strong>
      </div>
      <p className={styles.notice}>{notice}</p>

      <div className={styles.summaryList} aria-label="本地会话摘要">
        {storedSessions.length > 0 ? (
          storedSessions.slice(0, 5).map((session) => (
            <article className={styles.summary} key={session.id}>
              <strong>{session.title}</strong>
              <p>{summarize(session)}</p>
            </article>
          ))
        ) : (
          <p className={styles.empty}>还没有可显示的本地会话。</p>
        )}
      </div>

      <button className={styles.clearButton} type="button" onClick={onClearSessions}>
        让我忘记
      </button>
    </section>
  );
}
