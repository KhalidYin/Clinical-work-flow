import { useEffect } from "react";

export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = `${title} · 临床知识台账`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
