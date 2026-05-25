// ============================================================
// FrameworkAlignView — 框架对标（静态内容）
// 规格: §6.1 C-SSRS / EPITOME / CASEL 三块
// 颜色：依 ux-fig3-console-ia.svg 精确值
// ============================================================
import { FrameworkBox } from './FrameworkBox'
import styles from './FrameworkAlignView.module.css'

export function FrameworkAlignView() {
  return (
    <div className={styles.view}>
      <h2 className={styles.title}>框架对标</h2>
      <p className={styles.desc}>
        EmoAgent 的评估框架对应三个已验证量表。以下为各框架的核心维度与本系统实现的对应关系。
      </p>

      <div className={styles.frameworkRow}>
        {/* ── C-SSRS ── */}
        <FrameworkBox
          title="C-SSRS"
          subtitle="Columbia Suicide Severity Rating Scale"
          colorVar="--cssrs-green"
        >
          <p className={styles.para}>
            F1 安全门将每条倾诉分为三级风险：
          </p>
          <div className={styles.levelList}>
            <div className={styles.levelRow}>
              <span className={styles.level} style={{ background: '#d4edda', color: '#155724' }}>
                green
              </span>
              <span>无危机信号，正常进入 F2–F4 对话生成</span>
            </div>
            <div className={styles.levelRow}>
              <span className={styles.level} style={{ background: '#fff3cd', color: '#856404' }}>
                yellow
              </span>
              <span>检测到情绪困扰信号，F1 渲染 reply_text 后触发转介面板，输入锁定</span>
            </div>
            <div className={styles.levelRow}>
              <span className={styles.level} style={{ background: '#f8d7da', color: '#721c24' }}>
                red
              </span>
              <span>
                检测到明确危机词汇（自杀/自残/不想活等），
                立即拦截并呈现含 120/110 的紧急转介
              </span>
            </div>
          </div>
          <p className={styles.note}>
            F1 异常时 orchestrator 保守回退至 yellow 转介而非 green，
            避免漏判。
          </p>
        </FrameworkBox>

        {/* ── EPITOME ── */}
        <FrameworkBox
          title="EPITOME"
          subtitle="Empathy Process in Text Online Measurement"
          colorVar="--epitome-blue"
        >
          <p className={styles.para}>
            F4 Critic 使用 EPITOME 三维度对每条候选回应打 0/1/2 分：
          </p>
          <div className={styles.dimList}>
            <div className={styles.dimRow}>
              <span className={styles.dimTag}>ER</span>
              <div>
                <strong>Emotional Response</strong> — 情感回应
                <p className={styles.dimDesc}>
                  识别并回应对方的情绪状态；0=无回应，1=浅层识别，2=深层共情
                </p>
              </div>
            </div>
            <div className={styles.dimRow}>
              <span className={`${styles.dimTag} ${styles.dimWarning}`}>IP *</span>
              <div>
                <strong>Interpersonal Process</strong> — 人际过程
                <p className={styles.dimDesc}>
                  回应与倾诉者的人际关系脉络是否对齐；0=无，1=部分，2=充分
                </p>
              </div>
            </div>
            <div className={styles.dimRow}>
              <span className={styles.dimTag}>EX</span>
              <div>
                <strong>Exploration</strong> — 探索引导
                <p className={styles.dimDesc}>
                  是否帮助倾诉者探索感受/视角；0=无，1=浅层，2=深度探索
                </p>
              </div>
            </div>
          </div>
          <div className={styles.limitation}>
            <strong>⚠ IP 可靠性局限（Limitation）：</strong>
            原 EPITOME 论文（Kumar &amp; Groh, 2025）中 ER/IP 操作定义不清，
            专家评分者间 κ 偏低，仅 EX 维κ达到 substantial 以上。
            本系统针对中学生场景补充了中文操作定义以缓解此问题，
            残余局限在论文 limitation 节中如实讨论。
          </div>
        </FrameworkBox>

        {/* ── CASEL ── */}
        <FrameworkBox
          title="CASEL"
          subtitle="Collaborative for Academic, Social, and Emotional Learning"
          colorVar="--casel-gold"
        >
          <p className={styles.para}>
            F2 情境识别激活与当前倾诉匹配的 CASEL 维度，F4 按激活维度评分：
          </p>
          <div className={styles.caselList}>
            {CASEL_DIMS.map((d) => (
              <div key={d.key} className={styles.caselRow}>
                <span className={styles.caselTag}>{d.label}</span>
                <div>
                  <div className={styles.caselName}>{d.key}</div>
                  <div className={styles.caselDesc}>{d.desc}</div>
                  <div className={styles.caselScenario}>
                    典型情境：{d.scenarios.join('、')}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className={styles.note}>
            激活逻辑：F2 通过 Q-matrix 查表，按 scenario 动态激活 1–3 个维度，
            F4 仅对激活维度评分，非全维度强制打分。
          </p>
        </FrameworkBox>
      </div>
    </div>
  )
}

const CASEL_DIMS = [
  {
    key: '自我觉察引导',
    label: 'SA',
    desc: '帮助学生识别并命名自身情绪',
    scenarios: ['学业压力', '同伴关系', '亲子摩擦'],
  },
  {
    key: '自我管理引导',
    label: 'SM',
    desc: '引导情绪调节与冲动管理',
    scenarios: ['学业压力', '外放型倾诉'],
  },
  {
    key: '社会觉察引导',
    label: 'SOA',
    desc: '帮助理解他人视角（不替第三方归因）',
    scenarios: ['同伴关系', '亲子摩擦'],
  },
  {
    key: '人际关系引导',
    label: 'RS',
    desc: '支持健康人际互动与沟通',
    scenarios: ['同伴关系', '亲子摩擦'],
  },
  {
    key: '负责任决策引导',
    label: 'RD',
    desc: '引导识别可行的下一步行动',
    scenarios: ['学业压力', '亲子摩擦'],
  },
]
