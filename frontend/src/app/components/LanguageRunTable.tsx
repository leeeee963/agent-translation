import { useState } from "react";
import { Progress } from "./ui/progress";
import { Badge } from "./ui/badge";
import { Download } from "lucide-react";
import type { LanguageRun } from "../types/translation";
import { useLanguage } from "../contexts/LanguageContext";
import { tokenDiff } from "../utils/diffUtils";
import { downloadFile } from "../utils/download";
import { formatDuration } from "../utils/duration";
import { isActive, statusLabel, getStatusColor, exportReviewChanges, isReviewChanged } from "../utils/jobStatus";

// ── Timing display: elapsed + ETA, picks up live updates as run snapshot polls
function RunTiming({ run }: { run: LanguageRun }) {
  const { language } = useLanguage();
  const elapsed = run.elapsed_seconds;
  const eta = run.eta_seconds;
  if (elapsed == null && (eta == null || eta <= 0.5)) return null;

  const parts: string[] = [];
  if (elapsed != null && elapsed >= 1) {
    parts.push(language === "zh" ? `已用 ${formatDuration(elapsed)}` : `${formatDuration(elapsed)} elapsed`);
  }
  if (eta != null && eta > 0.5) {
    parts.push(language === "zh" ? `剩 ${formatDuration(eta)}` : `${formatDuration(eta)} left`);
  }
  if (parts.length === 0) return null;

  return (
    <span className="text-[10px] text-muted-foreground/70 whitespace-nowrap flex-shrink-0">
      {parts.join(" · ")}
    </span>
  );
}

// ── Inline diff display ─────────────────────────────────────────────

function InlineDiff({ before, after }: { before: string; after: string }) {
  const ops = tokenDiff(before, after);
  return (
    <span>
      {ops.map((op, idx) => {
        if (op.type === 'equal') return <span key={idx}>{op.text}</span>;
        if (op.type === 'delete') return <span key={idx} className="bg-red-100 text-red-600 line-through dark:bg-red-900/30 dark:text-red-400">{op.text}</span>;
        return <span key={idx} className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{op.text}</span>;
      })}
    </span>
  );
}

// ── Language run table ──────────────────────────────────────────────

export function LanguageRunTable({ runs, sourceFilename }: { runs: LanguageRun[]; sourceFilename?: string }) {
  const { t } = useLanguage();
  const baseName = sourceFilename ? sourceFilename.replace(/\.[^.]+$/, '') : '';
  const [expandedLang, setExpandedLang] = useState<string | null>(null);

  return (
    <div className="mt-2 rounded-lg border border-border overflow-hidden">
      {runs.map((run, i) => {
        const hasReview = run.review_changes && run.review_changes.length > 0;
        const isExpanded = expandedLang === run.target_language;
        const isDone = run.status === 'done';
        const isRunActive = isActive(run.status);

        return (
          <div key={run.target_language}>
            {/* Row */}
            <div
              className={[
                "flex items-center gap-3 px-3 py-2 text-xs",
                i > 0 ? "border-t border-border" : "",
                hasReview ? "cursor-pointer hover:bg-accent/20 transition-colors" : "",
              ].join(" ")}
              onClick={hasReview ? () => setExpandedLang(isExpanded ? null : run.target_language) : undefined}
            >
              {/* Language */}
              <span className="font-medium text-sm w-16 flex-shrink-0">{run.target_language}</span>

              {/* Progress — only when not done */}
              {!isDone && (
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {run.percent > 0 && (
                    <>
                      <Progress value={run.percent || 0} className="h-1 flex-1" />
                      <span className="text-muted-foreground flex-shrink-0 text-right whitespace-nowrap">
                        {run.segments_total > 0
                          ? `${run.segments_done}/${run.segments_total}`
                          : `${Math.round(run.percent)}%`}
                      </span>
                      <RunTiming run={run} />
                    </>
                  )}
                  {run.error_message && (
                    <span className="text-destructive truncate">{run.error_message}</span>
                  )}
                </div>
              )}

              {/* Status — only when in progress or error */}
              {!isDone && !['queued', 'pending'].includes(run.status) && (
                <Badge className={`${getStatusColor(run.status)} flex-shrink-0`}>
                  {statusLabel(run.status, t)}
                </Badge>
              )}

              {/* Spacer when done — push buttons to the right */}
              {isDone && <div className="flex-1" />}

              {/* Downloads */}
              {isDone && run.download_url && (
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {run.draft_download_url && (
                    <button
                      onClick={(e) => { e.stopPropagation(); downloadFile(run.draft_download_url!); }}
                      className="inline-flex items-center gap-1 text-xs font-medium bg-muted text-foreground px-2 py-0.5 rounded-md hover:bg-muted/80 transition-colors border border-border cursor-pointer"
                    >
                      <Download className="size-3" />
                      {t('review.translated')}
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); downloadFile(run.download_url); }}
                    className="inline-flex items-center gap-1 text-xs font-medium bg-foreground text-background px-2 py-0.5 rounded-md hover:bg-foreground/90 transition-colors cursor-pointer"
                  >
                    <Download className="size-3" />
                    {run.draft_download_url ? t('review.reviewed') : t('common.download')}
                  </button>
                </div>
              )}

              {/* Review count + export icon */}
              {hasReview && (
                <div className="flex items-center gap-1.5 flex-shrink-0 text-xs text-muted-foreground">
                  <span className="cursor-pointer hover:text-foreground transition-colors">
                    {t('review.title')} ({run.review_changes!.filter(isReviewChanged).length})
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); exportReviewChanges(run.target_language, run.review_changes!, baseName); }}
                    className="hover:text-foreground transition-colors p-0.5 rounded"
                    title={t('review.export')}
                  >
                    <Download className="size-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Expanded review details */}
            {hasReview && isExpanded && (
              <div className="border-t border-border bg-muted/30 px-3 py-2">
                <div className="space-y-2 max-h-96 overflow-y-auto overflow-x-hidden">
                  {run.review_changes!.map((c) => {
                    const isChanged = isReviewChanged(c);
                    return (
                      <div key={c.block_id} className={`rounded p-2 text-xs min-w-0 ${isChanged ? "border border-border bg-card space-y-1" : "bg-transparent px-2 py-0.5"}`}>
                        {isChanged ? (
                          <>
                            {c.source_text && (
                              <p className="text-muted-foreground truncate">{t('review.original')}: {c.source_text}</p>
                            )}
                            <p className="text-foreground leading-relaxed break-all">
                              <InlineDiff before={c.before} after={c.after} />
                            </p>
                          </>
                        ) : (
                          <p className="text-muted-foreground/60 leading-relaxed break-all">{c.after}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
