import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <main
          style={{
            display: "grid",
            minHeight: "100vh",
            placeItems: "center",
            padding: "32px",
            fontFamily: "var(--sans, sans-serif)",
            color: "var(--ink-900, #192b26)",
            background: "var(--paper-100, #f4f1e8)",
          }}
        >
          <div style={{ maxWidth: 520, textAlign: "center" }}>
            <div
              style={{
                width: 48,
                height: 48,
                margin: "0 auto 16px",
                display: "grid",
                placeItems: "center",
                color: "var(--red-700, #a6402a)",
                background: "var(--red-100, #f3ded7)",
                border: "1px solid rgba(166,64,42,0.2)",
                borderRadius: "50%",
                fontFamily: "var(--serif, serif)",
                fontSize: 24,
              }}
              aria-hidden="true"
            >
              !
            </div>
            <h1
              style={{
                fontFamily: "var(--serif, serif)",
                fontSize: "clamp(24px, 4vw, 36px)",
                margin: "0 0 8px",
              }}
            >
              页面发生未预期的错误
            </h1>
            <p
              style={{
                color: "var(--ink-700, #3d534b)",
                margin: "0 0 20px",
                lineHeight: 1.6,
              }}
            >
              组件渲染过程中发生了异常。这通常是数据格式或网络响应异常导致的，不会影响已保存的数据。
            </p>
            <button
              type="button"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              style={{
                minHeight: 40,
                padding: "10px 18px",
                color: "var(--white, #fffef9)",
                background: "var(--blue-700, #1f5c78)",
                border: "1px solid var(--blue-700, #1f5c78)",
                borderRadius: 2,
                cursor: "pointer",
                fontFamily: "var(--mono, monospace)",
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              重新加载页面
            </button>
            {this.state.error ? (
              <pre
                style={{
                  marginTop: 20,
                  padding: 12,
                  color: "var(--ink-500, #6e7e76)",
                  background: "var(--paper-200, #eae5d8)",
                  border: "1px solid var(--paper-300, #d9d1c0)",
                  fontFamily: "var(--mono, monospace)",
                  fontSize: 9,
                  textAlign: "left",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                }}
              >
                {this.state.error.message}
              </pre>
            ) : null}
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
