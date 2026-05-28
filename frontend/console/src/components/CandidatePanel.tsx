import type {
  CandidateScore,
  GeneratorCandidate,
  PreferencePair,
} from "@emoedu/shared/console";
import styles from "./CandidatePanel.module.css";

interface CandidatePanelProps {
  bestCandidateId: string | null;
  candidates: GeneratorCandidate[];
  preferencePair: PreferencePair | null;
  scores: CandidateScore[];
}

function getScoreForCandidate(scores: CandidateScore[], candidateId: string) {
  return scores.find((score) => score.candidate_id === candidateId);
}

export function CandidatePanel({
  bestCandidateId,
  candidates,
  preferencePair,
  scores,
}: CandidatePanelProps) {
  if (candidates.length === 0) {
    return (
      <div className={styles.empty}>
        安全门已拦截，本轮未生成候选回复。
      </div>
    );
  }

  return (
    <div className={styles.grid}>
      {candidates.map((candidate) => {
        const score = getScoreForCandidate(scores, candidate.candidate_id);
        const isBoundary = score?.boundary_flag === true;
        const isWinner =
          !isBoundary &&
          (candidate.candidate_id === preferencePair?.winner_id ||
            candidate.candidate_id === bestCandidateId);

        return (
          <article
            className={isBoundary ? styles.boundaryCandidate : styles.candidate}
            key={candidate.candidate_id}
          >
            <header className={styles.header}>
              <div>
                <p className={styles.id}>{candidate.candidate_id}</p>
                <h3>{candidate.orientation}</h3>
              </div>
              <div className={styles.markers}>
                {isWinner ? <span className={styles.winner}>胜出</span> : null}
                {isBoundary ? <span className={styles.boundary}>出局</span> : null}
              </div>
            </header>
            <p className={styles.text}>{candidate.text}</p>
            {isBoundary ? (
              <p className={styles.reason}>边界原因：{score?.boundary_reason || "未标注"}</p>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
