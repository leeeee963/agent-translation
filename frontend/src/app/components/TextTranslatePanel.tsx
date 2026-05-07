import { useEffect, useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Checkbox } from "./ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Loader2, Copy, CheckCheck, Plus, X, Check } from "lucide-react";
import type { Language } from "../types/translation";
import { fetchLanguages, translateText, type TextTranslateResult } from "../api";
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

const DEFAULT_TARGETS = ["zh-CN"];

export function TextTranslatePanel() {
  const { language: uiLang } = useLanguage();
  const [allLangs, setAllLangs] = useState<Language[]>([]);
  const [selectedCodes, setSelectedCodes] = useState<string[]>(DEFAULT_TARGETS);
  const [sourceText, setSourceText] = useState("");
  const [review, setReview] = useState(true);
  const [translating, setTranslating] = useState(false);
  const [results, setResults] = useState<Record<string, TextTranslateResult> | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState("");

  useEffect(() => {
    fetchLanguages().then(setAllLangs).catch(() => {});
  }, []);

  const canTranslate = sourceText.trim().length > 0 && selectedCodes.length > 0 && !translating;
  const availableToAdd = allLangs.filter((l) => !selectedCodes.includes(l.code));

  function addLang(code: string) {
    if (!selectedCodes.includes(code)) setSelectedCodes([...selectedCodes, code]);
  }
  function removeLang(code: string) {
    setSelectedCodes(selectedCodes.filter((c) => c !== code));
  }

  async function handleTranslate() {
    if (!canTranslate) return;
    setTranslating(true);
    setResults(null);
    try {
      const res = await translateText(sourceText, selectedCodes, review);
      setResults(res.results);
      setSourceLanguage(res.source_language);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setTranslating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full p-1">
      {/* ── Top control bar (single row) ─────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-medium text-muted-foreground shrink-0 mr-1">
          {uiLang === "zh" ? "译入" : "To"}
        </span>

        {/* Selected language chips */}
        {selectedCodes.map((code) => (
          <span
            key={code}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-muted text-foreground rounded-md border border-border"
          >
            {langDisplay(code, uiLang)}
            <button
              onClick={() => removeLang(code)}
              className="hover:text-destructive transition-colors -mr-0.5"
              title={uiLang === "zh" ? "移除" : "Remove"}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}

        {/* Add language dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={availableToAdd.length === 0}
            >
              <Plus className="size-3 mr-0.5" />
              {uiLang === "zh" ? "添加" : "Add"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-72 overflow-y-auto">
            {availableToAdd.map((lang) => (
              <DropdownMenuItem
                key={lang.code}
                onClick={() => addLang(lang.code)}
                className="cursor-pointer"
              >
                <span className="flex-1">{langDisplay(lang.code, uiLang)}</span>
                <span className="text-xs text-muted-foreground ml-3">{lang.code}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="flex-1" />

        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none mr-2">
          <Checkbox checked={review} onCheckedChange={(v) => setReview(v === true)} />
          <span>{uiLang === "zh" ? "自然度审校" : "Naturalness review"}</span>
        </label>

        <Button
          variant="action"
          onClick={handleTranslate}
          disabled={!canTranslate}
          className="px-5 h-8"
        >
          {translating ? (
            <>
              <Loader2 className="size-3.5 animate-spin mr-1.5" />
              {uiLang === "zh" ? "翻译中" : "Translating"}
            </>
          ) : (
            <>
              <Check className="size-3.5 mr-1.5" />
              {uiLang === "zh" ? "翻译" : "Translate"}
            </>
          )}
        </Button>
      </div>

      {/* ── Two-column area: source / outputs ─────────────────────── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0">
        {/* Source input */}
        <div className="flex flex-col bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-border flex items-center justify-between text-xs">
            <span className="font-medium">
              {uiLang === "zh" ? "原文" : "Source"}
              {sourceLanguage && (
                <span className="ml-2 text-muted-foreground font-normal">
                  · {langDisplay(sourceLanguage, uiLang)}
                </span>
              )}
            </span>
            <span className="text-muted-foreground tabular-nums">{sourceText.length}</span>
          </div>
          <Textarea
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            placeholder={
              uiLang === "zh" ? "粘贴或输入要翻译的文本……" : "Paste or type the text to translate…"
            }
            className="flex-1 border-0 rounded-none resize-none focus-visible:ring-0 text-sm leading-relaxed p-3"
          />
        </div>

        {/* Outputs */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">
          {!results && !translating && (
            <div className="flex-1 flex items-center justify-center text-muted-foreground/70 text-sm bg-muted/20 rounded-xl border border-dashed border-border">
              {uiLang === "zh" ? "译文将显示在这里" : "Translations appear here"}
            </div>
          )}
          {translating && !results && (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm bg-muted/20 rounded-xl border border-border">
              <Loader2 className="size-4 animate-spin mr-2" />
              {uiLang === "zh" ? "翻译中…" : "Translating…"}
            </div>
          )}
          {results &&
            selectedCodes.map((code) => {
              const r = results[code];
              if (!r) return null;
              return (
                <ResultCard
                  key={code}
                  langCode={code}
                  langDisplay={langDisplay(code, uiLang)}
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
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium">{langDisplay}</span>
          <span className="text-muted-foreground">{langCode}</span>
          {result.elapsed_seconds > 0 && (
            <span className="text-muted-foreground/70">· {formatDuration(result.elapsed_seconds)}</span>
          )}
        </div>
        {!hasError && result.translated && (
          <button
            onClick={handleCopy}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted -mr-1"
            title={uiLang === "zh" ? "复制" : "Copy"}
          >
            {copied ? <CheckCheck className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
          </button>
        )}
      </div>
      <div className="px-3 py-3 text-sm whitespace-pre-wrap break-words leading-relaxed min-h-[60px]">
        {hasError ? (
          <span className="text-destructive">{result.error}</span>
        ) : (
          result.translated
        )}
      </div>
    </div>
  );
}
