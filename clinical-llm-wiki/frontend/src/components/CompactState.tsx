import styles from "./shared.module.css";

interface CompactStateProps {
  title: string;
  text: string;
  error?: boolean;
  loading?: boolean;
}

export function CompactState({ title, text, error = false, loading = false }: CompactStateProps) {
  return (
    <div
      className={`${styles.compactState} ${error ? styles.error : ""}`}
      role={error ? "alert" : "status"}
      aria-label={title}
      aria-busy={loading || undefined}
    >
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}
