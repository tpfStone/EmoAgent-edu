import styles from "./FrameworkMap.module.css";

const cssrsRows = [
  {
    level: "green",
    mapping: "无自伤意念或计划，进入常规情境与 CASEL 路由。",
  },
  {
    level: "yellow",
    mapping: "存在显著痛苦或风险线索，回复保持支持性并建议可信成人介入。",
  },
  {
    level: "red",
    mapping: "出现明确自伤、自杀、工具或计划线索，F1 直接拦截并输出安全指引。",
  },
];

const epitomeRows = [
  { code: "ER", label: "Emotional Reaction", note: "承接、命名并降低情绪强度。" },
  { code: "IP", label: "Interpretation", note: "帮助澄清情境含义；IP 对第三方动机推断可靠性较弱。" },
  { code: "EX", label: "Exploration", note: "引导下一步表达、求助或低风险行动。" },
];

const caselRows = [
  { dimension: "自我觉察", scenarios: "学业压力、亲子摩擦" },
  { dimension: "自我管理", scenarios: "学业压力、危机前稳定" },
  { dimension: "社会觉察", scenarios: "同伴关系、被排斥体验" },
  { dimension: "关系技能", scenarios: "同伴关系、亲子沟通" },
  { dimension: "负责任决策", scenarios: "求助、边界、低风险行动选择" },
];

export function FrameworkMap() {
  return (
    <div className={styles.framework}>
      <header className={styles.header}>
        <p className={styles.kicker}>Framework map</p>
        <h2>安全、EPITOME 与 CASEL 对标</h2>
      </header>

      <section className={styles.band}>
        <div className={styles.sectionTitle}>
          <h3>C-SSRS 风险映射</h3>
          <p>F1 使用保守兜底：只要风险线索不清晰但可能升级，优先降低建议强度并转向可信成人/专业支持。</p>
        </div>
        <div className={styles.levels}>
          {cssrsRows.map((row) => (
            <article className={styles.level} key={row.level}>
              <strong className={styles[row.level]}>{row.level}</strong>
              <p>{row.mapping}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.band}>
        <div className={styles.sectionTitle}>
          <h3>EPITOME Critic</h3>
          <p>评分只用于候选比较，不覆盖安全门；boundary_flag 优先级高于加权分。</p>
        </div>
        <div className={styles.definitionGrid}>
          {epitomeRows.map((row) => (
            <article className={styles.definition} key={row.code}>
              <strong>{row.code}</strong>
              <span>{row.label}</span>
              <p>{row.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.band}>
        <div className={styles.sectionTitle}>
          <h3>CASEL 情境映射</h3>
          <p>维度用于解释情境目标，避免把学生问题简化成单一分数。</p>
        </div>
        <div className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                <th>dimension</th>
                <th>scenario mapping</th>
              </tr>
            </thead>
            <tbody>
              {caselRows.map((row) => (
                <tr key={row.dimension}>
                  <th scope="row">{row.dimension}</th>
                  <td>{row.scenarios}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
