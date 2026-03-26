import { useState, useEffect, useCallback, useRef } from "react";
import { FileUploadSection } from "./FileUploadSection";
import { LanguageSelector } from "./LanguageSelector";
import { TranslationModeSelector } from "./TranslationModeSelector";
import { TaskWorkbenchSection } from "./TaskWorkbenchSection";
import { TermLibraryContent } from "./TermLibraryPage";

import { SettingsDialog } from "./SettingsDialog";
import type { TranslationFile, Language, Job, LibraryDomain } from "../types/translation";
import { submitJobs, fetchJobs, cancelJob, fetchLibraryDomains } from "../api";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  FileText, Settings, Check,
  Info, LibraryBig, Moon, Sun, Languages,
  FilePlus2, ClipboardList,
} from "lucide-react";
import { Toaster } from "./ui/sonner";
import { useTheme } from "../contexts/ThemeContext";
import { useLanguage } from "../contexts/LanguageContext";

const USE_GLOSSARY_KEY = "translation_use_glossary";

function loadUseGlossarySetting(): boolean {
  try {
    const stored = localStorage.getItem(USE_GLOSSARY_KEY);
    return stored === null ? true : stored !== "false";
  } catch { return true; }
}

function saveUseGlossarySetting(value: boolean) {
  try { localStorage.setItem(USE_GLOSSARY_KEY, value ? "true" : "false"); } catch { /* ignore */ }
}

const POLL_INTERVAL = 1500;

type PanelId = "create" | "tasks" | "library";

