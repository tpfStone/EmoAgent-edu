import styles from "./StarterPrompts.module.css";

const prompts = [
  "今天有点累",
  "想吐槽一件事",
  "只是想有人在",
  "有点开心，想分享",
] as const;

interface StarterPromptsProps {
  disabled?: boolean;
  onPick: (label: string) => void;
}

export function StarterPrompts({ disabled = false, onPick }: StarterPromptsProps) {
  return (
    <div className={styles.prompts} aria-label="开场提示">
      {prompts.map((prompt) => (
        <button
          className={styles.promptButton}
          disabled={disabled}
          key={prompt}
          type="button"
          onClick={() => onPick(prompt)}
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
