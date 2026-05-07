import { useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Checkbox } from "./ui/checkbox";
import { Loader2, Copy, CheckCheck } from "lucide-react";
import type { Language } from "../types/translation";
import { LanguageSelector } from "./LanguageSelector";
import { translateText, type TextTranslateResult } from "../api";
import { useLanguage } from "../contexts/LanguageContext";
import { toast } from "sonner";
import { formatDuration } from "../utils/duration";

const LANG_NAMES: Record<string, { zh: string; en: string }> = {
  "zh-CN": { zh: "简体中文", en: "Chinese (Simplified)" },
  "zh-TW": { zh: "繁体中文", en: "Chinese (Traditional)" },
  en: { zh: "英文", en: "English" },
  ja: { zh: "日文", en: "Japanese" },
  ko: { zh: "韩文", en: "Korean" },
  mn: { zh: "蒙古文", en: "Mongolian" },
  th: { zh: "泰文", en: "Thai" },
  vi: { zh: "越南文", en: "Vietnamese" },
  id: { zh: "印尼文", en: "Indonesian" },
  kk: { zh: "哈萨克文", en: "Kazakh" },
  fr: { zh: "法文", en: "French" },
  de: { zh: "德文", en: "German" },
  es: { zh: "西班牙文", en: "Spanish" },
  pt: { zh: "葡萄牙文", en: "Portuguese" },
  ru: { zh: "俄文", en: "Russian" },
};

function langDisplay(code: string, uiLang: "zh" | "en"): string {
  return LANG_NAMES[code]?.[uiLang] ?? code;
}

export function TextTranslatePanel() {
  const { language: uiLang, t } = useLanguage();
  const [sourceText, setSourceText] = useState("");
  const [selectedLangs, setSelectedLangs] = useState<Language[]>([]);
  const [review, setReview] = useState(true);
  const [translating, setTranslating] = useState(false);
  const [results, setResults] = useState<Record<string, TextTranslateResult> | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState("");

  const canTranslate = sourceText.trim().length > 0 && selectedLangs.length > 0 && !translating;

  async function handleTranslate() {
    if (!canTranslate) return;
    setTranslating(true);
    setResults(null);
    try {
      const codes = selectedLangs.map((l) => l.code);
      const res = await translateText(sourceText, codes, review);
      setResults(res.results);
      setSourceLanguage(res.source_language);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setTranslating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* ── Top control bar ───────────────────────────────────────── */}
      <div className="flex flex-col gap-3 bg-card border border-border rounded-xl p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)]">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-foreground shrink-0">
            {uiLang === "zh" ? "目标语言" : "Target languages"}
          </span>
          <div className="flex-1 min-w-[200px]">
            <LanguageSelector
              selectedLanguages={selectedLangs}
              onLanguagesChange={setSelectedLangs}
              variant="compact"
            />
          </div>
        </div>
        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer select-none">
            <Checkbox checked={review} onCheckedChange={(v) => setReview(v === true)} />
            <span>{uiLang === "zh" ? "自然度审校" : "Naturalness review"}</span>
          </label>
          <Button
            variant="action"
            onClick={handleTranslate}
            disabled={!canTranslate}
            className="px-6"
          >
            {translating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              t("common.start")
            )}
          </Button>
        </div>
      </div>

      {/* ── Two-column area: source / outputs ─────────────────────── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        {/* Source input */}
        <div className="flex flex-col bg-card border border-border rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)] overflow-hidden">
          <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
            <span className="text-sm font-medium">
              {uiLang === "zh" ? "原文" : "Source"}
              {sourceLanguage && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {langDisplay(sourceLanguage, uiLang)}
                </span>
              )}
            </span>
            <span className="text-xs text-muted-foreground">{sourceText.length}</span>
          </div>
          <Textarea
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            placeholder={
              uiLang === "zh"
                ? "粘贴或输入要翻译的文本……"
                : "Paste or type the text to translate…"
            }
            className="flex-1 border-0 rounded-none resize-none focus-visible:ring-0 text-sm"
          />
        </div>

        {/* Outputs */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">
          {!results && !translating && (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm bg-muted/30 rounded-xl border border-dashed border-border">
              {uiLang === "zh" ? "译文将显示在这里" : "Translations will appear here"}
            </div>
          )}
          {translating && !results && (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm bg-muted/30 rounded-xl border border-border">
              <Loader2 className="size-4 animate-spin mr-2" />
              {uiLang === "zh" ? "翻译中…" : "Translating…"}
            </div>
          )}
          {results &&
            selectedLangs.map((lang) => {
              const r = results[lang.code];
              if (!r) return null;
              return (
                <ResultCard
                  key={lang.code}
                  langCode={lang.code}
                  langDisplay={langDisplay(lang.code, uiLang)}
                  result={r}
                  uiLang={uiLang}
                />
              );
            })}
        </div>
      </div>
    </div>
  );
}

function ResultCard({
  langCode,
  langDisplay,
  result,
  uiLang,
}: {
  langCode: string;
  langDisplay: string;
  result: TextTranslateResult;
  uiLang: "zh" | "en";
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!result.translated) return;
    try {
      await navigator.clipboard.writeText(result.translated);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(uiLang === "zh" ? "复制失败" : "Copy failed");
    }
  }

  const hasError = !!result.error;

  return (
    <div className="bg-card border border-border rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{langDisplay}</span>
          <span className="text-xs text-muted-foreground">{langCode}</span>
          {result.elapsed_seconds > 0 && (
            <span className="text-[10px] text-muted-foreground/70">
              {formatDuration(result.elapsed_seconds)}
            </span>
          )}
        </div>
        {!hasError && result.translated && (
          <button
            onClick={handleCopy}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted"
            title={uiLang === "zh" ? "复制" : "Copy"}
          >
            {copied ? <CheckCheck className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
          </button>
        )}
      </div>
      <div className="px-4 py-3 text-sm whitespace-pre-wrap break-words min-h-[60px]">
        {hasError ? (
          <span className="text-destructive">{result.error}</span>
        ) : (
          result.translated
        )}
      </div>
    </div>
  );
}