export function TranslationApp() {
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage, t } = useLanguage();
  const domainName = (d: LibraryDomain) => (language === 'zh' ? d.name_zh : d.name_en) || d.name;
  const [domainDropdownOpen, setDomainDropdownOpen] = useState(false);
  const domainDropdownRef = useRef<HTMLDivElement>(null);
  const [proInfoHover, setProInfoHover] = useState(false);
  const [files, setFiles] = useState<TranslationFile[]>([]);
  const [selectedLanguages, setSelectedLanguages] = useState<Language[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'api' | 'prompt'>('api');
  const [isTranslating, setIsTranslating] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);

  const [useGlossary, setUseGlossaryState] = useState<boolean>(loadUseGlossarySetting);
  const [libraryDomains, setLibraryDomains] = useState<LibraryDomain[]>([]);
  const [selectedDomainIds, setSelectedDomainIds] = useState<number[]>([]);

  // ── Panel animation system ──
  const [visiblePanels, setVisiblePanels] = useState<Set<PanelId>>(new Set(["create", "tasks"]));
  const [closingPanels, setClosingPanels] = useState<Set<PanelId>>(new Set());
  // Track panels that have finished entering (so we don't replay enter animation on re-render)
  const [enteredPanels, setEnteredPanels] = useState<Set<PanelId>>(new Set(["create", "tasks"]));

  // Refs for icon buttons (animation origin) and panel containers
  const iconRefs = useRef<Record<PanelId, HTMLButtonElement | null>>({ create: null, tasks: null, library: null });
  const panelRefs = useRef<Record<PanelId, HTMLDivElement | null>>({ create: null, tasks: null, library: null });
  // Store transform-origin at the moment of toggle (before layout changes)
  const originCache = useRef<Record<PanelId, string>>({ create: "0px 50%", tasks: "0px 50%", library: "0px 50%" });

  const computeTransformOrigin = useCallback((panelId: PanelId): string => {
    const iconEl = iconRefs.current[panelId];
    const panelEl = panelRefs.current[panelId];
    if (!iconEl || !panelEl) return "-48px 50%";
    const iconRect = iconEl.getBoundingClientRect();
    const panelRect = panelEl.getBoundingClientRect();
    const relativeX = iconRect.left + iconRect.width / 2 - panelRect.left;
    const relativeY = iconRect.top + iconRect.height / 2 - panelRect.top;
    return `${relativeX}px ${relativeY}px`;
  }, []);

  const togglePanel = useCallback((id: PanelId) => {
    if (visiblePanels.has(id)) {
      // Capture origin before exit animation starts
      originCache.current[id] = computeTransformOrigin(id);
      setClosingPanels((prev) => new Set([...prev, id]));
    } else {
      setVisiblePanels((prev) => new Set([...prev, id]));
    }
  }, [visiblePanels, computeTransformOrigin]);

  // After panel mounts, compute its origin for enter animation
  useEffect(() => {
    for (const id of visiblePanels) {
      if (!enteredPanels.has(id) && !closingPanels.has(id) && panelRefs.current[id]) {
        originCache.current[id] = computeTransformOrigin(id);
      }
    }
  });

  const handlePanelAnimationEnd = useCallback((id: PanelId) => {
    if (closingPanels.has(id)) {
      setClosingPanels((prev) => { const n = new Set(prev); n.delete(id); return n; });
      setVisiblePanels((prev) => { const n = new Set(prev); n.delete(id); return n; });
      setEnteredPanels((prev) => { const n = new Set(prev); n.delete(id); return n; });
    } else {
      // Enter animation finished — mark as entered
      setEnteredPanels((prev) => new Set([...prev, id]));
    }
  }, [closingPanels]);

  const shouldRender = (id: PanelId) => visiblePanels.has(id) || closingPanels.has(id);
  const isClosing = (id: PanelId) => closingPanels.has(id);
  const panelAnimClass = (id: PanelId) => {
    if (isClosing(id)) return "panel-exiting";
    if (!enteredPanels.has(id)) return "panel-entering";
    return "";  // Already entered, no animation class
  };

  const handleUseGlossaryChange = (value: boolean) => {
    setUseGlossaryState(value);
    saveUseGlossarySetting(value);
    if (!value) setSelectedDomainIds([]);
  };

  useEffect(() => {
    if (!domainDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (domainDropdownRef.current && !domainDropdownRef.current.contains(e.target as Node)) {
        setDomainDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [domainDropdownOpen]);

  useEffect(() => {
    fetchLibraryDomains().then(setLibraryDomains).catch(() => {});
  }, []);

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

  const handleStartTranslation = async () => {
    const completedFiles = files.filter((f) => f.uploadStatus === 'completed');
    if (completedFiles.length === 0 || selectedLanguages.length === 0) return;
    setIsTranslating(true);
    try {
      await submitJobs(
        completedFiles.map((f) => f.file),
        selectedLanguages.map((l) => l.code),
        useGlossary,
        selectedDomainIds,
      );
      await loadJobs();
      // Show tasks panel after starting
      setVisiblePanels((prev) => new Set([...prev, "tasks"]));
    } catch {
      setIsTranslating(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try { await cancelJob(jobId); await loadJobs(); } catch { /* silent */ }
  };

  const handleGlossaryConfirmed = async () => { await loadJobs(); };

  const completedFiles = files.filter((f) => f.uploadStatus === 'completed').length;
  const canStartTranslation = completedFiles > 0 && selectedLanguages.length > 0 && !isTranslating;

  const openSettings = (tab: 'api' | 'prompt') => {
    setSettingsTab(tab);
    setSettingsOpen(true);
  };

  const PANELS: { id: PanelId; icon: React.ReactNode; label: string }[] = [
    { id: "create", icon: <FilePlus2 className="size-[18px]" />, label: t("nav.create") },
    { id: "tasks", icon: <ClipboardList className="size-[18px]" />, label: t("nav.taskList") },
    { id: "library", icon: <LibraryBig className="size-[18px]" />, label: t("nav.library") },
  ];

  return (
    <div className="h-screen flex bg-background">
      <Toaster />

      {/* ── Narrow icon rail ── */}
      <aside className="w-14 h-screen flex flex-col items-center justify-between border-r border-border bg-card flex-shrink-0 py-3">
        {/* Top: Logo */}
        <div>
          <FileText className="size-5 text-foreground" />
        </div>

        {/* Center: Panel toggle icons */}
        <nav className="space-y-[30px]">
          {PANELS.map(({ id, icon, label }) => (
            <button
              key={id}
              ref={(el) => { iconRefs.current[id] = el; }}
              onClick={() => togglePanel(id)}
              className={[
                "flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-200",
                visiblePanels.has(id) && !closingPanels.has(id)
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
              ].join(" ")}
              title={label}
            >
              {icon}
            </button>
          ))}
        </nav>

        {/* Bottom icons */}
        <div className="space-y-1">
          <NavIcon
            icon={theme === 'dark' ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
            label={theme === 'dark' ? t('theme.light') : t('theme.dark')}
            onClick={toggleTheme}
          />
          <NavIcon
            icon={<Languages className="size-[18px]" />}
            label={language === 'en' ? '中文' : 'English'}
            onClick={() => setLanguage(language === 'en' ? 'zh' : 'en')}
          />
          <NavIcon
            icon={<Settings className="size-[18px]" />}
            label={t('settings.title')}
            onClick={() => openSettings('api')}
          />
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 min-w-0 h-screen overflow-y-auto overflow-x-hidden px-14 py-14 space-y-0">

        {/* Panel: New Translation */}
        {shouldRender("create") && (
          <div className={`panel-slot ${isClosing("create") ? "slot-closing" : ""}`}>
            <div className="panel-slot-inner">
              <div
                ref={(el) => { panelRefs.current.create = el; }}
                className={`bg-card border border-border rounded-xl shadow-sm flex overflow-hidden mb-14 ${panelAnimClass("create")}`}
                style={{ transformOrigin: originCache.current.create }}
                onAnimationEnd={() => handlePanelAnimationEnd("create")}
              >
                {/* Vertical title */}
                <div className="flex items-center justify-center px-4 bg-foreground rounded-l-xl flex-shrink-0">
                  <span className="[writing-mode:vertical-rl] text-base font-semibold text-background tracking-[0.3em] select-none">
                    {t('nav.create')}
                  </span>
                </div>
                {/* Content */}
                <div className="flex-1 min-w-0 p-14">
                <div className="grid grid-cols-[0.7fr_1fr_1.3fr_auto] gap-14 items-stretch">
                  {/* Sub-card 1: File Upload */}
                  <div className="bg-card border border-border rounded-xl shadow-sm p-4 min-h-[305px]">
                    <FileUploadSection files={files} onFilesChange={setFiles} />
                  </div>

                  {/* Sub-card 2: Domain + PRO */}
                  <div className="bg-card border border-border rounded-xl shadow-sm p-4 min-h-[305px] max-w-[70%] mx-auto">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-medium text-muted-foreground">{t('domain.select')}</span>
                      <TranslationModeSelector
                        useGlossary={useGlossary}
                        onUseGlossaryChange={handleUseGlossaryChange}
                      />
                    </div>
                    {!useGlossary ? (
                      <div
                        className="relative"
                        onMouseEnter={() => setProInfoHover(true)}
                        onMouseLeave={() => setProInfoHover(false)}
                      >
                        <p className="text-xs text-muted-foreground opacity-60">{t('mode.proInfoDesc')}</p>
                        {proInfoHover && (
                          <div className="absolute left-0 top-full mt-2 w-auto max-w-72 rounded-lg border border-border bg-popover text-popover-foreground shadow-lg z-50 p-4 space-y-3">
                            <div>
                              <span className="inline-block px-2 py-0.5 rounded text-xs font-black tracking-widest bg-foreground text-background">PRO</span>
                              <p className="text-xs text-muted-foreground mt-1.5">{t('mode.proInfoDesc')}</p>
                            </div>
                            <div className="h-px bg-border" />
                            <div>
                              <span className="inline-block px-2 py-0.5 rounded text-xs font-black tracking-widest bg-muted text-foreground border border-border">{t('mode.libraryInfoTitle')}</span>
                              <p className="text-xs text-muted-foreground mt-1.5">{t('mode.libraryInfoDesc')}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-1.5" ref={domainDropdownRef}>
                        {libraryDomains.length > 0 ? libraryDomains.map((d) => {
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
                                  : "bg-muted/50 text-muted-foreground hover:bg-muted"
                              }`}
                            >
                              {domainName(d)}
                            </button>
                          );
                        }) : (
                          <p className="text-xs text-muted-foreground">{t('domain.select')}</p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Sub-card 3: Language Selector */}
                  <div className="bg-card border border-border rounded-xl shadow-sm p-4 min-h-[305px] max-w-[70%] mx-auto">
                    <LanguageSelector
                      selectedLanguages={selectedLanguages}
                      onLanguagesChange={setSelectedLanguages}
                      variant="inline"
                    />
                  </div>

                  {/* Vertical Start Button */}
                  <Button
                    onClick={handleStartTranslation}
                    disabled={!canStartTranslation}
                    className="h-auto px-2.5 rounded-lg bg-foreground/80 text-background hover:bg-foreground/70 disabled:bg-foreground/15 disabled:shadow-none dark:bg-primary/80 dark:text-primary-foreground dark:hover:bg-primary/70 transition-all duration-200 active:scale-[0.97] [writing-mode:vertical-rl] text-sm tracking-widest"
                  >
                    {isTranslating ? '...' : t('common.start')}
                  </Button>
                </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Panel: Translation Tasks */}
        {shouldRender("tasks") && (
          <div className={`panel-slot ${isClosing("tasks") ? "slot-closing" : ""}`}>
            <div className="panel-slot-inner">
              <div
                ref={(el) => { panelRefs.current.tasks = el; }}
                className={`bg-card border border-border rounded-xl shadow-sm flex overflow-hidden mb-14 ${panelAnimClass("tasks")}`}
                style={{ transformOrigin: originCache.current.tasks }}
                onAnimationEnd={() => handlePanelAnimationEnd("tasks")}
              >
                {/* Vertical title */}
                <div className="flex items-center justify-center px-4 bg-foreground rounded-l-xl flex-shrink-0">
                  <span className="[writing-mode:vertical-rl] text-base font-semibold text-background tracking-[0.3em] select-none">
                    {t('nav.taskList')}
                  </span>
                </div>
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <TaskWorkbenchSection
                    jobs={jobs}
                    onCancelJob={handleCancelJob}
                    onGlossaryConfirmed={handleGlossaryConfirmed}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Panel: Terminology Library */}
        {shouldRender("library") && (
          <div className={`panel-slot ${isClosing("library") ? "slot-closing" : ""}`}>
            <div className="panel-slot-inner">
              <div
                ref={(el) => { panelRefs.current.library = el; }}
                className={`bg-card border border-border rounded-xl shadow-sm flex overflow-hidden mb-14 ${panelAnimClass("library")}`}
                style={{ transformOrigin: originCache.current.library, minHeight: "500px" }}
                onAnimationEnd={() => handlePanelAnimationEnd("library")}
              >
                {/* Vertical title */}
                <div className="flex items-center justify-center px-4 bg-foreground rounded-l-xl flex-shrink-0">
                  <span className="[writing-mode:vertical-rl] text-base font-semibold text-background tracking-[0.3em] select-none">
                    {t('nav.library')}
                  </span>
                </div>
                {/* Content */}
                <div className="flex-1 min-w-0 overflow-hidden">
                  <TermLibraryContent />
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        initialTab={settingsTab}
      />
    </div>
  );
}

/* ── Narrow nav icon button ── */

function NavIcon({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-center w-9 h-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
      title={label}
    >
      {icon}
    </button>
  );
}
