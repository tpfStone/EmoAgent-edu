import type { CandidateScore, PreferencePair } from "@emoedu/shared/console";
import styles from "./ScoreMatrix.module.css";

interface ScoreMatrixProps {
  emptyReason?: string;
  preferencePair: PreferencePair | null;
  scores: CandidateScore[];
}

function formatScore(value: number) {
  return value.toFixed(2);
}

function caselAverage(score: CandidateScore) {
  const values = Object.values(score.casel);
  if (values.length === 0) {
    return "—";
  }

  const total = values.reduce((sum, value) => sum + value, 0);
  return formatScore(total / values.length);
}

function preferenceMarker(candidateId: string, preferencePair: PreferencePair | null) {
  if (candidateId === preferencePair?.winner_id) {
    return "winner";
  }

  if (candidateId === preferencePair?.loser_id) {
    return "loser";
  }

  return "—";
}

export function ScoreMatrix({
  emptyReason = "安全门拦截后没有进入候选评分。",
  preferencePair,
  scores,
}: ScoreMatrixProps) {
  if (scores.length === 0) {
    return (
      <div className={styles.empty}>
        {emptyReason}
      </div>
    );
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.matrix}>
        <thead>
          <tr>
            <th>candidate</th>
            <th>ER</th>
            <th>IP</th>
            <th>EX</th>
            <th>CASEL average</th>
            <th>boundary_flag</th>
            <th>weighted_total</th>
            <th>preference</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((score) => {
            const isBoundary = score.boundary_flag === true;
            const isWinner =
              !isBoundary && score.candidate_id === preferencePair?.winner_id;

            return (
              <tr
                className={isWinner ? styles.winnerRow : undefined}
                key={score.candidate_id}
              >
                <th scope="row">{score.candidate_id}</th>
                <td>{score.epitome.ER}</td>
                <td>{score.epitome.IP}</td>
                <td>{score.epitome.EX}</td>
                <td>{caselAverage(score)}</td>
                <td>{String(score.boundary_flag)}</td>
                <td className={isBoundary ? styles.disqualifiedTotal : undefined}>
                  {formatScore(score.weighted_total)}
                </td>
                <td>{preferenceMarker(score.candidate_id, preferencePair)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
