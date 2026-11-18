import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

export const POLL_MS = 2000;

export interface Polled<T> {
  data: T | undefined;
  failed: boolean;
  reload: () => void;
}

/** Fetch a path now and, unless poll is false, every two seconds after. */
export function usePolling<T>(path: string, poll = true): Polled<T> {
  const [data, setData] = useState<T>();
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    let active = true;
    const load = () => {
      getJson<T>(path)
        .then((value) => {
          if (!active) return;
          setData(value);
          setFailed(false);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    };
    load();
    const timer = poll ? setInterval(load, POLL_MS) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path, poll, version]);

  return { data, failed, reload };
}
