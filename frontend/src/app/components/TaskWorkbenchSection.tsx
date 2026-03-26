import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Progress } from "./ui/progress";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  DropdownMenuItem,
} from "./ui/dropdown-menu";
import type { Job, LanguageRun, ReviewChange } from "../types/translation";
import {
  Download,
  CheckCircle2,
  Loader2,
  Clock,
  ChevronDown,
  ChevronRight,
  XCircle,
  ChevronsDownUp,
  ChevronsUpDown,
  FileText,
  BookOpen,
  Globe,
  Search,
  Filter,
  Bookmark,
  Plus,
  Trash2,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "./ui/popover";
import { useLanguage } from "../contexts/LanguageContext";
import { GlossaryReviewStep } from "./GlossaryReviewStep";
import { PhaseCard } from "./PhaseCard";
import { StepBadge, type Step } from "./StepIndicator";
import {
  groupJobs,
  countJobsInGroup,
  getAvailableFileTypes,
  useTaskViewPreferences,
  type GroupByKey,
  type TaskViewPreferences,
  type JobGroup,
  type SavedView,
} from "../utils/taskGrouping";

interface TaskWorkbenchSectionProps {
  jobs: Job[];
  onCancelJob: (jobId: string) => void;
  onGlossaryConfirmed?: () => void;
}

function exportReviewChanges(targetLanguage: string, changes: ReviewChange[], baseName?: string) {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const diffToHtml = (before: string, after: string) =>
    charDiff(before, after).map(op => {
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

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const prefix = baseName ? `${baseName}_` : '';
  a.download = `${prefix}${targetLanguage}_审校记录.html`;
  a.click();
  URL.revokeObjectURL(url);
}

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

function statusLabel(status: string, t?: (key: string) => string) {
  if (t) {
    const i18nKey = `status.${status}`;
    const translated = t(i18nKey);
    if (translated !== i18nKey) return translated;
  }
  return STATUS_LABELS[status] || status || "未知";
}

function isActive(status: string) {
  return ["queued", "pending", "parsing", "terminology", "translating", "reviewing", "rebuilding"].includes(status);
}

function getStatusIcon(status: string) {
  if (status === 'done') return <CheckCircle2 className="size-5 text-muted-foreground" />;
  if (status === 'error') return <XCircle className="size-5 text-destructive" />;
  if (isActive(status)) return <Loader2 className="size-5 text-foreground animate-spin" />;
  return <Clock className="size-5 text-muted-foreground" />;
}

function getStatusColor(status: string) {
  if (status === 'done') return 'bg-muted text-muted-foreground';
  if (status === 'error') return 'bg-destructive/10 text-destructive';
  if (status === 'cancelled') return 'bg-muted text-muted-foreground';
  if (isActive(status)) return 'bg-accent text-accent-foreground';
  return 'bg-muted text-muted-foreground';
}

/** Trigger downloads for all completed language runs of a job */
function downloadAll(job: Job) {
  const doneRuns = (job.language_runs || []).filter(
    (r) => r.status === 'done' && r.download_url
  );
  doneRuns.forEach((run, i) => {
    setTimeout(() => {
      const a = document.createElement('a');
      a.href = run.download_url;
      a.download = '';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }, i * 300); // stagger to avoid browser blocking
  });
}

// ── Phase derivation ─────────────────────────────────────────────────

type PhaseStatus = 'pending' | 'active' | 'done' | 'hidden';

interface PhaseInfo {
  id: 'glossary' | 'translation' | 'review';
  status: PhaseStatus;
}

function getJobPhases(job: Job): PhaseInfo[] {
  const phases: PhaseInfo[] = [];
  const s = job.status;

  // Phase 1: Glossary (only for glossary mode)
  if (job.use_glossary) {
    let gs: PhaseStatus = 'pending';
    if (['parsing', 'terminology', 'awaiting_glossary_review'].includes(s)) gs = 'active';
    else if (['translating', 'rebuilding', 'reviewing', 'done'].includes(s)) gs = 'done';
    phases.push({ id: 'glossary', status: gs });
  }

  // Phase 2: Translation
  let ts: PhaseStatus = 'pending';
  if (['translating', 'rebuilding'].includes(s)) ts = 'active';
  else if (['reviewing', 'done'].includes(s)) ts = 'done';
  phases.push({ id: 'translation', status: ts });

  return phases;
}

function getJobSteps(job: Job, t: (key: string) => string): Step[] {
  const s = job.status;
  const isError = s === 'error';

  type S = Step['status'];
  const stepStatus = (doneWhen: string[], activeWhen: string[]): S => {
    if (isError && activeWhen.includes(s)) return 'error';
    if (doneWhen.some((st) => st === s || (['done'].includes(s) && true))) {
      // Check if this step should be 'done'
    }
    if (activeWhen.includes(s)) return 'active';
    // Check done: if current status is beyond this step
    const allStatuses = job.use_glossary
      ? ['queued','pending','parsing','terminology','awaiting_glossary_review','translating','rebuilding','reviewing','done']
      : ['queued','pending','translating','rebuilding','reviewing','done'];
    const currentIdx = allStatuses.indexOf(s);
    const lastActiveIdx = Math.max(...activeWhen.map((st) => allStatuses.indexOf(st)));
    if (currentIdx > lastActiveIdx) return 'done';
    return 'pending';
  };

  const steps: Step[] = [];

  if (job.use_glossary) {
    steps.push({
      label: t('step.extractTerms'),
      status: stepStatus([], ['parsing', 'terminology']),
    });
    steps.push({
      label: t('step.confirmTerms'),
      status: stepStatus([], ['awaiting_glossary_review']),
    });
  }

  steps.push({
    label: t('step.translate'),
    status: stepStatus([], ['translating', 'rebuilding']),
  });
  steps.push({
    label: t('step.review'),
    status: stepStatus([], ['reviewing']),
  });
  steps.push({
    label: t('step.complete'),
    status: s === 'done' ? 'done' : 'pending',
  });

  return steps;
}

// ── Grouping rows with drag & drop ───────────────────────────────────

const GROUP_FIELD_OPTIONS: GroupByKey[] = ["status", "time", "fileType"];

function GroupingRows({
  activeGroups,
  sortDirections,
  groupLabel,
  setGroupAtLevel,
  removeGroupAtLevel,
  toggleSortAtLevel,
  onSwap,
  t,
}: {
  activeGroups: GroupByKey[];
  sortDirections: [import("../utils/taskGrouping").SortDirection, import("../utils/taskGrouping").SortDirection];
  groupLabel: (k: GroupByKey) => string;
  setGroupAtLevel: (level: number, value: GroupByKey) => void;
  removeGroupAtLevel: (level: number) => void;
  toggleSortAtLevel: (level: number) => void;
  onSwap: () => void;
  t: (k: string) => string;
}) {
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);

  return (
    <div className="space-y-1.5">
      {activeGroups.map((groupKey, level) => {
        const usedByOther = activeGroups.filter((_, i) => i !== level);
        const available = GROUP_FIELD_OPTIONS.filter((o) => !usedByOther.includes(o));
        const isDragging = dragIdx === level;
        const isOver = overIdx === level && dragIdx !== level;
        const dir = sortDirections[level];

        return (
          <div
            key={level}
            draggable
            onDragStart={() => setDragIdx(level)}
            onDragEnd={() => { setDragIdx(null); setOverIdx(null); }}
            onDragOver={(e) => { e.preventDefault(); setOverIdx(level); }}
            onDragLeave={() => setOverIdx(null)}
            onDrop={(e) => {
              e.preventDefault();
              if (dragIdx !== null && dragIdx !== level) onSwap();
              setDragIdx(null);
              setOverIdx(null);
            }}
            className={[
              "flex items-center gap-1.5 rounded-md px-1 py-0.5 transition-colors",
              isDragging ? "opacity-40" : "",
              isOver ? "bg-accent/40" : "",
            ].join(" ")}
          >
            <span className="text-muted-foreground cursor-grab active:cursor-grabbing select-none flex-shrink-0">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <circle cx="5.5" cy="4" r="1.2"/><circle cx="10.5" cy="4" r="1.2"/>
                <circle cx="5.5" cy="8" r="1.2"/><circle cx="10.5" cy="8" r="1.2"/>
                <circle cx="5.5" cy="12" r="1.2"/><circle cx="10.5" cy="12" r="1.2"/>
              </svg>
            </span>
            <Select value={groupKey} onValueChange={(v: GroupByKey) => setGroupAtLevel(level, v)}>
              <SelectTrigger className="h-7 w-[110px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {available.map((o) => (
                  <SelectItem key={o} value={o} className="text-xs">{groupLabel(o)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* Sort direction toggle */}
            <button
              onClick={() => toggleSortAtLevel(level)}
              className="h-7 ml-1 flex items-center gap-0 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
            >
              {dir === "asc" ? (
                <>A<span className="inline-block mx-1 w-6 text-center tracking-widest">→</span>Z</>
              ) : (
                <>Z<span className="inline-block mx-1 w-6 text-center tracking-widest">→</span>A</>
              )}
            </button>
            <button
              onClick={() => removeGroupAtLevel(level)}
              className="text-muted-foreground hover:text-destructive transition-colors p-0.5 flex-shrink-0"
            >
              <XCircle className="size-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ── Toolbar ──────────────────────────────────────────────────────────

function TaskListToolbar({
  prefs,
  onChange,
  jobs,
  t,
}: {
  prefs: TaskViewPreferences;
  onChange: (update: Partial<TaskViewPreferences>) => void;
  jobs: Job[];
  t: (k: string) => string;
}) {
  const [searchInput, setSearchInput] = useState(prefs.filter.search);
  const [searchOpen, setSearchOpen] = useState(!!prefs.filter.search);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const [viewName, setViewName] = useState("");

  // Debounced search
  useEffect(() => {
    timerRef.current = setTimeout(() => {
      onChange({ filter: { ...prefs.filter, search: searchInput } });
    }, 200);
    return () => clearTimeout(timerRef.current);
  }, [searchInput]);

  const fileTypes = useMemo(() => getAvailableFileTypes(jobs), [jobs]);

  const groupLabel = (key: GroupByKey) => t(`tasks.group.${key}`);

  // Compute active grouping levels (non-"none")
  const activeGroups: GroupByKey[] = [];
  if (prefs.grouping.primary !== "none") activeGroups.push(prefs.grouping.primary);
  if (prefs.grouping.secondary !== "none" && prefs.grouping.secondary !== prefs.grouping.primary) {
    activeGroups.push(prefs.grouping.secondary);
  }

  const filterCount = prefs.filter.statuses.length + prefs.filter.fileTypes.length + prefs.filter.timeBuckets.length;

  const toggleStatusFilter = (cat: string) => {
    const current = prefs.filter.statuses;
    const next = current.includes(cat) ? current.filter((s) => s !== cat) : [...current, cat];
    onChange({ filter: { ...prefs.filter, statuses: next } });
  };

  const toggleFileTypeFilter = (ext: string) => {
    const current = prefs.filter.fileTypes;
    const next = current.includes(ext) ? current.filter((s) => s !== ext) : [...current, ext];
    onChange({ filter: { ...prefs.filter, fileTypes: next } });
  };

  const toggleTimeBucketFilter = (key: string) => {
    const current = prefs.filter.timeBuckets;
    const next = current.includes(key) ? current.filter((s) => s !== key) : [...current, key];
    onChange({ filter: { ...prefs.filter, timeBuckets: next } });
  };

  const TIME_BUCKET_OPTIONS = [
    { key: "today", labelKey: "tasks.groupTime.today" },
    { key: "yesterday", labelKey: "tasks.groupTime.yesterday" },
    { key: "last7Days", labelKey: "tasks.groupTime.last7Days" },
    { key: "last30Days", labelKey: "tasks.groupTime.last30Days" },
    { key: "older", labelKey: "tasks.groupTime.older" },
  ];

  const setGroupAtLevel = (level: number, value: GroupByKey) => {
    if (level === 0) {
      const secondary = value === prefs.grouping.secondary ? "none" : prefs.grouping.secondary;
      onChange({ grouping: { ...prefs.grouping, primary: value, secondary } });
    } else {
      onChange({ grouping: { ...prefs.grouping, secondary: value } });
    }
  };

  const removeGroupAtLevel = (level: number) => {
    if (level === 0) {
      onChange({ grouping: { ...prefs.grouping, primary: prefs.grouping.secondary !== "none" ? prefs.grouping.secondary : "none", secondary: "none", primarySort: prefs.grouping.secondarySort, secondarySort: "asc" } });
    } else {
      onChange({ grouping: { ...prefs.grouping, secondary: "none", secondarySort: "asc" } });
    }
  };

  const toggleSortAtLevel = (level: number) => {
    if (level === 0) {
      onChange({ grouping: { ...prefs.grouping, primarySort: prefs.grouping.primarySort === "asc" ? "desc" : "asc" } });
    } else {
      onChange({ grouping: { ...prefs.grouping, secondarySort: prefs.grouping.secondarySort === "asc" ? "desc" : "asc" } });
    }
  };

  const addGroup = () => {
    if (activeGroups.length === 0) {
      onChange({ grouping: { ...prefs.grouping, primary: "status", secondary: "none", primarySort: "asc" } });
    } else if (activeGroups.length === 1) {
      const available = GROUP_FIELD_OPTIONS.filter((o) => o !== activeGroups[0]);
      onChange({ grouping: { ...prefs.grouping, secondary: available[0] || "time", secondarySort: "asc" } });
    }
  };

  const applyView = (view: SavedView) => {
    onChange({ grouping: view.grouping, filter: { ...prefs.filter, ...view.filter }, activeViewId: view.id });
  };

  const saveCurrentView = () => {
    if (!viewName.trim()) return;
    const newView: SavedView = {
      id: crypto.randomUUID(),
      name: viewName.trim(),
      grouping: { ...prefs.grouping },
      filter: { statuses: [...prefs.filter.statuses], fileTypes: [...prefs.filter.fileTypes] },
    };
    onChange({ savedViews: [...prefs.savedViews, newView], activeViewId: newView.id } as Partial<TaskViewPreferences>);
    setViewName("");
  };

  const deleteView = (id: string) => {
    onChange({
      savedViews: prefs.savedViews.filter((v) => v.id !== id),
      activeViewId: prefs.activeViewId === id ? null : prefs.activeViewId,
    } as Partial<TaskViewPreferences>);
  };

  return (
    <div className="flex items-center gap-1.5 pb-3 mb-1 flex-shrink-0">
      {/* Search toggle */}
      {searchOpen ? (
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onBlur={() => { if (!searchInput) setSearchOpen(false); }}
            placeholder={t("tasks.toolbar.search")}
            className="h-7 w-44 pl-7 text-xs"
            autoFocus
          />
          {searchInput && (
            <button
              onClick={() => { setSearchInput(""); setSearchOpen(false); }}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <XCircle className="size-3.5" />
            </button>
          )}
        </div>
      ) : (
        <button
          onClick={() => setSearchOpen(true)}
          className="h-7 w-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
        >
          <Search className="size-3.5" />
        </button>
      )}

      {/* Filter Popover */}
      <Popover>
        <PopoverTrigger asChild>
          <button className="h-7 px-2.5 flex items-center gap-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors">
            <Filter className="size-3.5" />
            <span>{t("tasks.toolbar.filter")}</span>
            {filterCount > 0 && (
              <span className="bg-foreground text-background text-[10px] font-medium rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">{filterCount}</span>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto min-w-[200px] p-3">
          {/* Status filter */}
          <div className="mb-3">
            <p className="text-xs font-medium text-muted-foreground mb-1.5">{t("tasks.toolbar.filterStatus")}</p>
            <div className="flex flex-wrap gap-1">
              {(["active", "error", "completed"] as const).map((cat) => (
                <label key={cat} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-accent/30 rounded px-2 py-1 transition-colors whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={prefs.filter.statuses.includes(cat)}
                    onChange={() => toggleStatusFilter(cat)}
                    className="rounded border-border"
                  />
                  {t(`tasks.groupStatus.${cat}`)}
                </label>
              ))}
            </div>
          </div>
          {/* Time filter */}
          <div className="mb-3">
            <p className="text-xs font-medium text-muted-foreground mb-1.5">{t("tasks.group.time")}</p>
            <div className="flex flex-wrap gap-1">
              {TIME_BUCKET_OPTIONS.map(({ key, labelKey }) => (
                <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-accent/30 rounded px-2 py-1 transition-colors whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={prefs.filter.timeBuckets.includes(key)}
                    onChange={() => toggleTimeBucketFilter(key)}
                    className="rounded border-border"
                  />
                  {t(labelKey)}
                </label>
              ))}
            </div>
          </div>
          {/* File type filter */}
          {fileTypes.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1.5">{t("tasks.toolbar.filterType")}</p>
              <div className="flex flex-wrap gap-1">
                {fileTypes.map((ext) => (
                  <label key={ext} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-accent/30 rounded px-2 py-1 transition-colors whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={prefs.filter.fileTypes.includes(ext)}
                      onChange={() => toggleFileTypeFilter(ext)}
                      className="rounded border-border"
                    />
                    {ext.replace(".", "").toUpperCase()}
                  </label>
                ))}
              </div>
            </div>
          )}
        </PopoverContent>
      </Popover>

      {/* Grouping Popover */}
      <Popover>
        <PopoverTrigger asChild>
          <button className="h-7 px-2.5 flex items-center gap-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors">
            <ChevronsDownUp className="size-3.5" />
            <span>{activeGroups.length > 0 ? `${activeGroups.length} ${t("tasks.toolbar.grouping")}` : t("tasks.toolbar.grouping")}</span>
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-3">
          <p className="text-xs font-medium text-muted-foreground mb-2.5">{t("tasks.toolbar.groupCondition")}</p>
          <GroupingRows
            activeGroups={activeGroups}
            sortDirections={[prefs.grouping.primarySort || "asc", prefs.grouping.secondarySort || "asc"]}
            groupLabel={groupLabel}
            setGroupAtLevel={setGroupAtLevel}
            removeGroupAtLevel={removeGroupAtLevel}
            toggleSortAtLevel={toggleSortAtLevel}
            onSwap={() => onChange({ grouping: { ...prefs.grouping, primary: prefs.grouping.secondary, secondary: prefs.grouping.primary, primarySort: prefs.grouping.secondarySort, secondarySort: prefs.grouping.primarySort } })}
            t={t}
          />
          {activeGroups.length < 2 && (
            <button
              onClick={addGroup}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mt-2.5 transition-colors"
            >
              <Plus className="size-3" />
              {t("tasks.toolbar.addGroup")}
            </button>
          )}
        </PopoverContent>
      </Popover>

      {/* Save / Switch View */}
      <Popover>
        <PopoverTrigger asChild>
          <button className="h-7 px-2.5 flex items-center gap-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors">
            <Bookmark className="size-3.5" />
            <span>
              {prefs.activeViewId
                ? prefs.savedViews.find((v) => v.id === prefs.activeViewId)?.name || t("tasks.toolbar.savedViews")
                : t("tasks.toolbar.saveView")}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-3">
          {/* Save new */}
          <div className="flex items-center gap-1.5 mb-2">
            <Input
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveCurrentView()}
              placeholder={t("tasks.toolbar.viewName")}
              className="h-7 text-xs flex-1"
            />
            <Button size="sm" className="h-7 text-xs px-2.5" onClick={saveCurrentView} disabled={!viewName.trim()}>
              {t("common.save")}
            </Button>
          </div>
          {/* Existing views */}
          {prefs.savedViews.length > 0 && (
            <>
              <div className="border-t border-border my-2" />
              <div className="space-y-0.5">
                {prefs.savedViews.map((view) => (
                  <div
                    key={view.id}
                    className={`flex items-center gap-1 rounded px-1.5 py-1 cursor-pointer transition-colors ${
                      prefs.activeViewId === view.id ? "bg-accent text-accent-foreground" : "hover:bg-accent/30"
                    }`}
                    onClick={() => applyView(view)}
                  >
                    <span className="text-xs flex-1 truncate">{view.name}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteView(view.id); }}
                      className="text-muted-foreground hover:text-destructive p-0.5 flex-shrink-0"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
}

// ── Group Section ────────────────────────────────────────────────────

function GroupSection({
  group,
  level,
  collapsedGroups,
  toggleGroupCollapse,
  expandedJobs,
  toggleJob,
  glossaryExpanded,
  toggleGlossary,
  onCancel,
  onGlossaryConfirmed,
}: {
  group: JobGroup;
  level: number;
  collapsedGroups: Set<string>;
  toggleGroupCollapse: (key: string) => void;
  expandedJobs: string[];
  toggleJob: (id: string) => void;
  glossaryExpanded: string[];
  toggleGlossary: (id: string) => void;
  onCancel: (id: string) => void;
  onGlossaryConfirmed?: () => void;
}) {
  const groupKey = `${level}-${group.key}`;
  const isCollapsed = collapsedGroups.has(groupKey);
  const count = countJobsInGroup(group);

  // No label = flat/ungrouped → render jobs directly
  if (!group.label) {
    return (
      <>
        {group.jobs.map((job) => (
          <JobCard
            key={job.job_id}
            job={job}
            isExpanded={expandedJobs.includes(job.job_id)}
            onToggle={() => toggleJob(job.job_id)}
            glossaryExpanded={glossaryExpanded.includes(job.job_id)}
            onToggleGlossary={() => toggleGlossary(job.job_id)}
            onCancel={onCancel}
            onGlossaryConfirmed={onGlossaryConfirmed}
          />
        ))}
      </>
    );
  }

  return (
    <div className={level > 0 ? "ml-3" : ""}>
      <button
        onClick={() => toggleGroupCollapse(groupKey)}
        className="flex items-center gap-2 text-sm py-1.5 text-muted-foreground hover:text-foreground transition-colors w-full"
      >
        {isCollapsed ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        <span className={level === 0 ? "font-semibold text-foreground text-sm" : "font-medium text-xs"}>
          {group.label}
        </span>
        <Badge variant="secondary" className="h-4 text-[10px] px-1.5">{count}</Badge>
      </button>

      {!isCollapsed && (
        <div className="space-y-2 mt-1">
          {group.subGroups
            ? group.subGroups.map((sub) => (
                <GroupSection
                  key={sub.key}
                  group={sub}
                  level={level + 1}
                  collapsedGroups={collapsedGroups}
                  toggleGroupCollapse={toggleGroupCollapse}
                  expandedJobs={expandedJobs}
                  toggleJob={toggleJob}
                  glossaryExpanded={glossaryExpanded}
                  toggleGlossary={toggleGlossary}
                  onCancel={onCancel}
                  onGlossaryConfirmed={onGlossaryConfirmed}
                />
              ))
            : group.jobs.map((job) => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  isExpanded={expandedJobs.includes(job.job_id)}
                  onToggle={() => toggleJob(job.job_id)}
                  glossaryExpanded={glossaryExpanded.includes(job.job_id)}
                  onToggleGlossary={() => toggleGlossary(job.job_id)}
                  onCancel={onCancel}
                  onGlossaryConfirmed={onGlossaryConfirmed}
                />
              ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export function TaskWorkbenchSection({
  jobs,
  onCancelJob,
  onGlossaryConfirmed,
}: TaskWorkbenchSectionProps) {
  const { t } = useLanguage();
  const [viewPrefs, setViewPrefs] = useTaskViewPreferences();

  // Track which Job cards are expanded (by job_id)
  const [expandedJobs, setExpandedJobs] = useState<string[]>([]);
  // Track which per-job glossary sections are expanded
  const [expandedGlossaries, setExpandedGlossaries] = useState<string[]>([]);
  // Track collapsed group sections
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const groups = useMemo(
    () => groupJobs(jobs, viewPrefs.grouping, viewPrefs.filter, t),
    [jobs, viewPrefs.grouping, viewPrefs.filter, t]
  );

  const toggleJob = (jobId: string) => {
    setExpandedJobs((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  const toggleGlossary = (jobId: string) => {
    setExpandedGlossaries((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  const toggleGroupCollapse = useCallback((key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const expandAll = () => {
    setExpandedJobs(jobs.map((j) => j.job_id));
    setCollapsedGroups(new Set());
  };

  const collapseAll = () => {
    setExpandedJobs([]);
  };

  const totalFiltered = groups.reduce((sum, g) => sum + countJobsInGroup(g), 0);

  return (
    <div className="px-14 py-14 space-y-4 flex flex-col min-h-0 flex-1 overflow-x-hidden">
          {jobs.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="size-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">{t('tasks.empty')}</p>
            </div>
          ) : (
            <>
              {totalFiltered === 0 ? (
                <div className="text-center py-8">
                  <TaskListToolbar prefs={viewPrefs} onChange={setViewPrefs} jobs={jobs} t={t} />
                  <Search className="size-10 text-muted-foreground mx-auto mb-2 mt-4" />
                  <p className="text-muted-foreground text-sm">{t('tasks.noResults')}</p>
                </div>
              ) : (
                <div className="space-y-2 overflow-y-auto overflow-x-hidden min-h-0 flex-1">
                  <TaskListToolbar prefs={viewPrefs} onChange={setViewPrefs} jobs={jobs} t={t} />
                  {groups.map((group) => (
                    <GroupSection
                      key={group.key}
                      group={group}
                      level={0}
                      collapsedGroups={collapsedGroups}
                      toggleGroupCollapse={toggleGroupCollapse}
                      expandedJobs={expandedJobs}
                      toggleJob={toggleJob}
                      glossaryExpanded={expandedGlossaries}
                      toggleGlossary={toggleGlossary}
                      onCancel={onCancelJob}
                      onGlossaryConfirmed={onGlossaryConfirmed}
                    />
                  ))}
                </div>
              )}
            </>
          )}
    </div>
  );
}

// ── Per-file Job Card ────────────────────────────────────────────────

interface JobCardProps {
  job: Job;
  isExpanded: boolean;
  onToggle: () => void;
  glossaryExpanded: boolean;
  onToggleGlossary: () => void;
  onCancel: (jobId: string) => void;
  onGlossaryConfirmed?: () => void;
}

function JobCard({
  job,
  isExpanded,
  onToggle,
  glossaryExpanded,
  onToggleGlossary,
  onCancel,
  onGlossaryConfirmed,
}: JobCardProps) {
  const { t } = useLanguage();
  const runs = job.language_runs || [];
  const doneRuns = runs.filter((r) => r.status === 'done' && r.download_url);
  const hasDoneRuns = doneRuns.length > 0;

  const glossaryColumns = job.glossary_exports?.columns || [];
  const glossaryRows = job.glossary_exports?.rows || [];

  return (
    <div className="bg-card border border-border rounded-xl shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)] hover:shadow-md hover:bg-accent/20 transition-[box-shadow,background-color] duration-300 ease-out px-5 py-3.5 overflow-hidden">
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <div>
          {/* ── Job Header ── */}
          <div className="flex items-center justify-between gap-4">
            <CollapsibleTrigger className="flex items-center gap-3 min-w-0 shrink">
              {isExpanded ? (
                <ChevronDown className="size-4 text-muted-foreground flex-shrink-0" />
              ) : (
                <ChevronRight className="size-4 text-muted-foreground flex-shrink-0" />
              )}
              <span className="font-semibold text-sm truncate min-w-0">{job.filename || t('tasks.empty')}</span>
            </CollapsibleTrigger>

            <div className="flex items-center gap-2 flex-shrink-0">
              {job.status === 'queued' && (
                <Button variant="outline" size="sm" onClick={() => onCancel(job.job_id)}>
                  {t('common.cancel')}
                </Button>
              )}
              <StepBadge steps={getJobSteps(job, t)} />
            </div>
          </div>


          {/* ── Collapsible Content: Phase Cards ── */}
          <CollapsibleContent>
            <div className="mt-2 pt-2 border-t border-border">
              <div className="flex flex-col gap-2">
                {getJobPhases(job).filter(p => p.status !== 'hidden').map((phase) => {
                  // Phase 1: Glossary
                  if (phase.id === 'glossary') {
                    const termCount = job.glossary?.terms?.length ?? 0;
                    const desc = phase.status === 'done'
                      ? `${termCount} ${t('phase.glossary.descDone')}`
                      : '';
                    const glossaryTitle = t('phase.glossary.title');

                    if (job.status === 'awaiting_glossary_review' && onGlossaryConfirmed) {
                      return (
                        <GlossaryReviewStep
                          key={phase.id}
                          job={job}
                          onConfirmed={onGlossaryConfirmed}
                          title={glossaryTitle}
                          description={desc}
                        />
                      );
                    }
                    if (job.status !== 'awaiting_glossary_review' && job.glossary?.terms && job.glossary.terms.length > 0) {
                      return (
                        <GlossaryReviewStep
                          key={phase.id}
                          job={job}
                          readOnly
                          title={glossaryTitle}
                          description={desc}
                        />
                      );
                    }

                    // Pending glossary phase — show as PhaseCard without content
                    return (
                      <PhaseCard
                        key={phase.id}
                        icon={<BookOpen className="size-4" />}
                        title={glossaryTitle}
                        description={desc}
                        status={phase.status as 'pending' | 'active' | 'done'}
                      />
                    );
                  }

                  // Phase 2: Translation
                  if (phase.id === 'translation') {
                    const langCount = runs.length;
                    const doneCount = runs.filter(r => r.status === 'done').length;
                    const desc = phase.status === 'active'
                      ? `${langCount} ${t('phase.translation.descActive')}`
                      : phase.status === 'done'
                        ? `${doneCount} ${t('phase.translation.descDone')}`
                        : '';
                    return (
                      <PhaseCard
                        key={phase.id}
                        icon={<Globe className="size-4" />}
                        title={t('phase.translation.title')}
                        description={desc}
                        status={phase.status as 'pending' | 'active' | 'done'}
                      >
                        {runs.length > 0 && (
                          <LanguageRunTable
                            runs={runs}
                            sourceFilename={job.filename}
                          />
                        )}
                      </PhaseCard>
                    );
                  }


                  return null;
                })}
              </div>
            </div>
          </CollapsibleContent>

        </div>
      </Collapsible>
    </div>
  );
}

// ── Inline diff helpers ──────────────────────────────────────────────

type DiffOp = { type: 'equal' | 'delete' | 'insert'; text: string };

/** LCS-based character-level diff between two strings. */
function charDiff(before: string, after: string): DiffOp[] {
  const m = before.length;
  const n = after.length;

  // Build LCS length table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = before[i - 1] === after[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to build diff ops
  const ops: DiffOp[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && before[i - 1] === after[j - 1]) {
      ops.push({ type: 'equal', text: before[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.push({ type: 'insert', text: after[j - 1] });
      j--;
    } else {
      ops.push({ type: 'delete', text: before[i - 1] });
      i--;
    }
  }
  ops.reverse();

  // Merge consecutive ops of the same type
  const merged: DiffOp[] = [];
  for (const op of ops) {
    if (merged.length > 0 && merged[merged.length - 1].type === op.type) {
      merged[merged.length - 1].text += op.text;
    } else {
      merged.push({ ...op });
    }
  }
  return merged;
}

function InlineDiff({ before, after }: { before: string; after: string }) {
  const ops = charDiff(before, after);
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

// ── Single language run row ──────────────────────────────────────────

function LanguageRunTable({ runs, sourceFilename }: { runs: LanguageRun[]; sourceFilename?: string }) {
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
                      <span className="text-muted-foreground flex-shrink-0 w-8 text-right">{Math.round(run.percent)}%</span>
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
                    <a
                      href={run.draft_download_url}
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-[11px] font-medium bg-muted text-foreground px-2 py-0.5 rounded-md hover:bg-muted/80 transition-colors border border-border"
                    >
                      <Download className="size-3" />
                      {t('review.translated')}
                    </a>
                  )}
                  <a
                    href={run.download_url}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-[11px] font-medium bg-foreground text-background px-2 py-0.5 rounded-md hover:bg-foreground/90 transition-colors"
                  >
                    <Download className="size-3" />
                    {run.draft_download_url ? t('review.reviewed') : t('common.download')}
                  </a>
                </div>
              )}

              {/* Review count + export icon */}
              {hasReview && (
                <div className="flex items-center gap-1.5 flex-shrink-0 text-[11px] text-muted-foreground">
                  <span className="cursor-pointer hover:text-foreground transition-colors">
                    {t('review.title')} ({run.review_changes!.length})
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
                <div className="space-y-2 max-h-64 overflow-y-auto overflow-x-hidden">
                  {run.review_changes!.map((c) => (
                    <div key={c.block_id} className="border border-border rounded p-2 text-xs space-y-1 bg-card min-w-0">
                      {c.source_text && (
                        <p className="text-muted-foreground truncate">{t('review.original')}: {c.source_text}</p>
                      )}
                      <p className="text-foreground leading-relaxed break-all">
                        <InlineDiff before={c.before} after={c.after} />
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
