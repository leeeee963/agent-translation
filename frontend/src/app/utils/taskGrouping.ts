/**
 * Multi-dimensional grouping, filtering, and search for translation tasks.
 * Pure utility — no React dependencies except the hook at the bottom.
 */

import { useState, useCallback } from "react";
import type { Job, JobStatus } from "../types/translation";

// ── Types ────────────────────────────────────────────────────────────

export type GroupByKey = "none" | "status" | "time" | "fileType";
export type SortDirection = "asc" | "desc";

export interface GroupingConfig {
  primary: GroupByKey;
  secondary: GroupByKey;
  primarySort: SortDirection;
  secondarySort: SortDirection;
}

export interface TaskFilterState {
  search: string;
  statuses: string[];
  fileTypes: string[];
  timeBuckets: string[];
}

export interface SavedView {
  id: string;
  name: string;
  grouping: GroupingConfig;
  filter: Omit<TaskFilterState, "search">;
}

export interface TaskViewPreferences {
  grouping: GroupingConfig;
  filter: TaskFilterState;
  savedViews: SavedView[];
  activeViewId: string | null;
}

export interface JobGroup {
  key: string;
  label: string;
  jobs: Job[];
  subGroups?: JobGroup[];
}

// ── Helpers ──────────────────────────────────────────────────────────

export function getStatusCategory(
  status: JobStatus | string
): "active" | "error" | "completed" {
  if (status === "error") return "error";
  if (["done", "cancelled"].includes(status)) return "completed";
  return "active";
}

export function getFileExtension(filename: string): string {
  const match = filename.match(/\.[^.]+$/);
  return match ? match[0].toLowerCase() : "";
}

interface BucketResult {
  key: string;
  label: string;
  sortOrder: number;
}

export function getTimeBucket(
  isoDate: string | null | undefined,
  t: (k: string) => string
): BucketResult {
  if (!isoDate) return { key: "unknown", label: t("tasks.groupTime.older"), sortOrder: 99 };

  const d = new Date(isoDate);
  if (isNaN(d.getTime()))
    return { key: "unknown", label: t("tasks.groupTime.older"), sortOrder: 99 };

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);

  const start7Days = new Date(startOfToday);
  start7Days.setDate(start7Days.getDate() - 7);

  const start30Days = new Date(startOfToday);
  start30Days.setDate(start30Days.getDate() - 30);

  if (d >= startOfToday)
    return { key: "today", label: t("tasks.groupTime.today"), sortOrder: 0 };
  if (d >= startOfYesterday)
    return { key: "yesterday", label: t("tasks.groupTime.yesterday"), sortOrder: 1 };
  if (d >= start7Days)
    return { key: "last7Days", label: t("tasks.groupTime.last7Days"), sortOrder: 2 };
  if (d >= start30Days)
    return { key: "last30Days", label: t("tasks.groupTime.last30Days"), sortOrder: 3 };
  return { key: "older", label: t("tasks.groupTime.older"), sortOrder: 4 };
}

// ── Classifiers ──────────────────────────────────────────────────────

type Classifier = (
  job: Job,
  t: (k: string) => string
) => BucketResult;

const classifiers: Record<Exclude<GroupByKey, "none">, Classifier> = {
  status: (job, t) => {
    const cat = getStatusCategory(job.status);
    const labels: Record<string, string> = {
      active: t("tasks.groupStatus.active"),
      error: t("tasks.groupStatus.error"),
      completed: t("tasks.groupStatus.completed"),
    };
    const order: Record<string, number> = { active: 0, error: 1, completed: 2 };
    return { key: cat, label: labels[cat], sortOrder: order[cat] };
  },
  time: (job, t) => getTimeBucket(job.created_at || job.completed_at || job.started_at, t),
  fileType: (job, t) => {
    const ext = getFileExtension(job.filename);
    return {
      key: ext || "unknown",
      label: ext ? ext.replace(".", "").toUpperCase() : t("tasks.groupFileType.unknown"),
      sortOrder: 0,
    };
  },
};

// ── Sort ─────────────────────────────────────────────────────────────

function sortJobs(jobs: Job[]): Job[] {
  const latest = (j: Job) =>
    [j.completed_at, j.started_at, j.created_at].filter(Boolean).sort().pop() || "";
  return [...jobs].sort((a, b) => latest(b).localeCompare(latest(a)));
}

// ── Main grouping function ───────────────────────────────────────────

