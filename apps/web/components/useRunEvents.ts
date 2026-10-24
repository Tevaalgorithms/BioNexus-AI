"use client";
import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "@/lib/types";
import { call } from "./useApi";

const KINDS = ["stage.completed", "agent.handoff", "run.status"];

/** Live run events: server-sent events with replay, falling back to polling. */
export function useRunEvents(runId: string, onStatus: () => void) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [mode, setMode] = useState<"live" | "polling">("live");
  const last = useRef(0);

  useEffect(() => {
    let ended = false;
    let timer: ReturnType<typeof setInterval> | undefined;
    const add = (event: RunEvent) => {
      if (event.seq <= last.current) return;
      last.current = event.seq;
      setEvents((prev) => [...prev, event]);
      if (event.kind === "run.status") onStatus();
    };
    const source = new EventSource(`/api/proxy/investigations/${runId}/events/stream`);
    for (const kind of KINDS) {
      source.addEventListener(kind, (e) => {
        const m = e as MessageEvent;
        add({ seq: Number(m.lastEventId), kind, data: JSON.parse(m.data) });
      });
    }
    source.addEventListener("end", () => { ended = true; source.close(); });
    source.onerror = () => {
      source.close();
      if (ended) return;
      setMode("polling");
      timer = setInterval(async () => {
        const fresh = await call<RunEvent[]>("GET", `investigations/${runId}/events?after=${last.current}`).catch(() => []);
        fresh.forEach(add);
      }, 3000);
    };
    return () => { source.close(); if (timer) clearInterval(timer); };
  }, [runId, onStatus]);

  return { events, mode };
}
