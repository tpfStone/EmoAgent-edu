import styles from "./ReferralPanel.module.css";

interface ReferralPanelProps {
  riskLevel: string;
}

export function ReferralPanel({ riskLevel }: ReferralPanelProps) {
  const showEmergency = riskLevel === "red";

  return (
    <section className={styles.panel} aria-label="支持资源">
      <div className={styles.copy}>
        <h2>我注意到你可能需要更多支持</h2>
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