export function groupJobs(
  jobs: Job[],
  config: GroupingConfig,
  filter: TaskFilterState,
  t: (k: string) => string
): JobGroup[] {
  // Step 1: Filter
  let filtered = jobs;

  if (filter.search) {
    const q = filter.search.toLowerCase();
    filtered = filtered.filter((j) => j.filename.toLowerCase().includes(q));
  }
  if (filter.statuses.length > 0) {
    filtered = filtered.filter((j) =>
      filter.statuses.includes(getStatusCategory(j.status))
    );
  }
  if (filter.fileTypes.length > 0) {
    filtered = filtered.filter((j) =>
      filter.fileTypes.includes(getFileExtension(j.filename))
    );
  }
  if (filter.timeBuckets.length > 0) {
    filtered = filtered.filter((j) => {
      const bucket = getTimeBucket(j.created_at || j.completed_at || j.started_at, t);
      return filter.timeBuckets.includes(bucket.key);
    });
  }

  // Step 2: No grouping — flat list
  if (config.primary === "none") {
    return [{ key: "all", label: "", jobs: sortJobs(filtered) }];
  }

  // Step 3: Primary grouping
  const primaryClassifier = classifiers[config.primary];
  const primaryMap = new Map<
    string,
    { label: string; sortOrder: number; jobs: Job[] }
  >();

  for (const job of filtered) {
    const { key, label, sortOrder } = primaryClassifier(job, t);
    let entry = primaryMap.get(key);
    if (!entry) {
      entry = { label, sortOrder, jobs: [] };
      primaryMap.set(key, entry);
    }
    entry.jobs.push(job);
  }

  // Step 4: Convert to JobGroup[], apply secondary grouping
  const groups: (JobGroup & { _sortOrder: number })[] = [];

  for (const [key, val] of primaryMap) {
    if (config.secondary !== "none" && config.secondary !== config.primary) {
      const secondaryClassifier = classifiers[config.secondary];
      const subMap = new Map<
        string,
        { label: string; sortOrder: number; jobs: Job[] }
      >();

      for (const job of val.jobs) {
        const sub = secondaryClassifier(job, t);
        let entry = subMap.get(sub.key);
        if (!entry) {
          entry = { label: sub.label, sortOrder: sub.sortOrder, jobs: [] };
          subMap.set(sub.key, entry);
        }
        entry.jobs.push(job);
      }

      const secDir = config.secondarySort === "desc" ? -1 : 1;
      const subGroups = [...subMap.entries()]
        .map(([sk, sv]) => ({
          key: sk,
          label: sv.label,
          jobs: sortJobs(sv.jobs),
          _sortOrder: sv.sortOrder,
        }))
        .sort((a, b) => secDir * (a._sortOrder - b._sortOrder) || secDir * a.label.localeCompare(b.label))
        .map(({ _sortOrder: _, ...rest }) => rest);

      groups.push({ key, label: val.label, jobs: [], subGroups, _sortOrder: val.sortOrder });
    } else {
      groups.push({ key, label: val.label, jobs: sortJobs(val.jobs), _sortOrder: val.sortOrder });
    }
  }

  const priDir = config.primarySort === "desc" ? -1 : 1;
  groups.sort((a, b) => priDir * (a._sortOrder - b._sortOrder) || priDir * a.label.localeCompare(b.label));
  return groups.map(({ _sortOrder: _, ...rest }) => rest);
}

// ── Count helper ─────────────────────────────────────────────────────

export function countJobsInGroup(group: JobGroup): number {
  if (group.subGroups) {
    return group.subGroups.reduce((sum, sg) => sum + countJobsInGroup(sg), 0);
  }
  return group.jobs.length;
}

// ── Extract available file types from jobs ───────────────────────────

export function getAvailableFileTypes(jobs: Job[]): string[] {
  const types = new Set<string>();
  for (const job of jobs) {
    const ext = getFileExtension(job.filename);
    if (ext) types.add(ext);
  }
  return [...types].sort();
}

// ── Default preferences ──────────────────────────────────────────────

const STORAGE_KEY = "task_view_preferences";

const DEFAULT_PREFS: TaskViewPreferences = {
  grouping: { primary: "status", secondary: "none", primarySort: "asc", secondarySort: "asc" },
  filter: { search: "", statuses: [], fileTypes: [], timeBuckets: [] },
  savedViews: [],
  activeViewId: null,
};

function loadPrefs(): TaskViewPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Merge with defaults to handle missing fields from older versions
      return { ...DEFAULT_PREFS, ...parsed, filter: { ...DEFAULT_PREFS.filter, ...parsed.filter } };
    }
  } catch {
    // ignore
  }
  return { ...DEFAULT_PREFS, filter: { ...DEFAULT_PREFS.filter } };
}

function savePrefs(prefs: TaskViewPreferences) {
  try {
    // Don't persist search text
    const toSave = { ...prefs, filter: { ...prefs.filter, search: "" } };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
  } catch {
    // ignore
  }
}

// ── React hook ───────────────────────────────────────────────────────

export function useTaskViewPreferences(): [
  TaskViewPreferences,
  (update: Partial<TaskViewPreferences>) => void,
] {
  const [prefs, setPrefs] = useState<TaskViewPreferences>(loadPrefs);

  const updatePrefs = useCallback(
    (update: Partial<TaskViewPreferences>) => {
      setPrefs((prev) => {
        const next = {
          ...prev,
          ...update,
          filter: update.filter ? { ...prev.filter, ...update.filter } : prev.filter,
        };
        // If user changes grouping/filter manually, clear activeViewId
        if (update.grouping || (update.filter && !update.activeViewId)) {
          next.activeViewId = null;
        }
        savePrefs(next);
        return next;
      });
    },
    []
  );

  return [prefs, updatePrefs];
}
