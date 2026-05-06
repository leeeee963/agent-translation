import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Info } from "lucide-react";
import { useLanguage } from "../contexts/LanguageContext";
import { fetchLLMConfig, fetchPrompt } from "../api";

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

  const [maskedKey, setMaskedKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiError, setApiError] = useState("");

  const [promptContent, setPromptContent] = useState("");
  const [promptPath, setPromptPath] = useState("");
  const [promptError, setPromptError] = useState("");

  const [activeTab, setActiveTab] = useState<string>(initialTab);

  useEffect(() => {
    if (open) setActiveTab(initialTab);
  }, [open, initialTab]);

  useEffect(() => {
    if (!open) return;
    setApiError("");
    fetchLLMConfig()
      .then((cfg) => {
        setMaskedKey(cfg.api_key_masked);
        setBaseUrl(cfg.base_url);
        setModel(cfg.model);
      })
      .catch((err) => setApiError(err instanceof Error ? err.message : "加载失败"));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setPromptError("");
    fetchPrompt()
      .then((cfg) => {
        setPromptContent(cfg.content);
        setPromptPath(cfg.path || "");
      })
      .catch((err) => setPromptError(err instanceof Error ? err.message : "加载失败"));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{t("settings.title")}</DialogTitle>
          <DialogDescription>当前服务端配置（只读）</DialogDescription>
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
            <ReadonlyField label={t("settings.apiKey")} value={maskedKey || "—"} mono />
            <ReadonlyField label={t("settings.apiEndpoint")} value={baseUrl || "—"} mono />
            <ReadonlyField label={t("settings.modelName")} value={model || "—"} mono />
            {apiError && <p className="text-sm text-destructive">{apiError}</p>}
          </TabsContent>

          {/* ── Prompt Tab ── */}
          <TabsContent
            value="prompt"
            className="flex-1 overflow-auto mt-4 space-y-4"
          >
            {promptError && (
              <div className="rounded-lg px-4 py-2 text-sm bg-destructive/10 text-destructive border border-destructive/20">
                {promptError}
              </div>
            )}

            <div className="bg-accent/50 border border-border rounded-lg p-4">
              <div className="flex gap-3">
                <Info className="size-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-foreground font-medium mb-2">
                    {t("settings.promptVariables")}
                  </p>
                  <div className="space-y-1">
                    {PROMPT_VARIABLES.map((variable) => (
                      <div key={variable.name} className="flex items-center gap-2">
                        <Badge variant="secondary" className="font-mono text-xs">
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

            <div className="space-y-2">
              <label className="font-medium text-foreground">
                {t("settings.prompt")}
              </label>
              {promptPath && (
                <p className="text-xs text-muted-foreground">{promptPath}</p>
              )}
              <Textarea
                value={promptContent}
                readOnly
                className="min-h-[300px] font-mono text-sm bg-muted/50"
                spellCheck={false}
              />
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>{promptContent.length} chars</span>
                <span className="text-border">|</span>
                <span>{promptContent.split("\n").length} lines</span>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end gap-2 pt-4 border-t border-border shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.close")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ReadonlyField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div
        className={`px-3 py-2 rounded-md border border-border bg-muted/50 text-sm ${
          mono ? "font-mono" : ""
        } text-muted-foreground select-all break-all`}
      >
        {value}
      </div>
    </div>
  );
}
