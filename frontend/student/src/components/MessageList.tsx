import type { StudentMessage } from "../hooks/useStudentSessions";
import styles from "./MessageList.module.css";

interface MessageListProps {
  messages: StudentMessage[];
}

function paragraphs(text: string): string[] {
  return text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className={styles.messageList} aria-live="polite">
      {messages.map((message) =>
        message.role === "agent" ? (
          <article className={styles.agentMessage} key={message.id}>
            <div className={styles.agentLabel}>
              <span className={styles.agentDot} />
              <span>EmoAgent</span>
            </div>
            <div className={styles.agentText}>
              {paragraphs(message.text).map((paragraph, index) => (
                <p key={`${message.id}-${index}`}>{paragraph}</p>
              ))}
            </div>
          </article>
        ) : (
          <article className={styles.studentRow} key={message.id}>
            <p className={styles.studentMessage}>{message.text}</p>
          </article>
        ),
      )}
    </div>
  );
}
