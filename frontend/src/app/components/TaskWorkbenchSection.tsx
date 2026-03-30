import { useState, useMemo, useCallback } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { Job } from "../types/translation";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  BookOpen,
  Globe,
  Search,
  Trash2,
  Check,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import { useLanguage } from "../contexts/LanguageContext";
import { GlossaryReviewStep } from "./GlossaryReviewStep";
import { PhaseCard } from "./PhaseCard";
import { StepBadge } from "./StepIndicator";
import { TaskListToolbar } from "./TaskListToolbar";
import { LanguageRunTable } from "./LanguageRunTable";
import { getJobPhases, getJobSteps } from "../utils/jobPhases";
import {
  groupJobs,
  countJobsInGroup,
  useTaskViewPreferences,
  type TaskViewPreferences,
  type JobGroup,
} from "../utils/taskGrouping";

interface TaskWorkbenchSectionProps {
  jobs: Job[];
  onCancelJob: (jobId: string) => void;
  onDeleteJobs: (jobIds: string[]) => void;
  onGlossaryConfirmed?: () => void;
}

// ── Group Section (recursive) ───────────────────────────────────────

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
  deleteMode,
  selectedJobs,
  onToggleSelect,
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
  deleteMode: boolean;
  selectedJobs: Set<string>;
  onToggleSelect: (id: string) => void;
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
            deleteMode={deleteMode}
            isSelected={selectedJobs.has(job.job_id)}
            onToggleSelect={onToggleSelect}
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
        <Badge variant="secondary" className="h-4 text-xs px-1.5">{count}</Badge>
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
                  deleteMode={deleteMode}
                  selectedJobs={selectedJobs}
                  onToggleSelect={onToggleSelect}
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
                  deleteMode={deleteMode}
                  isSelected={selectedJobs.has(job.job_id)}
                  onToggleSelect={onToggleSelect}
                  onGlossaryConfirmed={onGlossaryConfirmed}
                />
              ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────

export function TaskWorkbenchSection({
  jobs,
  onCancelJob,
  onDeleteJobs,
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

  // Delete mode
  const [deleteMode, setDeleteMode] = useState(false);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());

  const toggleSelectJob = (jobId: string) => {
    setSelectedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const enterDeleteMode = () => { setDeleteMode(true); setSelectedJobs(new Set()); };
  const exitDeleteMode = () => { setDeleteMode(false); setSelectedJobs(new Set()); };
  const confirmDelete = () => {
    if (selectedJobs.size > 0) onDeleteJobs([...selectedJobs]);
    exitDeleteMode();
  };

  const totalFiltered = groups.reduce((sum, g) => sum + countJobsInGroup(g), 0);

  return (
    <div className="px-6 py-5 space-y-4 flex flex-col min-h-0 flex-1 overflow-x-hidden">
          {jobs.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <FileText className="size-10 text-muted-foreground/40 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">{t('tasks.empty')}</p>
                <p className="text-xs text-muted-foreground/60 mt-1">{t('tasks.emptyHint')}</p>
              </div>
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
                <div className="space-y-3 overflow-y-auto overflow-x-hidden min-h-0 flex-1">
                  {deleteMode ? (
                    <div className="flex items-center justify-between pb-3 mb-1 flex-shrink-0">
                      <span className="text-sm text-muted-foreground">
                        {selectedJobs.size > 0
                          ? t('tasks.selected').replace('{count}', String(selectedJobs.size))
                          : t('tasks.selectHint')}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={exitDeleteMode}
                        >
                          {t('common.cancel')}
                        </Button>
                        <Button
                          size="sm"
                          className="h-7 text-xs bg-destructive hover:bg-destructive/90 text-white"
                          disabled={selectedJobs.size === 0}
                          onClick={confirmDelete}
                        >
                          <Trash2 className="size-3 mr-1" />
                          {t('common.delete')} ({selectedJobs.size})
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <TaskListToolbar prefs={viewPrefs} onChange={setViewPrefs} jobs={jobs} t={t} onDelete={enterDeleteMode} />
                  )}
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
                      deleteMode={deleteMode}
                      selectedJobs={selectedJobs}
                      onToggleSelect={toggleSelectJob}
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

// ── Per-file Job Card ───────────────────────────────────────────────

interface JobCardProps {
  job: Job;
  isExpanded: boolean;
  onToggle: () => void;
  glossaryExpanded: boolean;
  onToggleGlossary: () => void;
  onCancel: (jobId: string) => void;
  deleteMode: boolean;
  isSelected: boolean;
  onToggleSelect: (jobId: string) => void;
  onGlossaryConfirmed?: () => void;
}

function JobCard({
  job,
  isExpanded,
  onToggle,
  glossaryExpanded,
  onToggleGlossary,
  onCancel,
  deleteMode,
  isSelected,
  onToggleSelect,
  onGlossaryConfirmed,
}: JobCardProps) {
  const { t } = useLanguage();
  const runs = job.language_runs || [];

  return (
    <div className="bg-card border border-border rounded-xl shadow-[0_1px_3px_rgba(0,0,0,0.08),0_1px_2px_rgba(0,0,0,0.06)] hover:shadow-md hover:bg-accent/20 transition-[box-shadow,background-color] duration-300 ease-out px-5 py-3.5 overflow-hidden">
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <div>
          {/* ── Job Header ── */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0 shrink">
              {deleteMode && (
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleSelect(job.job_id); }}
                  className={`size-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                    isSelected
                      ? "bg-foreground border-foreground text-background"
                      : "border-border hover:border-muted-foreground"
                  }`}
                >
                  {isSelected && <Check className="size-2.5" />}
                </button>
              )}
              <CollapsibleTrigger className="flex items-center gap-3 min-w-0 shrink">
                {isExpanded ? (
                  <ChevronDown className="size-4 text-muted-foreground flex-shrink-0" />
                ) : (
                  <ChevronRight className="size-4 text-muted-foreground flex-shrink-0" />
                )}
                <span className="font-semibold text-sm truncate min-w-0">{job.filename || t('tasks.empty')}</span>
              </CollapsibleTrigger>
            </div>

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
