import styles from "./shared.module.css";

interface StatePanelProps {
  symbol: string;
  title: string;
  text: string;
  error?: boolean;
}

export function StatePanel({ symbol, title, text, error = false }: StatePanelProps) {
  return (
    <div className={`${styles.statePanel} ${error ? styles.error : ""}`} role="status">
      <div>
        <span className={styles.stateSymbol} aria-hidden="true">
          {symbol}
        </span>
        <h2 className={styles.stateTitle}>{title}</h2>
        <p className={styles.stateText}>{text}</p>
      </div>
    </div>
  );
}
