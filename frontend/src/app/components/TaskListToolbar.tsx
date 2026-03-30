import { useState, useMemo, useEffect, useRef } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "./ui/popover";
import type { Job } from "../types/translation";
import {
  Search,
  Filter,
  ChevronsDownUp,
  Bookmark,
  Plus,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  getAvailableFileTypes,
  type GroupByKey,
  type TaskViewPreferences,
  type SavedView,
  type SortDirection,
} from "../utils/taskGrouping";

// ── Grouping rows with drag & drop ──────────────────────────────────

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
  sortDirections: [SortDirection, SortDirection];
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

// ── Main Toolbar ────────────────────────────────────────────────────

export function TaskListToolbar({
  prefs,
  onChange,
  jobs,
  t,
  onDelete,
}: {
  prefs: TaskViewPreferences;
  onChange: (update: Partial<TaskViewPreferences>) => void;
  jobs: Job[];
  t: (k: string) => string;
  onDelete?: () => void;
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
              <span className="bg-foreground text-background text-xs font-medium rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">{filterCount}</span>
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

      {/* Delete mode toggle */}
      {onDelete && (
        <button
          onClick={onDelete}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-md hover:bg-accent/50 flex-shrink-0"
        >
          <Trash2 className="size-3.5" />
          {t('common.delete')}
        </button>
      )}
    </div>
  );
}
