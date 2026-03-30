import type { Job } from "../types/translation";
import type { Step } from "../components/StepIndicator";

// ── Phase derivation ────────────────────────────────────────────────

export type PhaseStatus = 'pending' | 'active' | 'done' | 'hidden';

export interface PhaseInfo {
  id: 'glossary' | 'translation' | 'review';
  status: PhaseStatus;
}

export function getJobPhases(job: Job): PhaseInfo[] {
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

export function getJobSteps(job: Job, t: (key: string) => string): Step[] {
  const s = job.status;
  const isError = s === 'error';

  type S = Step['status'];
  const stepStatus = (doneWhen: string[], activeWhen: string[]): S => {
    if (isError && activeWhen.includes(s)) return 'error';
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
