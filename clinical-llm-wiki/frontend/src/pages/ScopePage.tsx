import styles from "./pages.module.css";

interface ScopePageProps {
  eyebrow: string;
  title: string;
  description: string;
  phase: string;
}

export function ScopePage({ eyebrow, title, description, phase }: ScopePageProps) {
  return (
    <section className={styles.page} aria-labelledby="scope-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 className={styles.title} id="scope-title">
            {title}
          </h1>
          <p className={styles.lede}>{description}</p>
        </div>
      </header>
      <div className={styles.panel}>
        <div className={styles.scopePanel}>
          <div>
            <span className={styles.stateSymbol} aria-hidden="true">
              §
            </span>
            <h2 className={styles.stateTitle}>契约已预留</h2>
            <p className={styles.stateText}>
              此一级页面属于已批准信息架构，但当前 P1 切片没有声明真实数据来源。页面明确保持范围状态，不展示伪造指标。
            </p>
            <span className={styles.scopeMeta}>{phase}</span>
          </div>
        </div>
      </div>
    </section>
  );
}
