import type { SessionRecord } from "../hooks/useStudentSessions";
import styles from "./ConversationHistoryPanel.module.css";

interface ConversationHistoryPanelProps {
  sessions: SessionRecord[];
  onClearSessions: () => void;
}

const notice =
  '这里是你在这台设备上聊过的话题，方便你回到刚才的对话。我不会分析或记住"你是什么样的人"，也不会把这些发到别处。';

function summarize(session: SessionRecord): string {
  const latest = session.messages.at(-1);

  if (!latest) {
    return "还没有消息";
  }

  const text = latest.text.replace(/\s+/g, " ").trim();
  return text.length > 48 ? `${text.slice(0, 48)}...` : text;
}

export function ConversationHistoryPanel({
  sessions,
  onClearSessions,
}: ConversationHistoryPanelProps) {
  const storedSessions = sessions.filter((session) => session.messages.length > 0);

  return (
    <section className={styles.panel} aria-label="我聊过的">
      <div className={styles.header}>
        <span className={styles.dot} />
        <strong>我聊过的</strong>
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
