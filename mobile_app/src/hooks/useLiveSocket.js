import { useEffect, useRef } from 'react';

export default function useLiveSocket(url, onMessage) {
  const wsRef = useRef(null);

  useEffect(() => {
    if (!url) return undefined;

    let retryTimer;

    const connect = () => {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log('Mobile live socket connected');
      };

      wsRef.current.onmessage = (event) => {
        try {
          onMessage?.(JSON.parse(event.data));
        } catch {
          onMessage?.({ raw: event.data });
        }
      };

      wsRef.current.onclose = () => {
        retryTimer = setTimeout(connect, 2500);
      };
    };

    connect();

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, [url, onMessage]);

  return wsRef;
}
