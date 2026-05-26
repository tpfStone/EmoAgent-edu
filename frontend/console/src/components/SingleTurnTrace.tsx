import { FormEvent, useMemo, useRef, useState } from "react";
import { MOCK_SAMPLES, type FullChatResponse } from "@emoedu/shared/console";
import { useConsoleRun } from "../hooks/useConsoleRun";
import { CandidatePanel } from "./CandidatePanel";
import { ScoreMatrix } from "./ScoreMatrix";
import { StageBlock } from "./StageBlock";
import styles from "./SingleTurnTrace.module.css";

const samplePrompts: Record<string, string> = {
  syn_0007: "最近作业和考试都压在一起，我不知道从哪里开始。",
  syn_0021: "同学把我排除在外，还在背后笑我，我很难受。",
  syn_0032: "家里总觉得我不够努力，我想解释但又怕吵起来。",
  crisis: "我现在有强烈的危险念头，需要马上有人介入。",
};

function deriveInput(sample: FullChatResponse) {
  return samplePrompts[sample.session_id] ?? sample.reply_text.slice(0, 72);
}

function formatList(values: string[]) {
  return values.length > 0 ? values.join(" / ") : "未激活";
}

export function SingleTurnTrace() {
  const [selectedId, setSelectedId] = useState(MOCK_SAMPLES[0].session_id);
  const [customInput, setCustomInput] = useState("");
  const [displayResult, setDisplayResult] = useState<FullChatResponse | null>(null);
  const requestSequence = useRef(0);
  const { loading, error, run } = useConsoleRun();

  const selectedSample = useMemo(
    () => MOCK_SAMPLES.find((sample) => sample.session_id === selectedId) ?? MOCK_SAMPLES[0],
    [selectedId],
  );
  const activeResult = displayResult ?? selectedSample;

  const handleSampleChange = (nextSelectedId: string) => {
    requestSequence.current += 1;
    setDisplayResult(null);
    setSelectedId(nextSelectedId);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const currentMessage = customInput.trim() || deriveInput(selectedSample);
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    void run({
      session_id: selectedSample.session_id,
      current_message: currentMessage,
    })
      .then((response) => {
        if (requestSequence.current === requestId) {
          setDisplayResult(response);
        }
      })
      .catch(() => undefined);
  };

  return (
    <div className={styles.trace}>
      <header className={styles.topline}>
        <div>
          <p className={styles.kicker}>Single-turn trace</p>
          <h2>候选生成、边界出局与最终回复</h2>
        </div>
        <span className={`${styles.risk} ${styles[activeResult.risk_level]}`}>
          {activeResult.risk_level}
        </span>
      </header>

      <form className={styles.controls} onSubmit={handleSubmit}>
        <label className={styles.field}>
          <span>样本</span>
          <select
            value={selectedId}
            onChange={(event) => handleSampleChange(event.target.value)}
          >
            {MOCK_SAMPLES.map((sample) => (
              <option key={sample.session_id} value={sample.session_id}>
                {sample.session_id}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span>自定义输入</span>
          <input
            value={customInput}
            onChange={(event) => setCustomInput(event.target.value)}
            placeholder={deriveInput(selectedSample)}
          />
        </label>

        <button className={styles.runButton} type="submit" disabled={loading}>
          {loading ? "运行中" : "运行"}
        </button>
      </form>

      {error ? <p className={styles.error}>运行错误：{error}</p> : null}

      <div className={styles.sections}>
        <StageBlock
          label="F1 安全门"
          tone="f1"
          summary={`status: ${activeResult.status}`}
        >
          <dl className={styles.metrics}>
            <div>
              <dt>risk_level</dt>
              <dd>{activeResult.risk_level}</dd>
            </div>
            <div>
              <dt>failed_module</dt>
              <dd>{activeResult.failed_module ?? "none"}</dd>
            </div>
            <div>
              <dt>failure_reason</dt>
              <dd>{activeResult.failure_reason || "none"}</dd>
            </div>
          </dl>
        </StageBlock>

        <StageBlock
          label="F2 情境 + CASEL"
          tone="f2"
          summary={`scenario: ${activeResult.scenario ?? "safety override"}`}
        >
          <dl className={styles.metrics}>
            <div>
              <dt>session_id</dt>
              <dd>{activeResult.session_id}</dd>
            </div>
            <div>
              <dt>activated_casel</dt>
              <dd>{formatList(activeResult.activated_casel)}</dd>
            </div>
          </dl>
        </StageBlock>

        <StageBlock
          label="F3 双候选"
          tone="f3"
          summary={`candidates: ${activeResult.candidates.length}`}
        >
          <CandidatePanel
            bestCandidateId={activeResult.best_candidate_id}
            candidates={activeResult.candidates}
            preferencePair={activeResult.preference_pair}
            scores={activeResult.scores}
          />
        </StageBlock>

        <StageBlock
          label="F4 EPITOME / CASEL Critic"
          tone="f4"
          summary={`scores: ${activeResult.scores.length}`}
        >
          <ScoreMatrix
            preferencePair={activeResult.preference_pair}
            scores={activeResult.scores}
          />
        </StageBlock>

        <section className={styles.studentPreview} aria-label="学生实际看到的回复">
          <header className={styles.previewHeader}>
            <div>
              <p className={styles.kicker}>Student-visible reply</p>
              <h3>学生实际看到的回复</h3>
            </div>
            <span>只读预览，不连接学生端状态</span>
          </header>
          <p className={styles.studentReply}>{activeResult.reply_text}</p>
        </section>
      </div>
    </div>
  );
}
