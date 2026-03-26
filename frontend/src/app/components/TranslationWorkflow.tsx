import { useState, useEffect, useCallback } from "react";
import { FileUploadStep } from "./FileUploadStep";
import { LanguageSelectionStep } from "./LanguageSelectionStep";
import { PromptEditStep } from "./PromptEditStep";
import { TaskWorkbench } from "./TaskWorkbench";
import { GlossaryReviewStep } from "./GlossaryReviewStep";
import type { TranslationFile, Language, Job } from "../types/translation";
import { fetchLanguages, fetchPrompt, savePrompt, submitJobs, fetchJobs, cancelJob } from "../api";
import { Button } from "./ui/button";
import { ArrowLeft } from "lucide-react";

type Step = "upload" | "language" | "prompt" | "workbench";

const POLL_INTERVAL = 1500;
const VALID_EXTENSIONS = [".pptx", ".srt", ".vtt", ".ass", ".docx", ".doc", ".md", ".json", ".yaml", ".yml", ".po", ".pot", ".xliff", ".xlf", ".xml", ".html", ".htm"];
const USE_GLOSSARY_KEY = "translation_use_glossary";

function getExtension(filename: string) {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}

function loadUseGlossarySetting(): boolean {
  try {
    const stored = localStorage.getItem(USE_GLOSSARY_KEY);
    if (stored === null) return true; // default on
    return stored !== "false";
  } catch {
    return true;
  }
}

function saveUseGlossarySetting(value: boolean) {
  try {
    localStorage.setItem(USE_GLOSSARY_KEY, value ? "true" : "false");
  } catch {
    // ignore
  }
}

