// ============================================================
// BatchOverviewView — 45 样本批量验收总览
// 规格: §6.1 批量总览 · §6.2 数据来源
// 数据: raw_results.json（前端聚合）+ 回退至已知真实数字
// ============================================================
import { useEffect } from 'react'
import { useConsoleData } from '../../hooks/useConsoleData'
import { MetricCard } from './MetricCard'
import styles from './BatchOverviewView.module.css'

export function BatchOverviewView() {
  const { batchSummary, batchLoading, loadBatchSummary } = useConsoleData()

  useEffect(() => {
    loadBatchSummary()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (batchLoading) {
    return <div className={styles.loading}>加载批量数据…</div>
  }

  if (!batchSummary) return null

  const s = batchSummary

  return (
    <div className={styles.view}>
      <div className={styles.header}>
        <h2 className={styles.title}>批量验收总览</h2>
        <span className={styles.runTag}>real-llm-20260522-215717</span>
        {!s.rawLoaded && (
          <span className={styles.fallbackNote}>
            ⚠ JSON 未加载，显示已知验收数字（非实时计算）
          </span>
        )}
      </div>

      {/* ── 四个 KPI 卡片（依 fig3 布局）── */}
      <div className={styles.metricsRow}>
        <MetricCard
          value={`${s.scenarioAccuracy}%`}
          label="情境准确率"
          sub={`${s.requestOk} / ${s.totalRuns} 正确`}
        />
        <MetricCard
          value={`${s.requestOk}/${s.totalRuns}`}
          label="链路成功"
          sub="request_ok"
        />
        <MetricCard
          value={s.preferencePairsCount}
          label="偏好对 → DPO"
          sub="preference_pairs 落库"
        />
        <MetricCard
          value={s.boundaryInterceptions}
          label="边界拦截"
          sub="boundary_flag=true"
          accent={true}
        />
      </div>

      {/* ── 分情境准确率 ── */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>分情境准确率</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>情境</th>
              <th>正确数</th>
              <th>总数</th>
              <th>准确率</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(s.scenarioBreakdown).map(([sc, v]) => {
              const rate = v.total > 0
                ? ((v.correct / v.total) * 100).toFixed(1)
                : '—'
              return (
                <tr key={sc}>
                  <td>{sc}</td>
                  <td>{v.correct}</td>
                  <td>{v.total}</td>
                  <td>
                    <span className={styles.rateBadge}>{rate}%</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      {/* ── 落库校验 ── */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>落库校验</h3>
        <div className={styles.dbGrid}>
          {Object.entries(s.dbChecks).map(([key, val]) => (
            <div key={key} className={styles.dbCard}>
              <span className={styles.dbVal}>{val}</span>
              <span className={styles.dbKey}>{key}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── 已知缺陷记录 ── */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>已知缺陷闭环</h3>
        <table className={styles.defectTable}>
          <thead>
            <tr>
              <th>样本</th>
              <th>问题</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>syn_0012</td>
              <td>F3 内部提示外泄（system prompt 出现在回复中）</td>
              <td><span className={styles.fixed}>已修复</span></td>
            </tr>
            <tr>
              <td>syn_0032</td>
              <td>F3 事实编造（地名细节不实）</td>
              <td><span className={styles.fixed}>已修复</span></td>
            </tr>
            <tr>
              <td>亲子/同伴情境</td>
              <td>第三方动机推测残留（「也许她是…」）</td>
              <td><span className={styles.limitation}>Limitation</span></td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* TODO：后端聚合端点就绪后切换 */}
      <p className={styles.todo}>
        TODO: 后端聚合端点 <code>GET /console/runs/&#123;run_id&#125;/summary</code> 就绪后
        切换至实时接口（当前前端聚合）
      </p>
    </div>
  )
}
