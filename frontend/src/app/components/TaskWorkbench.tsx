import { Card } from "./ui/card";
import { Progress } from "./ui/progress";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import type { TranslationFile, Job, LanguageRun } from "../types/translation";
import { Download, FileText, CheckCircle2, Loader2, Clock, XCircle, Plus, BookOpen } from "lucide-react";

interface TaskWorkbenchProps {
  jobs: Job[];
  files: TranslationFile[];
  selectedLanguageCodes: string[];
  onCancelJob: (jobId: string) => void;
  onClearDone: () => void;
  onNewTask: () => void;
  onReviewGlossary: (jobId: string) => void;
}

const STATUS_LABELS: Record<string, string> = {
  queued: "等待中",
  pending: "等待中",
  parsing: "解析中",
  terminology: "术语提取中",
  awaiting_glossary_review: "待术语确认",
  translating: "翻译中",
  reviewing: "审校中",
  rebuilding: "重建中",
  done: "已完成",
  error: "失败",
  cancelled: "已取消",
};

function statusLabel(status: string) {
  return STATUS_LABELS[status] || status || "未知";
}

function isActive(status: string) {
  return ["queued", "pending", "parsing", "terminology", "translating", "reviewing", "rebuilding"].includes(status);
}

function isAwaitingReview(status: string) {
  return status === "awaiting_glossary_review";
}

function getStatusColor(status: string) {
  if (status === "done") return "bg-green-100 text-green-800";
  if (status === "error") return "bg-red-100 text-red-800";
  if (status === "cancelled") return "bg-gray-100 text-gray-800";
  if (isAwaitingReview(status)) return "bg-yellow-100 text-yellow-800";
  if (isActive(status)) return "bg-blue-100 text-blue-800";
  return "bg-gray-100 text-gray-800";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "done") return <CheckCircle2 className="size-5 text-green-600" />;
  if (status === "error") return <XCircle className="size-5 text-red-600" />;
  if (isAwaitingReview(status)) return <BookOpen className="size-5 text-yellow-600" />;
  if (isActive(status)) return <Loader2 className="size-5 text-blue-600 animate-spin" />;
  return <Clock className="size-5 text-gray-400" />;
}

