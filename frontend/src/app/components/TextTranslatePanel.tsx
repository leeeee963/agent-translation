import { useEffect, useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Checkbox } from "./ui/checkbox";
import { Loader2, Copy, CheckCheck, Plus, X } from "lucide-react";
import { translateText, type TextTranslateResult } from "../api";
import { useLanguage } from "../contexts/LanguageContext";
import { toast } from "sonner";
import { formatDuration } from "../utils/duration";
import { LANG_NAMES, langDisplay } from "../utils/languageNames";

const DEFAULT_TARGETS = ["zh-CN"];
const ALL_LANG_CODES = Object.keys(LANG_NAMES);

export function TextTranslatePanel() {
  const { language: uiLang } = useLanguage();
  const [selectedCodes, setSelectedCodes] = useState<string[]>(DEFAULT_TARGETS);
  const [sourceText, setSourceText] = useState("");
  const [review, setReview] = useState(true);
  const [translating, setTranslating] = useState(false);
  const [results, setResults] = useState<Record<string, TextTranslateResult> | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState("");
  const [showLangPicker, setShowLangPicker] = useState(false);

  const canTranslate =
    sourceText.trim().length > 0 && selectedCodes.length > 0 && !translating;
  const availableToAdd = ALL_LANG_CODES.filter((c) => !selectedCodes.includes(c));
  const isSingle = selectedCodes.length === 1;
  const isEmpty = selectedCodes.length === 0;

  function addLang(code: string) {
    if (!selectedCodes.includes(code)) {
      setSelectedCodes([...selectedCodes, code]);
    }
  }
  function removeLang(code: string) {
    const next = selectedCodes.filter((c) => c !== code);
    setSelectedCodes(next);
    // If user removed the last language, open the picker so they can add one
    if (next.length === 0) setShowLangPicker(true);
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

  // Cmd/Ctrl + Enter triggers translation from anywhere in the panel
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (canTranslate) handleTranslate();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canTranslate, sourceText, selectedCodes, review]);

  return (
    <div className="flex flex-col gap-4 h-full p-5 lg:p-6">
      {/* ── Control bar ───────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        {selectedCodes.map((code) => (
          <span
            key={code}
            className="inline-flex items-center gap-1 h-7 px-2 text-xs font-medium bg-muted text-foreground rounded-md border border-border"
          >
            {langDisplay(code, uiLang)}
            <button
              onClick={() => removeLang(code)}
              className="hover:text-destructive transition-colors -mr-0.5"
              title={uiLang === "zh" ? "移除" : "Remove"}
              aria-label={uiLang === "zh" ? "移除语言" : "Remove language"}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}

        <Button
          variant="outline"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => setShowLangPicker((v) => !v)}
          disabled={availableToAdd.length === 0}
        >
          <Plus className="size-3 mr-0.5" />
          {uiLang === "zh" ? "添加语言" : "Add"}
        </Button>

        <div className="flex-1" />

        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none mr-2 shrink-0">
          <Checkbox
            checked={review}
            onCheckedChange={(v) => setReview(v === true)}
          />
          <span>{uiLang === "zh" ? "自然度审校" : "Naturalness review"}</span>
        </label>

        <Button
          variant="action"
          onClick={handleTranslate}
          disabled={!canTranslate}
          className="h-8 px-5 shrink-0"
          title="Cmd/Ctrl + Enter"
        >
          {translating ? (
            <>
              <Loader2 className="size-3.5 animate-spin mr-1.5" />
              {uiLang === "zh" ? "翻译中" : "Translating"}
            </>
          ) : uiLang === "zh" ? (
            "翻译"
          ) : (
            "Translate"
          )}
        </Button>
      </div>

      {/* ── Inline language picker (no portal — works inside overlay) ── */}
      {showLangPicker && availableToAdd.length > 0 && (
        <div className="flex flex-wrap gap-1.5 p-3 bg-muted/30 rounded-lg border border-border shrink-0">
          {availableToAdd.map((code) => (
            <button
              key={code}
              onClick={() => {
                addLang(code);
                if (availableToAdd.length === 1) setShowLangPicker(false);
              }}
              className="inline-flex items-center gap-1 h-7 px-2 text-xs bg-background hover:bg-muted hover:border-foreground/20 rounded-md border border-border transition-colors cursor-pointer"
            >
              <span className="font-medium">{langDisplay(code, uiLang)}</span>
              <span className="text-muted-foreground">{code}</span>
            </button>
          ))}
          <button
            onClick={() => setShowLangPicker(false)}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground transition-colors px-2"
          >
            {uiLang === "zh" ? "完成" : "Done"}
          </button>
        </div>
      )}

      {/* ── Main area: 2-column symmetric ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 flex-1 min-h-0">
        {/* Source panel */}
        <div className="flex flex-col bg-card border border-border rounded-xl overflow-hidden">
          <div className="h-9 px-3 border-b border-border flex items-center justify-between text-xs shrink-0">
            <span>
              <span className="font-medium">
                {uiLang === "zh" ? "原文" : "Source"}
              </span>
              {sourceLanguage && (
                <span className="ml-1.5 text-muted-foreground font-normal">
                  · {langDisplay(sourceLanguage, uiLang)}
                </span>
              )}
            </span>
            <span className="text-muted-foreground tabular-nums">
              {sourceText.length} {uiLang === "zh" ? "字" : "chars"}
            </span>
          </div>
          <Textarea
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            placeholder={
              uiLang === "zh"
                ? "粘贴或输入要翻译的文本……"
                : "Paste or type the text to translate…"
            }
            className="flex-1 border-0 rounded-none resize-none focus-visible:ring-0 p-3 text-sm leading-relaxed"
          />
        </div>

        {/* Translation panel */}
        <div className="flex flex-col bg-card border border-border rounded-xl overflow-hidden">
          {isEmpty ? (
            <div className="h-full flex items-center justify-center text-muted-foreground/70 text-xs px-3 text-center">
              {uiLang === "zh"
                ? "请先在上方点「+ 添加语言」选择目标语言"
                : "Click + Add above to pick a target language"}
            </div>
          ) : isSingle ? (
            <SingleResult
              code={selectedCodes[0]}
              result={results?.[selectedCodes[0]]}
              translating={translating}
              uiLang={uiLang}
            />
          ) : (
            <MultiResults
              codes={selectedCodes}
              results={results}
              translating={translating}
              uiLang={uiLang}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Single language: mirror of the source panel ──────────────────────

function SingleResult({
  code,
  result,
  translating,
  uiLang,
}: {
  code: string;
  result?: TextTranslateResult;
  translating: boolean;
  uiLang: "zh" | "en";
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!result?.translated) return;
    try {
      await navigator.clipboard.writeText(result.translated);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(uiLang === "zh" ? "复制失败" : "Copy failed");
    }
  }

  const hasError = !!result?.error;
  const text = result?.translated || "";

  return (
    <>
      <div className="h-9 px-3 border-b border-border flex items-center justify-between text-xs shrink-0">
        <span className="flex items-center gap-1.5 min-w-0">
          <span className="font-medium">{uiLang === "zh" ? "译文" : "Translation"}</span>
          <span className="text-muted-foreground font-normal truncate">
            · {langDisplay(code, uiLang)}
          </span>
          {result?.elapsed_seconds && result.elapsed_seconds > 0 ? (
            <span className="text-muted-foreground/70 shrink-0">
              · {formatDuration(result.elapsed_seconds)}
            </span>
          ) : null}
        </span>
        {!hasError && text && (
          <button
            onClick={handleCopy}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted -mr-1"
            title={uiLang === "zh" ? "复制" : "Copy"}
            aria-label={uiLang === "zh" ? "复制译文" : "Copy translation"}
          >
            {copied ? (
              <CheckCheck className="size-3.5 text-emerald-600" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-sm leading-relaxed whitespace-pre-wrap break-words">
        {translating && !text ? (
          <div className="h-full flex items-center justify-center text-muted-foreground/70 text-xs">
            <Loader2 className="size-4 animate-spin mr-2" />
            {uiLang === "zh" ? "翻译中…" : "Translating…"}
          </div>
        ) : hasError ? (
          <span className="text-destructive">{result?.error}</span>
        ) : text ? (
          text
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground/70 text-xs">
            {uiLang === "zh" ? "输入文字后点翻译" : "Enter text and click Translate"}
          </div>
        )}
      </div>
    </>
  );
}

// ── Multi-language: stacked sub-cards ────────────────────────────────

function MultiResults({
  codes,
  results,
  translating,
  uiLang,
}: {
  codes: string[];
  results: Record<string, TextTranslateResult> | null;
  translating: boolean;
  uiLang: "zh" | "en";
}) {
  const doneCount = results
    ? codes.filter((c) => results[c]?.translated && !results[c]?.error).length
    : 0;

  return (
    <>
      <div className="h-9 px-3 border-b border-border flex items-center justify-between text-xs shrink-0">
        <span>
          <span className="font-medium">{uiLang === "zh" ? "译文" : "Translations"}</span>
          <span className="ml-1.5 text-muted-foreground font-normal">
            · {uiLang === "zh" ? `${codes.length} 种语言` : `${codes.length} languages`}
          </span>
        </span>
        {results && (
          <span className="text-muted-foreground tabular-nums">
            {uiLang === "zh"
              ? `${doneCount}/${codes.length} 完成`
              : `${doneCount}/${codes.length} done`}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {translating && !results && (
          <div className="flex-1 flex items-center justify-center text-muted-foreground/70 text-xs">
            <Loader2 className="size-4 animate-spin mr-2" />
            {uiLang === "zh" ? "翻译中…" : "Translating…"}
          </div>
        )}
        {!translating && !results && (
          <div className="flex-1 flex items-center justify-center text-muted-foreground/70 text-xs">
            {uiLang === "zh" ? "输入文字后点翻译" : "Enter text and click Translate"}
          </div>
        )}
        {results &&
          codes.map((code) => (
            <SubResultCard
              key={code}
              code={code}
              result={results[code]}
              uiLang={uiLang}
            />
          ))}
      </div>
    </>
  );
}

function SubResultCard({
  code,
  result,
  uiLang,
}: {
  code: string;
  result?: TextTranslateResult;
  uiLang: "zh" | "en";
}) {
  const [copied, setCopied] = useState(false);
  if (!result) return null;

  async function handleCopy() {
    if (!result?.translated) return;
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
    <div className="bg-muted/30 border border-border rounded-lg overflow-hidden">
      <div className="h-8 px-3 border-b border-border flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 min-w-0">
          <span className="font-medium truncate">{langDisplay(code, uiLang)}</span>
          <span className="text-muted-foreground">{code}</span>
          {result.elapsed_seconds > 0 && (
            <span className="text-muted-foreground/70">
              · {formatDuration(result.elapsed_seconds)}
            </span>
          )}
        </span>
        {!hasError && result.translated && (
          <button
            onClick={handleCopy}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted -mr-1"
            title={uiLang === "zh" ? "复制" : "Copy"}
          >
            {copied ? (
              <CheckCheck className="size-3.5 text-emerald-600" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        )}
      </div>
      <div className="p-3 text-sm leading-relaxed whitespace-pre-wrap break-words">
        {hasError ? (
          <span className="text-destructive">{result.error}</span>
        ) : (
          result.translated
        )}
      </div>
    </div>
  );
}
