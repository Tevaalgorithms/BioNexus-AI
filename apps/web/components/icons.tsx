import { ReactElement } from "react";

/** A small inline icon set (stroke icons). Decorative by default; pass `label` to expose one. */
const PATHS: Record<string, ReactElement> = {
  logo: <><circle cx="6" cy="7" r="2.4" /><circle cx="18" cy="6" r="2.4" /><circle cx="12" cy="18" r="2.4" /><path d="M8 8l3 8M16 8l-3 8M8.4 7h7.2" /></>,
  home: <path d="M3 11l9-7 9 7M5 10v10h14V10" />,
  plus: <path d="M12 5v14M5 12h14" />,
  review: <><path d="M9 11l2 2 4-4" /><rect x="4" y="3" width="16" height="18" rx="2" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4 4-6 8-6s7 2 8 6" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 114 2c-1 .8-1.5 1.200-1.500 2.500M12 17h.01" /></>,
  dna: <path d="M7 3c0 6 10 6 10 12M17 3c0 6-10 6-10 12M7 21c0-3 3-4 5-5M17 21c0-3-3-4-5-5M9 7h6M9 17h6" />,
  book: <path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 21h15" />,
  path: <><circle cx="5" cy="6" r="2" /><circle cx="19" cy="12" r="2" /><circle cx="5" cy="18" r="2" /><path d="M7 6h6a4 4 0 014 4M7 18h6a4 4 0 004-4" /></>,
  flask: <path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3M8 15h8" />,
  scale: <path d="M12 3v18M5 7h14M5 7l-3 7a3 3 0 006 0L5 7zM19 7l-3 7a3 3 0 006 0l-3-7z" />,
  pen: <path d="M4 20l4-1 11-11a2.100 2.100 0 00-3-3L5 16l-1 4z" />,
  compass: <><circle cx="12" cy="12" r="9" /><path d="M15.500 8.500l-2 5-5 2 2-5 5-2z" /></>,
  search: <><circle cx="11" cy="11" r="6" /><path d="M20 20l-4-4" /></>,
  link: <path d="M10 14a4 4 0 005.500 0l3-3a4 4 0 00-5.500-5.500l-1 1M14 10a4 4 0 00-5.500 0l-3 3a4 4 0 005.500 5.500l1-1" />,
  check: <path d="M5 12l5 5 9-10" />,
  cross: <path d="M6 6l12 12M18 6L6 18" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  pause: <path d="M8 5v14M16 5v14" />,
  shield: <path d="M12 3l8 3v6c0 5-3.500 8-8 9-4.500-1-8-4-8-9V6l8-3zM9 12l2 2 4-4" />,
  lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></>,
  chart: <path d="M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3" />,
  coin: <><circle cx="12" cy="12" r="9" /><path d="M14.500 9.500c-.5-1-1.500-1.500-2.500-1.500-1.500 0-2.500.8-2.500 2s1 1.700 2.500 2 2.500.8 2.500 2-1 2-2.500 2c-1.200 0-2.200-.6-2.700-1.600M12 6.500v1.500m0 8v1.500" /></>,
  server: <><rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.500h.01M7 16.500h.01" /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3M10 10h4v4h-4z" /></>,
  sliders: <path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6" />,
  list: <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />,
  doc: <path d="M7 3h7l5 5v13H7V3zM14 3v5h5M10 13h6M10 17h6" />,
  download: <path d="M12 4v11m0 0l-4-4m4 4l4-4M5 20h14" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.500h.01" /></>,
  alert: <path d="M12 4l9 16H3L12 4zM12 10v4M12 17h.01" />,
  stop: <><circle cx="12" cy="12" r="9" /><path d="M9 9h6v6H9z" /></>,
  spark: <path d="M12 3l1.800 5.200L19 10l-5.200 1.800L12 17l-1.800-5.200L5 10l5.200-1.800L12 3z" />,
  graph: <><circle cx="6" cy="6" r="2" /><circle cx="18" cy="8" r="2" /><circle cx="9" cy="18" r="2" /><path d="M8 6.500l8 1M7 8l1.500 8M16.500 9.500L10.500 16.500" /></>,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20, label }: { name: IconName; size?: number; label?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} focusable="false">
      {PATHS[name]}
    </svg>
  );
}
