import styles from "./ReferralPanel.module.css";

interface ReferralPanelProps {
  riskLevel: string;
  onDismiss?: () => void;
}

interface SupportResourceHintProps {
  onExpand: () => void;
}

export function ReferralPanel({ riskLevel, onDismiss }: ReferralPanelProps) {
  const showEmergency = riskLevel === "red";
  const showDismiss = riskLevel === "yellow" && onDismiss;

  return (
    <section className={styles.panel} aria-label="支持资源">
      <div className={styles.copy}>
        <div className={styles.header}>
          <h2>我注意到你可能需要更多支持</h2>
          {showDismiss ? (
            <button
              aria-label="关闭支持提示"
              className={styles.dismissButton}
              type="button"
              onClick={onDismiss}
            >
              <span aria-hidden="true">×</span>
            </button>
          ) : null}
        </div>
        <p>你愿意说出来，很勇敢。</p>
        <p>现在，请联系一位你信任的大人，让他或她陪你一起处理。</p>
      </div>

      <div className={styles.hotlines} aria-label="热线电话">
        <a href="tel:12356">
          <span>心理援助热线</span>
          <strong>12356</strong>
        </a>
        <a href="tel:12355">
          <span>青少年服务台</span>
          <strong>12355</strong>
        </a>
        {showEmergency ? (
          <>
            <a className={styles.emergency} href="tel:120">
              <span>急救</span>
              <strong>120</strong>
            </a>
            <a className={styles.emergency} href="tel:110">
              <span>警察</span>
              <strong>110</strong>
            </a>
          </>
        ) : null}
      </div>
    </section>
  );
}

export function SupportResourceHint({ onExpand }: SupportResourceHintProps) {
  return (
    <section className={styles.hint} aria-label="支持资源入口">
      <span>需要支持时，可以查看资源</span>
      <button type="button" onClick={onExpand}>
        查看资源
      </button>
    </section>
  );
}
