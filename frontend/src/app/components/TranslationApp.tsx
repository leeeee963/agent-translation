import { useState, useEffect, useCallback } from "react";
import { FileUploadSection } from "./FileUploadSection";
import { LanguageSelector } from "./LanguageSelector";
import { TaskWorkbenchSection } from "./TaskWorkbenchSection";
import { TermLibraryContent } from "./TermLibraryPage";
import { SettingsDialog } from "./SettingsDialog";
import type { TranslationFile, Language, Job, LibraryDomain } from "../types/translation";
import { submitJobs, fetchJobs, cancelJob, deleteJobs, fetchLibraryDomains } from "../api";
import { Button } from "./ui/button";
import {
  Settings,
  LibraryBig, Moon, Sun, Languages,
  FilePlus2, ClipboardList, X, Loader2,
} from "lucide-react";
import { Toaster } from "./ui/sonner";
import { toast } from "sonner";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";
import { Sidebar } from "./layout/Sidebar";
import { WorkspaceLayout } from "./layout/WorkspaceLayout";
import { Panel } from "./layout/Panel";
const POLL_INTERVAL = 1500;

// ── Main App ──

export function TranslationApp() {
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage, t } = useLanguage();
  const domainName = (d: LibraryDomain) => (language === 'zh' ? d.name_zh : d.name_en) || d.name;

  // ── Form state ──
  const [files, setFiles] = useState<TranslationFile[]>([]);
  const [selectedLanguages, setSelectedLanguages] = useState<Language[]>([]);
  const [isTranslating, setIsTranslating] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);

  // ── Domain state ──
  const [libraryDomains, setLibraryDomains] = useState<LibraryDomain[]>([]);
  const [selectedDomainIds, setSelectedDomainIds] = useState<number[]>([]);

  // ── Settings state ──
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'api' | 'prompt'>('api');

  // ── Layout state ──
  const [showLibrary, setShowLibrary] = useState(false);
  const [showCreatePanel, setShowCreatePanel] = useState(true);

  // ── Effects ──

  // Fetch library domains on mount
  useEffect(() => {
    fetchLibraryDomains().then(setLibraryDomains).catch(() => {});
  }, []);

  // Job polling
  const loadJobs = useCallback(async () => {
    try {
      const allJobs = await fetchJobs();
      setJobs(allJobs);
      const hasActive = allJobs.some((j) =>
        ["queued", "pending", "parsing", "terminology", "translating", "rebuilding"].includes(j.status)
      );
      if (!hasActive && isTranslating) setIsTranslating(false);
    } catch { /* silent */ }
  }, [isTranslating]);

  useEffect(() => {
    loadJobs();
    const timer = window.setInterval(loadJobs, POLL_INTERVAL);
    return () => window.clearInterval(timer);
  }, [loadJobs]);

  // ── Handlers ──

  const handleStartTranslation = async () => {
    const completedFiles = files.filter((f) => f.uploadStatus === 'completed');
    if (completedFiles.length === 0 || selectedLanguages.length === 0) return;
    setIsTranslating(true);
    try {
      await submitJobs(
        completedFiles.map((f) => f.file),
        selectedLanguages.map((l) => l.code),
        selectedDomainIds.length > 0,
        selectedDomainIds,
      );
      await loadJobs();
    } catch {
      setIsTranslating(false);
      toast.error(t('error.submitFailed'));
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try { await cancelJob(jobId); await loadJobs(); } catch { toast.error(t('error.cancelFailed')); }
  };

  const handleDeleteJobs = async (jobIds: string[]) => {
    try { await deleteJobs(jobIds); await loadJobs(); } catch { toast.error(t('error.deleteFailed')); }
  };

  const handleGlossaryConfirmed = async () => { await loadJobs(); };

  const openSettings = (tab: 'api' | 'prompt') => {
    setSettingsTab(tab);
    setSettingsOpen(true);
  };

  const completedFiles = files.filter((f) => f.uploadStatus === 'completed').length;
  const canStartTranslation = completedFiles > 0 && selectedLanguages.length > 0 && !isTranslating;

  // ── Render ──

  return (
    <div className="h-screen flex bg-background">
      <Toaster />

      {/* ── Sidebar ── */}
      <Sidebar
        navItems={[
          { icon: <FilePlus2 className="size-5" />, label: t("nav.create"), active: showCreatePanel && !showLibrary, onClick: () => setShowCreatePanel((v) => !v) },
          { icon: <ClipboardList className="size-5" />, label: t("nav.taskList"), active: !showLibrary },
          { icon: <LibraryBig className="size-5" />, label: t("nav.library"), active: showLibrary, onClick: () => setShowLibrary((v) => !v) },
        ]}
        bottomItems={[
          { icon: theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />, label: theme === 'dark' ? t('theme.light') : t('theme.dark'), onClick: toggleTheme },
          { icon: <Languages className="size-5" />, label: language === 'en' ? '中文' : 'English', onClick: () => setLanguage(language === 'en' ? 'zh' : 'en') },
          { icon: <Settings className="size-5" />, label: t('settings.title'), onClick: () => openSettings('api') },
        ]}
      />

      {/* ── Workspace ── */}
      <WorkspaceLayout
        showLeft={showCreatePanel}
        leftPanel={
          <Panel
            title={t("nav.create")}
            className="flex-1"
            footer={
              <div className="px-6 py-4">
                <Button
                  variant="action"
                  onClick={handleStartTranslation}
                  disabled={!canStartTranslation}
                  className="w-full py-2.5 rounded-lg text-base tracking-wide"
                >
                  {isTranslating ? <Loader2 className="size-4 animate-spin" /> : t('common.start')}
                </Button>
              </div>
            }
          >
            <div className="p-4 flex flex-col gap-3 h-full">
              {/* File Upload */}
              <div className="flex-[2] flex flex-col bg-muted/30 rounded-lg px-4 py-4 min-h-0">
                <div className="text-xs font-medium text-muted-foreground mb-1.5">{t('upload.title') || '上传文件'}</div>
                <div className="flex-1 flex min-h-0">
                  <FileUploadSection files={files} onFilesChange={setFiles} />
                </div>
              </div>

              {/* Domain Selection */}
              <div className="flex-1 bg-muted/30 rounded-lg px-4 py-4">
                <div className="text-xs font-medium text-muted-foreground mb-3">{t('domain.select')}</div>
                {libraryDomains.length > 0 ? (
                  <>
                    <div className="flex flex-wrap gap-1.5">
                      {[...libraryDomains].sort((a, b) => domainName(a).length - domainName(b).length).map((d) => {
                        const isDomainSelected = selectedDomainIds.includes(d.id);
                        return (
                          <button
                            key={d.id}
                            onClick={() => {
                              if (isDomainSelected) {
                                setSelectedDomainIds(selectedDomainIds.filter((id) => id !== d.id));
                              } else {
                                setSelectedDomainIds([...selectedDomainIds, d.id]);
                              }
                            }}
                            className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                              isDomainSelected
                                ? "bg-foreground/80 text-background"
                                : "bg-card text-muted-foreground hover:bg-card/80"
                            }`}
                          >
                            {domainName(d)}
                            {d.term_count > 0 && <span className="opacity-60 ml-0.5">({d.term_count})</span>}
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-xs text-muted-foreground opacity-40 mt-3 leading-relaxed">
                      {selectedDomainIds.length > 0 ? t('domain.selectedHint') : t('domain.unselectedHint')}
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground opacity-50">{t('domain.noDomains')}</p>
                )}
              </div>

              {/* Language Selection */}
              <div className="flex-1 bg-muted/30 rounded-lg px-4 py-4">
                <LanguageSelector
                  selectedLanguages={selectedLanguages}
                  onLanguagesChange={setSelectedLanguages}
                  variant="inline"
                />
              </div>
            </div>
          </Panel>
        }

        rightPanel={
          <Panel title={t("nav.taskList")} className="flex-1">
            <TaskWorkbenchSection
              jobs={jobs}
              onCancelJob={handleCancelJob}
              onDeleteJobs={handleDeleteJobs}
              onGlossaryConfirmed={handleGlossaryConfirmed}
            />
          </Panel>
        }

        showOverlay={showLibrary}
        overlay={
          <Panel
            title={t("nav.library")}
            className="h-full"
            headerRight={
              <button
                onClick={() => setShowLibrary(false)}
                className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted"
                title={t('common.close') || '关闭'}
              >
                <X className="size-4" />
              </button>
            }
          >
            <TermLibraryContent />
          </Panel>
        }
      />

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        initialTab={settingsTab}
      />
    </div>
  );
}
