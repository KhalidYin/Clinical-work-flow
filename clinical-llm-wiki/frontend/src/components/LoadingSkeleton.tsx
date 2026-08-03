import styles from "./shared.module.css";

export function LoadingSkeleton({ rows = 3, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className={styles.tableWrap} aria-label="正在加载" aria-busy="true">
      <table className={styles.table}>
        <tbody>
          {Array.from({ length: rows }, (_, row) => (
            <tr key={row}>
              {Array.from({ length: cols }, (_, cell) => (
                <td key={cell}>
                  <span className={styles.skeleton} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
