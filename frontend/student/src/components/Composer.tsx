import { FormEvent, KeyboardEvent, useState } from "react";
import styles from "./Composer.module.css";

interface ComposerProps {
  disabled?: boolean;
  loading?: boolean;
  onSend: (text: string) => void;
}

export function Composer({
  disabled = false,
  loading = false,
  onSend,
}: ComposerProps) {
  const [value, setValue] = useState("");

  function submit() {
    const text = value.trim();

    if (!text || disabled || loading) {
      return;
    }

    setValue("");
    onSend(text);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className={styles.composer} onSubmit={handleSubmit}>
      <textarea
        aria-label="输入消息"
        className={styles.input}
        disabled={disabled || loading}
        rows={1}
        value={value}
        placeholder="想说点什么..."
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        aria-label={loading ? "正在回应" : "发送"}
        className={styles.sendButton}
        disabled={disabled || loading || value.trim().length === 0}
        type="submit"
      >
        <span aria-hidden="true">{loading ? "..." : "↑"}</span>
      </button>
    </form>
  );
}
