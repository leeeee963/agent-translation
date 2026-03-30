import type { Job, ReviewChange } from "../types/translation";
import { tokenDiff } from "./diffUtils";
import { saveContent } from "./download";

// ── Status helpers ──────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  queued: "等待中",
  pending: "等待中",
  parsing: "解析中",
  terminology: "提取术语",
  awaiting_glossary_review: "待审核术语",
  translating: "翻译中",
  reviewing: "审校中",
  rebuilding: "重建中",
  done: "已完成",
  error: "失败",
  cancelled: "已取消",
};

export function statusLabel(status: string, t?: (key: string) => string) {
  if (t) {
    const i18nKey = `status.${status}`;
    const translated = t(i18nKey);
    if (translated !== i18nKey) return translated;
  }
  return STATUS_LABELS[status] || status || "未知";
}

export function isActive(status: string) {
  return ["queued", "pending", "parsing", "terminology", "translating", "reviewing", "rebuilding"].includes(status);
}

export function getStatusColor(status: string) {
  if (status === 'done') return 'bg-muted text-muted-foreground';
  if (status === 'error') return 'bg-destructive/10 text-destructive';
  if (status === 'cancelled') return 'bg-muted text-muted-foreground';
  if (isActive(status)) return 'bg-accent text-accent-foreground';
  return 'bg-muted text-muted-foreground';
}

// ── Export review changes as HTML ───────────────────────────────────

export function exportReviewChanges(targetLanguage: string, changes: ReviewChange[], baseName?: string) {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const diffToHtml = (before: string, after: string) =>
    tokenDiff(before, after).map(op => {
      const t = esc(op.text);
      if (op.type === 'equal') return t;
      if (op.type === 'delete') return `<del>${t}</del>`;
      return `<ins>${t}</ins>`;
    }).join('');

  const cards = changes.map(c => `
  <div class="card">
    <div class="src">原文：${esc(c.source_text)}</div>
    <div class="diff">${diffToHtml(c.before, c.after)}</div>
  </div>`).join('\n');

  const html = `<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>审校记录 - ${esc(targetLanguage)}</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:960px;margin:0 auto;padding:24px 28px;background:#f9fafb;color:#111;}
h1{font-size:17px;font-weight:600;margin-bottom:20px;color:#1f2937;}
.card{border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin-bottom:10px;background:#fff;}
.src{color:#9ca3af;font-size:12px;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.diff{font-size:14px;line-height:1.75;}
del{color:#dc2626;text-decoration:line-through;background:#fef2f2;padding:0 1px;border-radius:2px;}
ins{color:#16a34a;text-decoration:none;background:#f0fdf4;padding:0 1px;border-radius:2px;}
</style></head>
<body>
<h1>审校记录（共改写 ${changes.length} 处）- ${esc(targetLanguage)}</h1>
${cards}
</body></html>`;

  const prefix = baseName ? `${baseName}_` : '';
  const filename = `${prefix}${targetLanguage}_审校记录.html`;
  saveContent(html, filename);
}
