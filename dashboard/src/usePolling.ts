import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

export const POLL_MS = 2000;

export interface Polled<T> {
  data: T | undefined;
  failed: boolean;
  reload: () => void;
}

/** Fetch a path now and every two seconds, so the page stays current. */
export function usePolling<T>(path: string): Polled<T> {
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
    const timer = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path, version]);

  return { data, failed, reload };
}