export function TaskWorkbench({ jobs, files, selectedLanguageCodes, onCancelJob, onClearDone, onNewTask, onReviewGlossary }: TaskWorkbenchProps) {
  const activeJobs = jobs.filter((j) => isActive(j.status) || isAwaitingReview(j.status)).length;
  const completedRuns = jobs.reduce((sum, j) => sum + (j.language_runs || []).filter((r) => r.status === "done").length, 0);
  const totalRuns = jobs.reduce((sum, j) => sum + (j.language_runs || []).length, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold mb-2">任务工作台</h2>
          <p className="text-gray-600">实时查看每个翻译任务的进度</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onNewTask}>
            <Plus className="size-4 mr-1" />新建任务
          </Button>
          <Button variant="outline" size="sm" onClick={onClearDone}>清除已完成</Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">当前文件</p>
              <p className="text-2xl font-semibold mt-1">{files.length}</p>
            </div>
            <FileText className="size-8 text-gray-400" />
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">目标语言</p>
              <p className="text-2xl font-semibold mt-1">{selectedLanguageCodes.length}</p>
            </div>
            <div className="size-8 bg-blue-100 rounded-full flex items-center justify-center">
              <span className="text-blue-600 font-semibold text-lg">🌐</span>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">进行中</p>
              <p className="text-2xl font-semibold mt-1">{activeJobs}</p>
            </div>
            {activeJobs > 0 ? <Loader2 className="size-8 text-blue-600 animate-spin" /> : <Clock className="size-8 text-gray-300" />}
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">已完成版本</p>
              <p className="text-2xl font-semibold mt-1">{completedRuns}</p>
              <p className="text-xs text-gray-400">共 {totalRuns} 个语言版本</p>
            </div>
            <CheckCircle2 className="size-8 text-green-600" />
          </div>
        </Card>
      </div>

      {/* Job Cards */}
      {jobs.length > 0 ? (
        <div className="space-y-6">
          {jobs.map((job) => (
            <JobCard key={job.job_id} job={job} onCancel={onCancelJob} onReviewGlossary={onReviewGlossary} />
          ))}
        </div>
      ) : (
        <Card className="p-6">
          <div className="text-center py-12">
            <Clock className="size-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">任务开始后会出现在这里</p>
            <p className="text-sm text-gray-400 mt-1">
              你会看到共享术语表、每种语言的阶段进度，以及完成后的直接下载入口。
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

/** Format an ISO timestamp to a local readable string */
function formatTime(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
}

/** Compute human-readable duration between two ISO timestamps */
function formatDuration(start?: string | null, end?: string | null): string {
  if (!start || !end) return "-";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (isNaN(ms) || ms < 0) return "-";
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}秒`;
  const mins = Math.floor(secs / 60);
  const remainSecs = secs % 60;
  if (mins < 60) return `${mins}分${remainSecs}秒`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hours}时${remainMins}分`;
}

function JobCard({ job, onCancel, onReviewGlossary }: { job: Job; onCancel: (id: string) => void; onReviewGlossary: (id: string) => void }) {
  const glossaryColumns = job.glossary_exports?.columns || [];
  const glossaryRows = job.glossary_exports?.rows || [];
  const showCancel = job.status === "queued";
  const showReviewButton = job.status === "awaiting_glossary_review";

  return (
    <Card className="p-6">
      {/* Job Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <StatusIcon status={job.status} />
          <div>
            <h3 className="font-semibold text-lg">{job.filename || "未命名文件"}</h3>
            <p className="text-sm text-gray-600">
              {job.detail || "等待后端处理"} {job.current_range ? `· ${job.current_range}` : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={getStatusColor(job.status)}>{statusLabel(job.status)}</Badge>
          {showCancel && (
            <Button variant="outline" size="sm" onClick={() => onCancel(job.job_id)}>取消排队</Button>
          )}
          {showReviewButton && (
            <Button
              size="sm"
              className="bg-yellow-500 hover:bg-yellow-600 text-white"
              onClick={() => onReviewGlossary(job.job_id)}
            >
              <BookOpen className="size-4 mr-1" />
              审核术语表
            </Button>
          )}
        </div>
      </div>

      {/* Overall Progress */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">整体进度</span>
          <span className="font-medium">{job.percent || 0}%</span>
        </div>
        <Progress value={job.percent || 0} className="h-2" />
      </div>

      {/* Job Meta */}
      <div className="grid grid-cols-3 gap-4 mb-4 py-3 border-t border-b">
        <div>
          <p className="text-xs text-gray-500">任务 ID</p>
          <p className="text-sm font-medium mt-1">{job.job_id}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">目标语言</p>
          <p className="text-sm font-medium mt-1">{(job.target_languages || []).join(", ") || "-"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">已完成</p>
          <p className="text-sm font-medium mt-1">
            {(job.language_runs || []).filter((r) => r.status === "done").length}/{(job.language_runs || []).length}
          </p>
        </div>
      </div>

      {/* Time Info */}
      <div className="grid grid-cols-3 gap-4 mb-4 py-3 border-b text-xs">
        <div>
          <p className="text-gray-500">创建时间</p>
          <p className="font-medium mt-1">{formatTime(job.created_at)}</p>
        </div>
        <div>
          <p className="text-gray-500">完成时间</p>
          <p className="font-medium mt-1">{formatTime(job.completed_at)}</p>
        </div>
        <div>
          <p className="text-gray-500">耗时</p>
          <p className="font-medium mt-1">{formatDuration(job.started_at, job.completed_at)}</p>
        </div>
      </div>

      {/* Glossary Table */}
      {glossaryRows.length > 0 && (
        <div className="mb-4">
          <h4 className="font-semibold mb-3 flex items-center gap-2">
            共享术语表
            <Badge variant="secondary">{glossaryRows.length} 个术语</Badge>
          </h4>
          <div className="border rounded-lg overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {glossaryColumns.map((col) => (
                    <TableHead key={col}>{col}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {glossaryRows.slice(0, 12).map((row, idx) => (
                  <TableRow key={idx}>
                    {glossaryColumns.map((col) => (
                      <TableCell key={col}>{String(row[col] ?? "")}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Language Runs */}
      <div>
        <h4 className="font-semibold mb-3">翻译任务</h4>
        <div className="space-y-3">
          {(job.language_runs || []).map((run) => (
            <LanguageRunCard key={`${job.job_id}-${run.target_language}`} run={run} />
          ))}
        </div>
      </div>
    </Card>
  );
}

function LanguageRunCard({ run }: { run: LanguageRun }) {
  return (
    <Card className="p-4 border-2">
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusIcon status={run.status} />
            <div>
              <h4 className="font-semibold">{run.target_language || "未知语言"}</h4>
              <p className="text-sm text-gray-600">{run.detail || "等待处理"}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge className={getStatusColor(run.status)}>{statusLabel(run.status)}</Badge>
            {run.status === "done" && run.download_url && (
              <a href={run.download_url} className="inline-flex items-center gap-1 text-sm font-medium bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700 transition-colors">
                <Download className="size-4" />
                下载译文
              </a>
            )}
          </div>
        </div>

        {/* Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">
              {run.current_range || (isActive(run.status) ? "处理中..." : "已结束")}
            </span>
            <span className="font-medium">{run.percent || 0}%</span>
          </div>
          <Progress value={run.percent || 0} className="h-2" />
        </div>

        {/* Details */}
        {run.status !== "queued" && (
          <div className="grid grid-cols-3 gap-4 pt-2 border-t">
            <div>
              <p className="text-xs text-gray-500">段落进度</p>
              <p className="text-sm font-medium mt-1">
                {run.segments_total ? `${run.segments_done}/${run.segments_total} 段` : "等待分段"}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">当前阶段</p>
              <p className="text-sm font-medium mt-1">{statusLabel(run.status)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">状态</p>
              <p className="text-sm font-medium mt-1">{run.error_message || (run.status === "done" ? "已完成" : "进行中")}</p>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
