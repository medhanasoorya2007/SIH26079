"use client";

import { useEffect, useRef, useState } from "react";

export interface ApiState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/** Minimal data hook: refetches when `key` changes, ignores stale responses. */
export function useApi<T>(key: string | null, fetcher: () => Promise<T>): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: undefined, error: undefined, loading: key !== null });
  const seq = useRef(0);
  useEffect(() => {
    if (key === null) return;
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    fetcher()
      .then((data) => id === seq.current && setState({ data, error: undefined, loading: false }))
      .catch((error: Error) => id === seq.current && setState((s) => ({ ...s, error, loading: false })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
