/**
 * File download utility.
 * - Desktop (pywebview): calls server-side export endpoint to save to ~/Downloads/
 * - Browser: uses fetch + Blob + a.download
 */

import { toast } from "sonner";

function isDesktop(): boolean {
  if ((window as any).pywebview) return true;
  const ua = navigator.userAgent;
  return ua.includes('AppleWebKit') && !ua.includes('Chrome') && !ua.includes('Firefox');
}

export async function downloadFile(url: string, filename?: string): Promise<void> {
  if (isDesktop()) {
    const exportUrl = url.replace('/api/download/', '/api/export/');
    const resp = await fetch(exportUrl, { method: 'POST' });
    if (resp.ok) {
      const data = await resp.json();
      toast.success(`已保存到 Downloads 文件夹`, { description: data.filename });
    } else {
      toast.error('导出失败');
    }
    return;
  }

  // Browser: fetch + Blob
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
  if (isDesktop()) {
    const resp = await fetch('/api/export-content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, filename }),
    });
    if (resp.ok) {
      const data = await resp.json();
      toast.success(`已保存到 Downloads 文件夹`, { description: data.filename });
    } else {
      toast.error('导出失败');
    }
    return;
  }

  // Browser fallback
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
