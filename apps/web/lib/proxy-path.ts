/**
 * The browser may only reach API paths made of plain segments. Dot segments, encoded separators or
 * backslashes could make the upstream URL resolve to a different route than the one we authorised.
 */
const SAFE_SEGMENT = /^[A-Za-z0-9_~:@-][A-Za-z0-9._~:@-]*$/;

export function isSafeProxyPath(segments: string[]): boolean {
  return segments.length > 0 && segments.every((s) => s !== "." && s !== ".." && SAFE_SEGMENT.test(s));
}
