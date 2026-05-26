import styles from "./BatchEvidence.module.css";

const summaryRows = [
  { label: "request/link success", value: "45/45" },
  { label: "scenario accuracy", value: "43/45", note: "95.6%" },
  { label: "turns", value: "45" },
  { label: "messages", value: "90" },
  { label: "candidates", value: "90" },
  { label: "preference_pairs", value: "43" },
];

const defectRows = [
  {
    id: "syn_0012",
    issue: "场景识别偏差",
    note: "需要人工复核样本上下文与标签边界。",
  },
  {
    id: "syn_0032",
    issue: "候选边界出局",
    note: "syn_0032_c2 因事实编造触发 boundary_flag。",
  },
  {
    id: "third-party motive limitation",
    issue: "第三方动机限制",
    note: "对家长、同伴等第三方意图保持保守表述。",
  },
];

export function BatchEvidence() {
  return (
    <div className={styles.batch}>
      <header className={styles.header}>
        <p className={styles.kicker}>Batch evidence</p>
        <h2>验收摘要</h2>
        <p>来源：real-llm-20260522-215717 验收摘要；非实时计算</p>
      </header>

      <section className={styles.metrics} aria-label="Acceptance summary metrics">
        {summaryRows.map((row) => (
          <article className={styles.metric} key={row.label}>
            <p>{row.label}</p>
            <strong>{row.value}</strong>
            {row.note ? <span>{row.note}</span> : null}
          </article>
        ))}
      </section>

      <section className={styles.defects} aria-label="Defect rows">
        <h3>缺陷行</h3>
        <div className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                <th>row</th>
                <th>issue</th>
                <th>note</th>
              </tr>
            </thead>
            <tbody>
              {defectRows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.id}</th>
                  <td>{row.issue}</td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
