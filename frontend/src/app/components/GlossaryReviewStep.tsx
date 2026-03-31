import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { Button } from "./ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import type { Job, GlossaryTerm } from "../types/translation";
import { updateGlossaryTerm, confirmGlossary, reextractGlossary } from "../api";
import { AlertTriangle, CheckCircle2, Check, RefreshCw, LibraryBig, Info, ChevronDown, ChevronRight } from "lucide-react";
import { useLanguage } from "../contexts/LanguageContext";

interface GlossaryReviewStepProps {
  job: Job;
  onConfirmed?: () => void;
  readOnly?: boolean;
  title?: string;
  description?: string;
  defaultOpen?: boolean;
}

const AI_CATEGORY_KEYS: Record<string, string> = {
  proper_noun: "glossary.catProperNoun",
  person: "glossary.catPerson",
  place: "glossary.catPlace",
  brand: "glossary.catBrand",
  domain_term: "glossary.catDomainTerm",
  ambiguous: "glossary.catAmbiguous",
};

const STRATEGY_KEYS: { value: GlossaryTerm["strategy"]; labelKey: string; hintKey: string }[] = [
  { value: "hard", labelKey: "glossary.strategyEnforce", hintKey: "glossary.strategyEnforceHint" },
  { value: "keep_original", labelKey: "glossary.strategyPreserve", hintKey: "glossary.strategyPreserveHint" },
  { value: "skip", labelKey: "glossary.strategySkip", hintKey: "glossary.strategySkipHint" },
];


