/**
 * Format a duration in seconds for compact display.
 *
 * Examples:
 *   formatDuration(3)    -> "3s"
 *   formatDuration(45)   -> "45s"
 *   formatDuration(125)  -> "2m05s"
 *   formatDuration(3661) -> "1h01m"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !isFinite(seconds) || seconds < 0) return "";
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m${s.toString().padStart(2, "0")}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h${m.toString().padStart(2, "0")}m`;
}
