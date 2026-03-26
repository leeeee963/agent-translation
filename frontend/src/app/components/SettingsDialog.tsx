import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Eye, EyeOff, Info, Save } from "lucide-react";
import { useLanguage } from "../contexts/LanguageContext";
import { fetchLLMConfig, saveLLMConfig } from "../api";
import { fetchPrompt, savePrompt } from "../api";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: "api" | "prompt";
}

const PROMPT_VARIABLES = [
  { name: "{target_language}", description: "目标语言" },
  { name: "{source_text}", description: "原文内容" },
  { name: "{glossary_constraints}", description: "术语约束" },
  { name: "{context_hint}", description: "上下文提示" },
];

export function SettingsDialog({
  open,
  onOpenChange,
  initialTab = "api",
}: SettingsDialogProps) {
  const { t } = useLanguage();

  // ── API settings state ──
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [maskedKey, setMaskedKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [apiSaving, setApiSaving] = useState(false);
  const [apiSaved, setApiSaved] = useState(false);
  const [apiError, setApiError] = useState("");

  // ── Prompt settings state ──
  const [editedPrompt, setEditedPrompt] = useState("");
  const [savedPrompt, setSavedPrompt] = useState("");
  const [promptPath, setPromptPath] = useState("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptSaving, setPromptSaving] = useState(false);
  const [banner, setBanner] = useState<{ type: string; message: string }>({
    type: "",
    message: "",
  });

  // ── Tab state ──
  const [activeTab, setActiveTab] = useState<string>(initialTab);

  // Reset tab when initialTab prop changes
  useEffect(() => {
    if (open) {
      setActiveTab(initialTab);
    }
  }, [open, initialTab]);

  // ── Load API config on open ──
  useEffect(() => {
    if (!open) return;
    setApiError("");
    setApiSaved(false);
    setApiKey("");
    setShowKey(false);
    fetchLLMConfig()
      .then((cfg) => {
        setMaskedKey(cfg.api_key_masked);
        setBaseUrl(cfg.base_url);
        setModel(cfg.model);
      })
      .catch(() => setApiError(t("settings.api") + " – load failed"));
  }, [open]);

  // ── Load Prompt on open ──
  useEffect(() => {
    if (open) {
      loadPrompt();
    }
  }, [open]);

  const loadPrompt = async () => {
    setPromptLoading(true);
    setBanner({ type: "", message: "" });
    try {
      const config = await fetchPrompt();
      setEditedPrompt(config.content);
      setSavedPrompt(config.content);
      setPromptPath(config.path || "");
    } catch (err: unknown) {
      setBanner({
        type: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPromptLoading(false);
    }
  };

  // ── API save handler ──
  const handleApiSave = async () => {
    setApiSaving(true);
    setApiError("");
    setApiSaved(false);
    try {
      const payload: { api_key?: string; base_url?: string; model?: string } =
        {};
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      if (baseUrl.trim()) payload.base_url = baseUrl.trim();
      if (model.trim()) payload.model = model.trim();
      await saveLLMConfig(payload);
      setApiSaved(true);
      if (apiKey.trim()) {
        const k = apiKey.trim();
        setMaskedKey(
          k.length > 4 ? "\u2022".repeat(k.length - 4) + k.slice(-4) : k
        );
        setApiKey("");
        setShowKey(false);
      }
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setApiSaving(false);
    }
  };

  // ── Prompt save handler ──
  const handlePromptSave = async () => {
    setPromptSaving(true);
    setBanner({ type: "", message: "" });
    try {
      await savePrompt(editedPrompt);
      setSavedPrompt(editedPrompt);
      setBanner({ type: "success", message: t("settings.saved") });
    } catch (err: unknown) {
      setBanner({
        type: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPromptSaving(false);
    }
  };

  const handlePromptReset = () => {
    setEditedPrompt(savedPrompt);
  };

  const promptDirty = editedPrompt !== savedPrompt;

  // ── Unified save dispatcher ──
  const handleSave = () => {
    if (activeTab === "api") {
      handleApiSave();
    } else {
      handlePromptSave();
    }
  };

  const isSaving = activeTab === "api" ? apiSaving : promptSaving;
  const isSaveDisabled =
    activeTab === "api"
      ? apiSaving
      : promptSaving || promptLoading || !promptDirty;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{t("settings.title")}</DialogTitle>
          <DialogDescription>{t("settings.promptDesc")}</DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex-1 flex flex-col overflow-hidden"
        >
          <TabsList className="shrink-0">
            <TabsTrigger value="api">{t("settings.tabApi")}</TabsTrigger>
            <TabsTrigger value="prompt">{t("settings.tabPrompt")}</TabsTrigger>
          </TabsList>

          {/* ── API Tab ── */}
          <TabsContent
            value="api"
            className="flex-1 overflow-auto mt-4 space-y-4"
          >
            {/* API Key */}
            <div className="space-y-1">
              <label className="text-sm font-medium text-foreground">
                {t("settings.apiKey")}
              </label>
              <div className="relative">
                <Input
                  type={showKey ? "text" : "password"}
                  placeholder={maskedKey || "Enter API Key"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowKey((v) => !v)}
                >
                  {showKey ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </button>
              </div>
              {maskedKey && !apiKey && (
                <p className="text-xs text-muted-foreground">
                  {maskedKey}
                </p>
              )}
            </div>

            {/* Base URL */}
            <div className="space-y-1">
              <label className="text-sm font-medium text-foreground">
                {t("settings.apiEndpoint")}
              </label>
              <Input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.poe.com/v1"
              />
            </div>

            {/* Model */}
            <div className="space-y-1">
              <label className="text-sm font-medium text-foreground">
                {t("settings.modelName")}
              </label>
              <Input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="GPT-4o"
              />
            </div>

            {apiError && (
              <p className="text-sm text-destructive">{apiError}</p>
            )}
            {apiSaved && (
              <p className="text-sm text-emerald-600">{t("settings.saved")}</p>
            )}
          </TabsContent>

          {/* ── Prompt Tab ── */}
          <TabsContent
            value="prompt"
            className="flex-1 overflow-auto mt-4 space-y-4"
          >
            {banner.message && (
              <div
                className={`rounded-lg px-4 py-2 text-sm ${
                  banner.type === "error"
                    ? "bg-destructive/10 text-destructive border border-destructive/20"
                    : "bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-800"
                }`}
              >
                {banner.message}
              </div>
            )}

            {/* Variable Info */}
            <div className="bg-accent/50 border border-border rounded-lg p-4">
              <div className="flex gap-3">
                <Info className="size-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-foreground font-medium mb-2">
                    {t("settings.promptVariables")}
                  </p>
                  <div className="space-y-1">
                    {PROMPT_VARIABLES.map((variable) => (
                      <div
                        key={variable.name}
                        className="flex items-center gap-2"
                      >
                        <Badge
                          variant="secondary"
                          className="font-mono text-xs"
                        >
                          {variable.name}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {variable.description}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Prompt Editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <label className="font-medium text-foreground">
                    {t("settings.prompt")}
                  </label>
                  {promptPath && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {promptPath}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={loadPrompt}
                    disabled={promptLoading}
                  >
                    Reload
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePromptReset}
                    disabled={!promptDirty}
                  >
                    Reset
                  </Button>
                </div>
              </div>
              {promptLoading ? (
                <div className="text-center py-12 text-muted-foreground">
                  Loading...
                </div>
              ) : (
                <Textarea
                  value={editedPrompt}
                  onChange={(e) => setEditedPrompt(e.target.value)}
                  className="min-h-[250px] font-mono text-sm"
                  placeholder="Enter translation prompt..."
                  spellCheck={false}
                />
              )}
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>{editedPrompt.length} chars</span>
                <span className="text-border">|</span>
                <span>{editedPrompt.split("\n").length} lines</span>
                {promptDirty && (
                  <>
                    <span className="text-border">|</span>
                    <span className="text-amber-600">unsaved changes</span>
                  </>
                )}
              </div>
            </div>

            {/* Preview */}
            <div className="space-y-2">
              <label className="font-medium text-foreground">Preview</label>
              <div className="bg-muted rounded-lg p-4 text-sm font-mono whitespace-pre-wrap text-muted-foreground border border-border">
                {editedPrompt
                  .replace("{target_language}", "English")
                  .replace(
                    "{source_text}",
                    "这是一个用于验证模板变量的示例文本。"
                  )
                  .replace(
                    "{glossary_constraints}",
                    "API -> API\nDashboard -> 仪表板"
                  )
                  .replace("{context_hint}", "产品说明文档")}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-4 border-t border-border shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSave} disabled={isSaveDisabled}>
            <Save className="size-4 mr-1.5" />
            {isSaving ? "..." : t("common.save")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
