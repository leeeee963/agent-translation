/**
 * File download utility — fetch + Blob + a.download
 */

import { toast } from "sonner";

export async function downloadFile(url: string, filename?: string): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);

  if (!filename) {
    const disposition = response.headers.get('Content-Disposition');
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
      if (match) filename = decodeURIComponent(match[1]);
    }
    if (!filename) filename = url.split('/').pop() || 'download';
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
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
