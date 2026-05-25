// ============================================================
// ScoreTable — F4 EPITOME/CASEL 打分表
// boundary_flag=true 的候选显示「出局」标记 + weighted_total 划除
// ============================================================
import type { CandidateScore } from '@emoedu/shared'
import styles from './ScoreTable.module.css'

interface Props {
  scores: CandidateScore[]
  bestCandidateId: string | null
  winnerId?: string
  loserId?: string
}

export function ScoreTable({ scores, bestCandidateId, winnerId, loserId }: Props) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>候选</th>
            <th title="Emotional Response">ER</th>
            <th title="Interpersonal Process — 可靠性偏低¹">IP *</th>
            <th title="Exploration">EX</th>
            <th>CASEL 均分</th>
            <th>Boundary</th>
            <th>加权总分</th>
            <th>偏好对</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((s) => {
            const blocked = s.boundary_flag
            const caselAvg =
              Object.values(s.casel).length > 0
                ? (
                    Object.values(s.casel).reduce((a, b) => a + b, 0) /
                    Object.values(s.casel).length
                  ).toFixed(2)
                : '—'

            return (
              <tr
                key={s.candidate_id}
                className={`
                  ${blocked ? styles.blocked : ''}
                  ${s.candidate_id === bestCandidateId && !blocked ? styles.best : ''}
                `}
              >
                <td className={styles.cidCell}>
                  <span className={styles.cid}>{s.candidate_id}</span>
                  {blocked && (
                    <span className={styles.blockedBadge}>出局</span>
                  )}
                </td>
                <td>{s.epitome.ER}</td>
                <td>{s.epitome.IP}</td>
                <td>{s.epitome.EX}</td>
                <td>{caselAvg}</td>
                <td>
                  {blocked ? (
                    <span className={styles.flagTrue}>
                      ✗ {s.boundary_reason || '触发边界'}
                    </span>
                  ) : (
                    <span className={styles.flagFalse}>—</span>
                  )}
                </td>
                {/* boundary=true 时 weighted_total 划除 */}
                <td className={blocked ? styles.strikethrough : ''}>
                  {s.weighted_total.toFixed(2)}
                </td>
                <td>
                  {s.candidate_id === winnerId && (
                    <span className={styles.winner}>W</span>
                  )}
                  {s.candidate_id === loserId && (
                    <span className={styles.loser}>L</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* EPITOME IP 可靠性 limitation 标注（规格 §6.1 要求）*/}
      <p className={styles.limitation}>
        * IP（人际过程）维度：原 EPITOME 论文（Kumar &amp; Groh, 2025）中
        ER/IP 操作定义不清，专家评分者间可靠性偏低；仅 EX 维κ较高。
        本系统针对中学生场景补充了中文操作定义以缓解此问题，但残余局限在论文 limitation
        节中如实讨论。
      </p>

      {/* rationale 详情 */}
      {scores.map((s) =>
        s.rationale ? (
          <details key={s.candidate_id} className={styles.rationale}>
            <summary>
              {s.candidate_id} 评分依据
            </summary>
            <p>{s.rationale}</p>
          </details>
        ) : null
      )}
    </div>
  )
}