export function TranslationWorkflow() {
  const [currentStep, setCurrentStep] = useState<Step>("upload");
  const [files, setFiles] = useState<TranslationFile[]>([]);

  const [availableLanguages, setAvailableLanguages] = useState<Language[]>([]);
  const [selectedLanguageCodes, setSelectedLanguageCodes] = useState<string[]>([]);
  const [loadingLanguages, setLoadingLanguages] = useState(true);

  const [promptValue, setPromptValue] = useState("");
  const [savedPromptValue, setSavedPromptValue] = useState("");
  const [promptPath, setPromptPath] = useState("");
  const [loadingPrompt, setLoadingPrompt] = useState(true);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [dismissedJobIds, setDismissedJobIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Glossary review: if any visible job is awaiting review, show the review step
  const [reviewingJobId, setReviewingJobId] = useState<string | null>(null);

  // Global mode setting (persisted in localStorage)
  const [useGlossary, setUseGlossaryState] = useState<boolean>(loadUseGlossarySetting);

  const [banner, setBanner] = useState<{ type: string; message: string }>({ type: "", message: "" });

  const handleUseGlossaryChange = (value: boolean) => {
    setUseGlossaryState(value);
    saveUseGlossarySetting(value);
  };

  useEffect(() => {
    setLoadingLanguages(true);
    fetchLanguages()
      .then((langs) => setAvailableLanguages(langs))
      .catch((err) => setBanner({ type: "error", message: err.message }))
      .finally(() => setLoadingLanguages(false));
  }, []);

  const loadPrompt = useCallback(async (showStatus = false) => {
    setLoadingPrompt(true);
    try {
      const config = await fetchPrompt();
      setPromptValue(config.content);
      setSavedPromptValue(config.content);
      setPromptPath(config.path || "");
      if (showStatus) setBanner({ type: "success", message: "已从服务端重新加载 Prompt" });
    } catch (err: unknown) {
      setBanner({ type: "error", message: err instanceof Error ? err.message : String(err) });
    } finally {
      setLoadingPrompt(false);
    }
  }, []);

  useEffect(() => { loadPrompt(); }, [loadPrompt]);

  const loadJobs = useCallback(async () => {
    try { setJobs(await fetchJobs()); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadJobs();
    const timer = window.setInterval(loadJobs, POLL_INTERVAL);
    return () => window.clearInterval(timer);
  }, [loadJobs]);

  // Auto-open glossary review when a job enters awaiting_glossary_review state
  useEffect(() => {
    const awaitingJob = jobs.find(
      (j) => j.status === "awaiting_glossary_review" && !dismissedJobIds.includes(j.job_id)
    );
    if (awaitingJob && currentStep === "workbench") {
      setReviewingJobId(awaitingJob.job_id);
    }
  }, [jobs, dismissedJobIds, currentStep]);

  const addFiles = (fileList: FileList) => {
    const next: TranslationFile[] = [];
    Array.from(fileList).forEach((file) => {
      const ext = getExtension(file.name);
      if (!VALID_EXTENSIONS.includes(ext)) {
        setBanner({ type: "error", message: `不支持的文件格式：${file.name}。支持 ${VALID_EXTENSIONS.join(", ")}` });
        return;
      }
      if (!files.some((f) => f.name === file.name && f.size === file.size)) {
        next.push({ id: `${Date.now()}-${file.name}-${file.size}`, name: file.name, size: file.size, file });
      }
    });
    if (next.length) { setFiles((prev) => [...prev, ...next]); setBanner({ type: "", message: "" }); }
  };

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  const toggleLanguage = (code: string) => {
    setSelectedLanguageCodes((prev) => prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]);
  };

  const handleSavePrompt = async () => {
    try {
      await savePrompt(promptValue);
      setSavedPromptValue(promptValue);
      setBanner({ type: "success", message: "Prompt 已保存" });
    } catch (err: unknown) {
      setBanner({ type: "error", message: err instanceof Error ? err.message : String(err) });
    }
  };

  const handleStartTranslation = async () => {
    if (!files.length) { setBanner({ type: "error", message: "请先上传至少一个文件。" }); setCurrentStep("upload"); return; }
    if (!selectedLanguageCodes.length) { setBanner({ type: "error", message: "请至少选择一种目标语言。" }); setCurrentStep("language"); return; }
    setSubmitting(true);
    setBanner({ type: "", message: "" });
    try {
      if (promptValue !== savedPromptValue) { await savePrompt(promptValue); setSavedPromptValue(promptValue); }
      const jobIds = await submitJobs(files.map((f) => f.file), selectedLanguageCodes, useGlossary);
      await loadJobs();
      setCurrentStep("workbench");
      setBanner({ type: "success", message: `已提交 ${jobIds.length} 个任务，正在进入工作台。` });
    } catch (err: unknown) {
      setBanner({ type: "error", message: err instanceof Error ? err.message : String(err) });
    } finally { setSubmitting(false); }
  };

  const handleCancelJob = async (jobId: string) => {
    try { await cancelJob(jobId); await loadJobs(); } catch (err: unknown) {
      setBanner({ type: "error", message: err instanceof Error ? err.message : String(err) });
    }
  };

  const clearDoneJobs = () => {
    const visible = jobs.filter((j) => !dismissedJobIds.includes(j.job_id));
    setDismissedJobIds((prev) => [...prev, ...visible.filter((j) => ["done", "error", "cancelled"].includes(j.status)).map((j) => j.job_id)]);
  };

  const resetComposer = () => { setFiles([]); setSelectedLanguageCodes([]); setCurrentStep("upload"); };
  const goBack = () => { const steps: Step[] = ["upload", "language", "prompt", "workbench"]; const idx = steps.indexOf(currentStep); if (idx > 0) setCurrentStep(steps[idx - 1]); };

  const visibleJobs = jobs.filter((j) => !dismissedJobIds.includes(j.job_id));

  // Job awaiting review (if any)
  const reviewingJob = reviewingJobId
    ? visibleJobs.find((j) => j.job_id === reviewingJobId)
    : null;
  const showGlossaryReview = reviewingJob?.status === "awaiting_glossary_review";

  const handleGlossaryConfirmed = async () => {
    setReviewingJobId(null);
    await loadJobs();
    setBanner({ type: "success", message: "术语已确认，翻译任务已启动。" });
  };

  return (
    <div className="size-full min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {currentStep !== "upload" && currentStep !== "workbench" && (
                <Button variant="ghost" size="sm" onClick={goBack}><ArrowLeft className="size-4" /></Button>
              )}
              <h1 className="text-2xl font-semibold">多语言翻译平台</h1>
            </div>
            {/* Mode indicator (read-only; toggle is in upload step) */}
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>模式：</span>
              <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs">
                {useGlossary ? "术语表模式" : "直接翻译"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <StepIndicator number={1} title="上传文件" active={currentStep === "upload"} completed={currentStep !== "upload"} />
            <div className="flex-1 h-px bg-gray-300 mx-4" />
            <StepIndicator number={2} title="选择语言" active={currentStep === "language"} completed={currentStep === "prompt" || currentStep === "workbench"} />
            <div className="flex-1 h-px bg-gray-300 mx-4" />
            <StepIndicator number={3} title="编辑Prompt" active={currentStep === "prompt"} completed={currentStep === "workbench"} />
            <div className="flex-1 h-px bg-gray-300 mx-4" />
            <StepIndicator number={4} title="任务工作台" active={currentStep === "workbench"} completed={false} />
          </div>
        </div>
      </div>

      {banner.message && (
        <div className="max-w-7xl mx-auto px-6 pt-4">
          <div className={`rounded-lg px-4 py-3 text-sm ${banner.type === "error" ? "bg-red-50 text-red-800 border border-red-200" : banner.type === "success" ? "bg-green-50 text-green-800 border border-green-200" : "bg-blue-50 text-blue-800 border border-blue-200"}`}>
            {banner.message}
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-6 py-8">
        {currentStep === "upload" && <FileUploadStep files={files} onAddFiles={addFiles} onRemoveFile={removeFile} onNext={() => setCurrentStep("language")} useGlossary={useGlossary} onUseGlossaryChange={handleUseGlossaryChange} />}
        {currentStep === "language" && <LanguageSelectionStep availableLanguages={availableLanguages} selectedCodes={selectedLanguageCodes} onToggle={toggleLanguage} loading={loadingLanguages} onNext={() => setCurrentStep("prompt")} />}
        {currentStep === "prompt" && (
          <PromptEditStep
            promptValue={promptValue}
            savedPromptValue={savedPromptValue}
            promptPath={promptPath}
            loading={loadingPrompt}
            onPromptChange={setPromptValue}
            onSave={handleSavePrompt}
            onReload={() => loadPrompt(true)}
            onStartTranslation={handleStartTranslation}
            submitting={submitting}
            selectedLanguages={availableLanguages.filter((l) => selectedLanguageCodes.includes(l.code))}
          />
        )}
        {currentStep === "workbench" && (
          showGlossaryReview && reviewingJob ? (
            <GlossaryReviewStep
              job={reviewingJob}
              onConfirmed={handleGlossaryConfirmed}
            />
          ) : (
            <TaskWorkbench
              jobs={visibleJobs}
              files={files}
              selectedLanguageCodes={selectedLanguageCodes}
              onCancelJob={handleCancelJob}
              onClearDone={clearDoneJobs}
              onNewTask={resetComposer}
              onReviewGlossary={(jobId) => setReviewingJobId(jobId)}
            />
          )
        )}
      </div>
    </div>
  );
}

function StepIndicator({ number, title, active, completed }: { number: number; title: string; active: boolean; completed: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${active ? "bg-blue-600 text-white" : completed ? "bg-green-600 text-white" : "bg-gray-200 text-gray-600"}`}>{number}</div>
      <span className={`text-sm font-medium ${active ? "text-blue-600" : completed ? "text-green-600" : "text-gray-600"}`}>{title}</span>
    </div>
  );
}
