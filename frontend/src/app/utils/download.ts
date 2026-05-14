/**
 * File download utility.
 *
 * Uses a native <a href download> click — the browser streams the file
 * directly, so the download starts the instant the user clicks. The previous
 * `await fetch + blob + click` pattern blocked for the entire transfer
 * (20+ seconds for a 21 MB file with no UI feedback), which made users
 * click again and again and triggered N concurrent downloads.
 *
 * The backend serves these URLs with `Content-Disposition: attachment` already
 * (see FileResponse(..., filename=...) in src/server.py), so we don't need
 * to fetch headers client-side to pick the filename.
 *
 * A small per-URL dedupe window (1 s) absorbs accidental double-clicks
 * defensively, even though the click itself is now instantaneous.
 */

const recentClicks = new Map<string, number>();
const DEDUPE_WINDOW_MS = 1000;

export function downloadFile(url: string, filename?: string): void {
  const now = Date.now();
  const last = recentClicks.get(url) ?? 0;
  if (now - last < DEDUPE_WINDOW_MS) return;
  recentClicks.set(url, now);

  const a = document.createElement('a');
  a.href = url;
  // An empty `download` attribute tells the browser to download instead of
  // navigate; the actual filename comes from the server's Content-Disposition.
  a.download = filename ?? '';
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function saveContent(content: string, filename: string): Promise<void> {
  const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
