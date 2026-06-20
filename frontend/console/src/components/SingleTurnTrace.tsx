import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  MOCK_SAMPLES,
  type CriticGuidanceStatusResponse,
  type FullChatResponse,
} from "@emoedu/shared/console";
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

const STORAGE_KEY = "emoagent.console.singleTurnTrace.v1";

interface StoredConsoleTrace {
  selectedId: string;
  customInput: string;
  displayResult: FullChatResponse | null;
  criticGuidance: CriticGuidanceStatusResponse | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readStoredTrace(): StoredConsoleTrace | null {
  if (typeof localStorage === "undefined") {
    return null;
  }

  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (!isRecord(parsed) || typeof parsed.selectedId !== "string") {
      return null;
    }
    const selectedExists = MOCK_SAMPLES.some(
      (sample) => sample.session_id === parsed.selectedId,
    );
    const displayResult =
      isRecord(parsed.displayResult) &&
      typeof parsed.displayResult.session_id === "string"
        ? (parsed.displayResult as unknown as FullChatResponse)
        : null;
    const criticGuidance =
      isRecord(parsed.criticGuidance) &&
      typeof parsed.criticGuidance.session_id === "string"
        ? (parsed.criticGuidance as unknown as CriticGuidanceStatusResponse)
        : null;

    return {
      selectedId: selectedExists ? parsed.selectedId : MOCK_SAMPLES[0].session_id,
      customInput:
        typeof parsed.customInput === "string" ? parsed.customInput : "",
      displayResult,
      criticGuidance,
    };
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function writeStoredTrace(trace: StoredConsoleTrace) {
  if (typeof localStorage === "undefined") {
    return;
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(trace));
}

export function buildConsoleRunSessionId(sampleId: string) {
  const suffix = Math.random().toString(36).slice(2, 8);
  return `${sampleId}-console-${Date.now()}-${suffix}`;
}

export function SingleTurnTrace() {
  const initialTrace = useMemo(() => readStoredTrace(), []);
  const [selectedId, setSelectedId] = useState(
    () => initialTrace?.selectedId ?? MOCK_SAMPLES[0].session_id,
  );
  const [customInput, setCustomInput] = useState(
    () => initialTrace?.customInput ?? "",
  );
  const [displayResult, setDisplayResult] = useState<FullChatResponse | null>(
    () => initialTrace?.displayResult ?? null,
  );
  const [persistedGuidance, setPersistedGuidance] =
    useState<CriticGuidanceStatusResponse | null>(
      () => initialTrace?.criticGuidance ?? null,
    );
  const requestSequence = useRef(0);
  const resumedGuidanceSessionRef = useRef<string | null>(null);
  const {
    criticGuidance,
    guidanceError,
    guidanceLoading,
    loading,
    error,
    refreshGuidance,
    run,
  } = useConsoleRun();

  const selectedSample = useMemo(
    () => MOCK_SAMPLES.find((sample) => sample.session_id === selectedId) ?? MOCK_SAMPLES[0],
    [selectedId],
  );
  const activeResult = displayResult ?? selectedSample;
  const activeGuidance = (
    criticGuidance?.session_id === activeResult.session_id
      ? criticGuidance
      : null
  ) ?? (
    persistedGuidance?.session_id === activeResult.session_id
      ? persistedGuidance
      : null
  );
  const activeScores =
    activeGuidance?.status === "ready" && activeGuidance.scores.length > 0
      ? activeGuidance.scores
      : activeResult.scores;
  const f4Summary = activeGuidance
    ? `guidance: ${activeGuidance.status}; scores: ${activeScores.length}`
    : `scores: ${activeScores.length}`;
  const f4EmptyReason = (() => {
    if (activeGuidance?.status === "pending" || guidanceLoading) {
      return "F4 guidance 正在后台运行，稍等后会显示评分。";
    }
    if (activeGuidance?.status === "failed") {
      return `F4 guidance 失败：${activeGuidance.error || "unknown error"}`;
    }
    if (activeResult.status === "blocked_by_safety") {
      return "安全门拦截后没有进入候选评分。";
    }
    if (activeResult.selected_by?.includes("followup")) {
      return "后续轮次快路径不重新生成候选评分。";
    }
    if (activeResult.candidates.length === 0) {
      return "当前响应没有候选可评分。";
    }
    return "F4 评分尚未返回。";
  })();

  const handleSampleChange = (nextSelectedId: string) => {
    requestSequence.current += 1;
    setDisplayResult(null);
    setPersistedGuidance(null);
    setSelectedId(nextSelectedId);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const currentMessage = customInput.trim() || deriveInput(selectedSample);
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    void run({
      session_id: buildConsoleRunSessionId(selectedSample.session_id),
      current_message: currentMessage,
    })
      .then((response) => {
        if (requestSequence.current === requestId) {
          setDisplayResult(response);
        }
      })
      .catch(() => undefined);
  };

  useEffect(() => {
    if (criticGuidance?.session_id === activeResult.session_id) {
      setPersistedGuidance(criticGuidance);
    }
  }, [activeResult.session_id, criticGuidance]);

  useEffect(() => {
    writeStoredTrace({
      selectedId,
      customInput,
      displayResult,
      criticGuidance: activeGuidance,
    });
  }, [activeGuidance, customInput, displayResult, selectedId]);

  useEffect(() => {
    if (!displayResult || activeGuidance?.status === "ready") {
      return;
    }
    if (resumedGuidanceSessionRef.current === displayResult.session_id) {
      return;
    }

    resumedGuidanceSessionRef.current = displayResult.session_id;
    void refreshGuidance(displayResult.session_id);
  }, [activeGuidance?.status, displayResult, refreshGuidance]);

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
      {guidanceError ? (
        <p className={styles.error}>F4 guidance 错误：{guidanceError}</p>
      ) : null}

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
          label="F3 单候选"
          tone="f3"
          summary={`candidates: ${activeResult.candidates.length}`}
        >
          <CandidatePanel
            bestCandidateId={activeResult.best_candidate_id}
            candidates={activeResult.candidates}
            preferencePair={activeResult.preference_pair}
            scores={activeScores}
          />
        </StageBlock>

        <StageBlock
          label="F4 EPITOME / CASEL Critic"
          tone="f4"
          summary={guidanceLoading ? `${f4Summary}; polling` : f4Summary}
        >
          <ScoreMatrix
            emptyReason={f4EmptyReason}
            preferencePair={activeResult.preference_pair}
            scores={activeScores}
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
