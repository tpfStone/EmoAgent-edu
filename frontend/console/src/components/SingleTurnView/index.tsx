// ============================================================
// SingleTurnView — 单轮 pipeline 追踪视图
// 规格: §6.1 F1→F2→F3→F4 分步揭示，含输入/输出闭环
// ============================================================
import { useState } from 'react'
import { fetchChat } from '@emoedu/shared'
import type { FullChatResponse } from '@emoedu/shared'
import { MOCK_SAMPLES } from '@emoedu/shared'
import { StageCard } from './StageCard'
import { CandidateCard } from './CandidateCard'
import { ScoreTable } from './ScoreTable'
import styles from './SingleTurnView.module.css'

type Stage = 0 | 1 | 2 | 3 | 4  // 0=未开始，1-4=揭示到对应阶段

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MODE: string = ((import.meta as any)?.env?.VITE_API_MODE) ?? 'mock'

export function SingleTurnView() {
  const [selectedSampleId, setSelectedSampleId] = useState<string>(MOCK_SAMPLES[0].id)
  const [customInput, setCustomInput] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  const [response, setResponse] = useState<FullChatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [revealedStage, setRevealedStage] = useState<Stage>(0)

  const selectedSample = MOCK_SAMPLES.find((s) => s.id === selectedSampleId)
  const inputText = useCustom ? customInput : (selectedSample?.input ?? '')

  const handleRun = async () => {
    if (!inputText.trim()) return
    setLoading(true)
    setError('')
    setResponse(null)
    setRevealedStage(0)
    try {
      const sessionId = `console-trace-${Date.now()}`
      // mock 模式：api.ts 会按 session_id 匹配样例
      const fullSessionId = useCustom
        ? sessionId
        : `${sessionId}-${selectedSampleId}`

      const res = await fetchChat({
        session_id: fullSessionId,
        current_message: inputText,
      })
      setResponse(res)
      // 自动揭示 F1
      setRevealedStage(1)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const revealNext = () =>
    setRevealedStage((s) => Math.min(s + 1, 4) as Stage)

  return (
    <div className={styles.view}>
      {/* ── 样例选择器 ── */}
      <section className={styles.selector}>
        <div className={styles.selectorRow}>
          <label className={styles.selectorLabel}>
            <input
              type="radio"
              checked={!useCustom}
              onChange={() => setUseCustom(false)}
            />
            选择样例
          </label>
          {!useCustom && (
            <select
              className={styles.sampleSelect}
              value={selectedSampleId}
              onChange={(e) => setSelectedSampleId(e.target.value)}
            >
              {MOCK_SAMPLES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} · {s.label}
                </option>
              ))}
            </select>
          )}

          <label className={styles.selectorLabel}>
            <input
              type="radio"
              checked={useCustom}
              onChange={() => setUseCustom(true)}
            />
            自定义输入
            {MODE === 'live' ? '（Live 模式）' : '（需 Live 模式生效）'}
          </label>
        </div>

        {useCustom && (
          <textarea
            className={styles.customInput}
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="输入学生倾诉内容……"
            rows={3}
          />
        )}
      </section>

      {/* ── 学生输入 ── */}
      <div className={styles.inputBlock}>
        <span className={styles.inputLabel}>学生输入</span>
        <p className={styles.inputText}>{inputText || '—'}</p>
      </div>

      {/* ── 运行按钮 ── */}
      <button
        className={styles.runBtn}
        onClick={handleRun}
        disabled={loading || !inputText.trim()}
      >
        {loading ? '分析中…' : '▶ 运行 Pipeline'}
      </button>
      {error && <p className={styles.error}>{error}</p>}

      {/* ── F1–F4 分步揭示 ── */}
      {response && (
        <div className={styles.pipeline}>
          {/* F1 安全门 */}
          <StageCard
            stage="F1"
            revealed={revealedStage >= 1}
            onReveal={() => setRevealedStage(1)}
          >
            <div className={styles.f1Content}>
              <div className={`${styles.riskBadge} ${styles[`risk_${response.risk_level}`]}`}>
                {response.risk_level.toUpperCase()}
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldKey}>status</span>
                <code className={styles.fieldVal}>{response.status}</code>
              </div>
            </div>
          </StageCard>

          {revealedStage >= 1 && revealedStage < 2 && (
            <button className={styles.nextBtn} onClick={revealNext}>
              展开 F2 情境识别 →
            </button>
          )}

          {/* F2 情境识别 */}
          <StageCard
            stage="F2"
            revealed={revealedStage >= 2}
            onReveal={revealNext}
          >
            <div className={styles.f2Content}>
              <div className={styles.fieldRow}>
                <span className={styles.fieldKey}>scenario</span>
                <span className={styles.scenarioBadge}>{response.scenario ?? '—'}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldKey}>activated_casel</span>
                <div className={styles.caselList}>
                  {response.activated_casel.length === 0 ? (
                    <span className={styles.fieldVal}>—</span>
                  ) : (
                    response.activated_casel.map((c) => (
                      <span key={c} className={styles.caselTag}>{c}</span>
                    ))
                  )}
                </div>
              </div>
            </div>
          </StageCard>

          {revealedStage >= 2 && revealedStage < 3 && (
            <button className={styles.nextBtn} onClick={revealNext}>
              展开 F3 双候选 →
            </button>
          )}

          {/* F3 双候选 */}
          <StageCard
            stage="F3"
            revealed={revealedStage >= 3}
            onReveal={revealNext}
          >
            <div className={styles.candidatesGrid}>
              {response.candidates.map((c) => (
                <CandidateCard
                  key={c.candidate_id}
                  candidate={c}
                  isBest={c.candidate_id === response.best_candidate_id}
                />
              ))}
              {response.candidates.length === 0 && (
                <p className={styles.empty}>blocked_by_safety — 无候选生成</p>
              )}
            </div>
          </StageCard>

          {revealedStage >= 3 && revealedStage < 4 && (
            <button className={styles.nextBtn} onClick={revealNext}>
              展开 F4 打分择优 →
            </button>
          )}

          {/* F4 打分择优 */}
          <StageCard
            stage="F4"
            revealed={revealedStage >= 4}
            onReveal={revealNext}
          >
            {response.scores.length > 0 ? (
              <ScoreTable
                scores={response.scores}
                bestCandidateId={response.best_candidate_id}
                winnerId={response.preference_pair?.winner_id}
                loserId={response.preference_pair?.loser_id}
              />
            ) : (
              <p className={styles.empty}>无评分数据（safety 拦截）</p>
            )}

            {response.preference_pair && (
              <div className={styles.prefPair}>
                <span className={styles.prefLabel}>preference_pair →</span>
                <span>winner: <strong>{response.preference_pair.winner_id}</strong></span>
                <span>loser: <strong>{response.preference_pair.loser_id}</strong></span>
                <span className={styles.prefNote}>→ DPO 训练料</span>
              </div>
            )}
          </StageCard>

          {/* ── 学生最终收到的内容（闭环）── */}
          {revealedStage >= 4 && (
            <div className={styles.outputBlock}>
              <span className={styles.outputLabel}>学生最终收到</span>
              <p className={styles.outputText}>{response.reply_text}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