export function GlossaryReviewStep({ job, onConfirmed, readOnly = false, title, description, defaultOpen = true }: GlossaryReviewStepProps) {
  const { t, language } = useLanguage();
  const [sectionOpen, setSectionOpen] = useState(defaultOpen);
  const hasHeader = !!title;
  const terms = job.glossary?.terms ?? [];
  const targetLanguages = job.glossary?.target_languages ?? job.target_languages ?? [];

  const [localTerms, setLocalTerms] = useState<GlossaryTerm[]>(() => terms);

  // Sync localTerms when the server returns a fresh extraction (term IDs change)
  const termIds = terms.map((t) => t.id).join(",");
  useEffect(() => {
    setLocalTerms(terms);
    setEditingCell(null);
    setFilterCategory("all");
    setFilterSource("all");
    setFilterUncertain(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [termIds]);
  const [editingCell, setEditingCell] = useState<{ termId: string; lang: string } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterUncertain, setFilterUncertain] = useState(false);
  const [filterSource, setFilterSource] = useState<"all" | "library" | "new">("all");
  const [confirming, setConfirming] = useState(false);
  const [reextracting, setReextracting] = useState(false);
  const [error, setError] = useState("");
  const [showLibraryUpdateDialog, setShowLibraryUpdateDialog] = useState(false);
  const [pendingConfirmAction, setPendingConfirmAction] = useState<"start" | "all" | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const helpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!helpOpen) return;
    const handler = (e: MouseEvent) => {
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
        setHelpOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [helpOpen]);

  const handleStrategyChange = useCallback(
    async (termId: string, strategy: GlossaryTerm["strategy"]) => {
      setLocalTerms((prev) =>
        prev.map((t) => (t.id === termId ? { ...t, strategy } : t))
      );
      try {
        await updateGlossaryTerm(job.job_id, termId, { strategy });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        // Revert on error
        setLocalTerms((prev) =>
          prev.map((t) => (t.id === termId ? { ...t, strategy: t.strategy } : t))
        );
      }
    },
    [job.job_id]
  );

  const handleTargetEdit = useCallback(
    (termId: string, lang: string, currentValue: string) => {
      setEditingCell({ termId, lang });
      setEditValue(currentValue);
    },
    []
  );

  const handleSaveToLibraryToggle = useCallback(
    async (termId: string, value: boolean) => {
      setLocalTerms((prev) =>
        prev.map((t) => (t.id === termId ? { ...t, save_to_library: value } : t))
      );
      try {
        await updateGlossaryTerm(job.job_id, termId, { save_to_library: value });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setLocalTerms((prev) =>
          prev.map((t) => (t.id === termId ? { ...t, save_to_library: !value } : t))
        );
      }
    },
    [job.job_id]
  );

  const handleTargetSave = useCallback(async () => {
    if (!editingCell) return;
    const { termId, lang } = editingCell;
    const newTargets = { [lang]: editValue };

    setLocalTerms((prev) =>
      prev.map((t) =>
        t.id === termId ? { ...t, targets: { ...t.targets, [lang]: editValue } } : t
      )
    );
    setEditingCell(null);

    try {
      await updateGlossaryTerm(job.job_id, termId, { targets: newTargets });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [editingCell, editValue, job.job_id]);

  // Detect library terms whose targets were edited by the user
  const modifiedLibraryTerms = localTerms.filter((t) => {
    if (t.library_term_id == null) return false;
    const original = terms.find((o) => o.id === t.id);
    if (!original) return false;
    return JSON.stringify(t.targets) !== JSON.stringify(original.targets);
  });

  const doConfirm = useCallback(async (action: "start" | "all", updateLibraryTermIds?: string[]) => {
    setConfirming(true);
    setError("");
    try {
      if (action === "all") {
        await confirmGlossary(job.job_id, undefined, updateLibraryTermIds);
      } else {
        const nonSkippedIds = localTerms.filter((t) => t.strategy !== "skip").map((t) => t.id);
        await confirmGlossary(job.job_id, nonSkippedIds, updateLibraryTermIds);
      }
      onConfirmed();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConfirming(false);
    }
  }, [job.job_id, localTerms, onConfirmed]);

  const triggerConfirm = useCallback((action: "start" | "all") => {
    if (modifiedLibraryTerms.length > 0) {
      setPendingConfirmAction(action);
      setShowLibraryUpdateDialog(true);
    } else {
      doConfirm(action);
    }
  }, [modifiedLibraryTerms.length, doConfirm]);

  const handleConfirmAll = useCallback(() => triggerConfirm("all"), [triggerConfirm]);

  const handleReextract = useCallback(async () => {
    setReextracting(true);
    setError("");
    try {
      await reextractGlossary(job.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReextracting(false);
    }
  }, [job.job_id]);

  const handleStartTranslation = useCallback(() => triggerConfirm("start"), [triggerConfirm]);

  const filteredTerms = localTerms
    .filter((t) => {
      if (filterUncertain && !t.uncertain) return false;
      if (filterCategory !== "all" && t.ai_category !== filterCategory) return false;
      if (filterSource === "library" && t.library_term_id == null) return false;
      if (filterSource === "new" && t.library_term_id != null) return false;
      return true;
    })
    .sort((a, b) => (b.frequency || 0) - (a.frequency || 0));

  const categories = Array.from(new Set(localTerms.map((t) => t.ai_category).filter(Boolean)));
  const uncertainCount = localTerms.filter((t) => t.uncertain).length;
  const libraryCount = localTerms.filter((t) => t.library_term_id != null).length;
  const newCount = localTerms.length - libraryCount;
  const constraintCount = localTerms.filter((t) => t.strategy !== "skip").length;
  const maxFrequency = useMemo(
    () => Math.max(1, ...localTerms.map((t) => t.frequency || 0)),
    [localTerms]
  );

  const filterPills = (
    <div className="flex items-center gap-1.5 flex-wrap">
      <button
        className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${filterCategory === "all" && filterSource === "all" ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:bg-muted/50"}`}
        onClick={() => { setFilterCategory("all"); setFilterSource("all"); setFilterUncertain(false); }}
      >
        {t('glossary.filterAll')}
      </button>
      {categories.map((cat) => (
        <button
          key={cat}
          className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${filterCategory === cat ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:bg-muted/50"}`}
          onClick={() => setFilterCategory(filterCategory === cat ? "all" : cat)}
        >
          {t(AI_CATEGORY_KEYS[cat]) || cat}
        </button>
      ))}
      {libraryCount > 0 && (
        <>
          <span className="text-border mx-0.5">|</span>
          <button
            className={`text-xs px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${filterSource === "library" ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:bg-muted/50"}`}
            onClick={() => setFilterSource(filterSource === "library" ? "all" : "library")}
          >
            <LibraryBig className="size-2.5" />
            {t('glossary.libraryMatch')} ({libraryCount})
          </button>
          <button
            className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${filterSource === "new" ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:bg-muted/50"}`}
            onClick={() => setFilterSource(filterSource === "new" ? "all" : "new")}
          >
            {t('glossary.newlyExtracted')} ({newCount})
          </button>
        </>
      )}
      {uncertainCount > 0 && (
        <button
          className={`text-xs px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${filterUncertain ? "bg-foreground text-background border-foreground" : "bg-card text-foreground border-border hover:bg-muted/50"}`}
          onClick={() => setFilterUncertain(!filterUncertain)}
        >
          <AlertTriangle className="size-2.5" />
          {t('glossary.onlyUncertain')} ({uncertainCount})
        </button>
      )}
    </div>
  );

  return (
    <div className={hasHeader
      ? "bg-card border border-border rounded-lg px-5 py-4 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)] space-y-4"
      : "space-y-4"
    }>
      {/* Header row: title + filters */}
      {hasHeader && (
        <div className="flex items-start justify-between gap-3">
          <div
            className="flex items-center gap-2 cursor-pointer select-none flex-shrink-0"
            onClick={() => setSectionOpen((v) => !v)}
          >
            <span className="text-muted-foreground">
              {sectionOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
            </span>
            <span className="text-sm font-medium">{title}</span>
            {description && <span className="text-xs text-muted-foreground">{description}</span>}
          </div>
          {sectionOpen && filterPills}
        </div>
      )}

      {/* Collapsible body */}
      {(!hasHeader || sectionOpen) && (
        <div className="space-y-3">
          {!hasHeader && filterPills}

          {error && (
            <div className="rounded-lg px-4 py-3 text-sm bg-[var(--status-error-from)] text-[var(--status-error-fg)] border border-[var(--status-error-border)]">
              {error}
            </div>
          )}

      {/* Glossary Table */}
      <div className="overflow-auto rounded-lg border border-border">
        <Table className="table-fixed">
          <colgroup>
            <col className="w-8" />{/* # */}
            <col className="w-8" />{/* lib icon */}
            <col className="w-56" />{/* source: 224px */}
            <col className="w-44" />{/* strategy: 176px */}
            {targetLanguages.map((lang) => (
              <col key={lang} className="w-48" />
            ))}
            <col className="w-24" />{/* frequency: 96px */}
            <col style={{ width: '42rem' }} />{/* context: fixed wide, table scrolls horizontally */}
          </colgroup>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead className="text-center">#</TableHead>
              <TableHead title={t('glossary.colLibraryHint')}>
                <LibraryBig className="size-3.5 text-muted-foreground" />
              </TableHead>
              <TableHead className={targetLanguages.length > 1 ? "sticky left-0 z-10 bg-muted/50" : ""}>{t('glossary.colSource')} ({(job.glossary?.source_language ?? '').toUpperCase()})</TableHead>
              <TableHead className="text-center">
                <div className="flex items-center justify-center gap-1.5 relative" ref={helpRef}>
                  {t('glossary.colStrategy')}
                  <button
                    onClick={() => setHelpOpen((v) => !v)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Info className="size-3.5" />
                  </button>
                  {helpOpen && (
                    <div className="absolute left-0 top-full mt-2 w-80 rounded-lg border border-border bg-popover text-popover-foreground shadow-lg z-50 p-4 space-y-3 whitespace-normal text-left">
                      <div>
                        <p className="text-sm font-medium text-left">{t('glossary.helpStrategyTitle')}</p>
                        <ul className="text-xs text-muted-foreground mt-2 space-y-2">
                          {STRATEGY_KEYS.map((opt) => {
                            const fullText = t(opt.hintKey);
                            const parts = fullText.split(' — ');
                            const badgeColor = opt.value === 'hard'
                              ? 'bg-foreground text-background'
                              : 'bg-muted-foreground text-background';
                            return (
                              <li key={opt.value} className="flex items-start gap-2">
                                <span className={`${badgeColor} px-2 py-0.5 rounded text-xs font-medium shrink-0`}>
                                  {t(opt.labelKey)}
                                </span>
                                <span className="break-words">{parts.length > 1 ? parts[1] : fullText}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                      <div className="h-px bg-border" />
                      <div>
                        <p className="text-sm font-medium text-left">{t('glossary.helpLibTitle')}</p>
                        <ul className="text-xs text-muted-foreground mt-2 space-y-2">
                          <li className="flex items-center gap-2">
                            <LibraryBig className="size-4 text-[var(--cat-person-fg)] shrink-0" />
                            <span>{t('glossary.helpLibInLibrary')}</span>
                          </li>
                          <li className="flex items-center gap-2">
                            <span className="size-4 shrink-0 rounded border-2 border-muted-foreground/50 flex items-center justify-center">
                              <Check className="size-3 text-muted-foreground" />
                            </span>
                            <span>{t('glossary.helpLibNew')}</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              </TableHead>
              {targetLanguages.map((lang) => (
                <TableHead key={lang}>{lang.toUpperCase()}</TableHead>
              ))}
              <TableHead className="text-center">{t('glossary.colFrequency')}</TableHead>
              <TableHead>{t('glossary.colContext')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTerms.map((term, idx) => (
              <TableRow
                key={term.id}
                className={term.strategy === "skip" ? "opacity-40" : ""}
              >
                <TableCell className="text-muted-foreground text-xs text-center">{idx + 1}</TableCell>
                <TableCell>
                  {term.library_term_id != null ? (
                    <LibraryBig className="size-4 text-[var(--cat-person-fg)]" title={t('glossary.fromLibraryTitle')} />
                  ) : readOnly ? (
                    <span className="size-4 block" />
                  ) : (
                    <button
                      onClick={() => handleSaveToLibraryToggle(term.id, !term.save_to_library)}
                      className={`size-4 rounded border-2 flex items-center justify-center transition-colors ${
                        term.save_to_library
                          ? "bg-foreground border-foreground"
                          : "border-muted-foreground/50 hover:border-foreground"
                      }`}
                      title={term.save_to_library ? t('glossary.unsaveFromLibrary') : t('glossary.saveToLibrary')}
                    >
                      {term.save_to_library && <Check className="size-3 text-background" />}
                    </button>
                  )}
                </TableCell>
                <TableCell className={`whitespace-normal ${targetLanguages.length > 1 ? "sticky left-0 z-10 bg-[inherit]" : ""}`}>
                  <span className="font-medium text-sm">{term.source}</span>
                  {term.uncertain && term.uncertainty_note && (() => {
                    const note = term.uncertainty_note === "TRANSLATION_DIFFERS"
                      ? t('glossary.noteTranslationDiffers')
                      : term.uncertainty_note.startsWith("MISSING_TRANSLATIONS:")
                        ? t('glossary.noteMissingTranslations').replace('{langs}', term.uncertainty_note.split(':')[1])
                        : term.uncertainty_note;
                    return (
                      <span className="relative inline-block ml-1 align-middle text-[var(--status-warning-fg)] cursor-help group/tip">
                        <AlertTriangle className="size-3.5" />
                        <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 hidden group-hover/tip:block w-max max-w-[200px] px-2 py-1 text-xs text-popover-foreground bg-popover border border-border rounded-md shadow-md z-50 whitespace-normal">
                          {note}
                        </span>
                      </span>
                    );
                  })()}
                </TableCell>
                <TableCell className="text-center">
                  {readOnly ? (
                    <span className={`inline-block px-2.5 py-1 text-xs font-medium rounded-md ${
                      term.strategy === 'hard' ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground'
                    }`}>
                      {t(STRATEGY_KEYS.find(s => s.value === term.strategy)?.labelKey ?? '')}
                    </span>
                  ) : (
                    <div className="inline-flex rounded-md border border-border overflow-hidden">
                      {STRATEGY_KEYS.map((opt) => {
                        const selected = term.strategy === opt.value;
                        const colorMap: Record<string, string> = {
                          hard: selected
                            ? "bg-foreground text-background"
                            : "text-muted-foreground hover:bg-muted/50",
                          keep_original: selected
                            ? "bg-muted-foreground text-background"
                            : "text-muted-foreground hover:bg-muted/50",
                          skip: selected
                            ? "bg-muted-foreground text-background"
                            : "text-muted-foreground hover:bg-muted/50",
                        };
                        return (
                          <button
                            key={opt.value}
                            onClick={() => handleStrategyChange(term.id, opt.value)}
                            className={`px-2.5 py-1 text-xs font-medium border-r last:border-r-0 border-border transition-colors ${colorMap[opt.value]}`}
                            title={t(opt.hintKey)}
                          >
                            {t(opt.labelKey)}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </TableCell>
                {targetLanguages.map((lang) => (
                  <TableCell key={lang} className="whitespace-normal">
                    {readOnly ? (
                      <span className="text-sm font-medium">
                        {term.targets[lang] || <span className="text-muted-foreground/30">—</span>}
                      </span>
                    ) : editingCell?.termId === term.id && editingCell?.lang === lang ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={handleTargetSave}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleTargetSave();
                            if (e.key === "Escape") setEditingCell(null);
                          }}
                          className="border border-border rounded px-1.5 py-0.5 text-sm w-full min-w-16 bg-background"
                        />
                        <button onClick={handleTargetSave} className="text-[var(--status-success-fg)] hover:opacity-80">
                          <CheckCircle2 className="size-4" />
                        </button>
                      </div>
                    ) : (
                      <button
                        className="text-sm text-left w-full hover:bg-muted/50 rounded py-0.5 min-h-6 transition-colors font-medium"
                        onClick={() => handleTargetEdit(term.id, lang, term.targets[lang] || "")}
                        title={t('glossary.clickToEdit')}
                      >
                        {term.targets[lang] || <span className="text-muted-foreground/30">—</span>}
                      </button>
                    )}
                  </TableCell>
                ))}
                <TableCell className="text-sm text-muted-foreground">
                  {term.frequency > 0 ? (() => {
                    const ratio = term.frequency / maxFrequency;
                    const opacity = 0.15 + ratio * 0.55;
                    return (
                      <div className="flex flex-col items-center gap-1">
                        <span className="tabular-nums">{term.frequency}</span>
                        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-foreground"
                            style={{
                              width: `${Math.round(ratio * 100)}%`,
                              opacity,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })() : <span className="block text-center">-</span>}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground whitespace-normal break-words">
                  {term.context || "-"}
                </TableCell>
              </TableRow>
            ))}
            {filteredTerms.length === 0 && (
              <TableRow>
                <TableCell colSpan={5 + targetLanguages.length} className="text-center text-muted-foreground py-8">
                  {t('glossary.noFilterResults')}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Bottom summary + action (hidden in readOnly) */}
      {!readOnly && <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-sm text-muted-foreground">
          {t('glossary.bottomSummary').replace('{total}', String(localTerms.length))}
          {libraryCount > 0 && (
            t('glossary.bottomLibrary')
              .replace('{lib}', String(libraryCount))
              .replace('{new}', String(newCount))
          )}
          {t('glossary.bottomConstraint').replace('{count}', String(constraintCount))}
        </p>
        <Button
          size="sm"
          onClick={handleStartTranslation}
          disabled={confirming}
          className="bg-foreground text-background hover:bg-foreground/85"
        >
          {confirming ? t('glossary.processing') : t('glossary.startTranslationArrow')}
        </Button>
      </div>}

        </div>
      )}

      {/* Library Update Confirmation Dialog */}
      <Dialog open={showLibraryUpdateDialog} onOpenChange={setShowLibraryUpdateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('glossary.libSyncTitle')}</DialogTitle>
          </DialogHeader>
          <div className="py-3 space-y-2">
            <p className="text-sm text-muted-foreground">
              {t('glossary.libSyncDesc')}
            </p>
            <ul className="text-sm space-y-1 max-h-40 overflow-auto">
              {modifiedLibraryTerms.map((mt) => (
                <li key={mt.id} className="flex items-center gap-2">
                  <LibraryBig className="size-3.5 text-[var(--cat-person-fg)]" />
                  <span className="font-medium">{mt.source}</span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-muted-foreground mt-2">
              {t('glossary.libSyncExplain')}
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowLibraryUpdateDialog(false);
                if (pendingConfirmAction) doConfirm(pendingConfirmAction);
                setPendingConfirmAction(null);
              }}
            >
              {t('glossary.libSyncThisTime')}
            </Button>
            <Button
              className="bg-foreground text-background hover:bg-foreground/85"
              onClick={() => {
                setShowLibraryUpdateDialog(false);
                const ids = modifiedLibraryTerms.map((mt) => mt.id);
                if (pendingConfirmAction) doConfirm(pendingConfirmAction, ids);
                setPendingConfirmAction(null);
              }}
            >
              {t('glossary.libSyncUpdate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
