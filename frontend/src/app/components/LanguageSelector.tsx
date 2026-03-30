import { useState, useEffect } from "react";
import { Input } from "./ui/input";
import { Search, X, Plus, Check } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "./ui/popover";
import { ScrollArea } from "./ui/scroll-area";
import type { Language } from "../types/translation";
import { fetchLanguages } from "../api";
import { useLanguage } from "../contexts/LanguageContext";

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

interface LanguageSelectorProps {
  selectedLanguages: Language[];
  onLanguagesChange: (languages: Language[]) => void;
  variant?: "compact" | "inline";
}

export function LanguageSelector({ selectedLanguages, onLanguagesChange, variant = "compact" }: LanguageSelectorProps) {
  const { t, language: uiLang } = useLanguage();
  const displayName = (lang: Language) =>
    LANG_NAMES[lang.code]?.[uiLang] || lang.name;
  const [searchQuery, setSearchQuery] = useState("");
  const [availableLanguages, setAvailableLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchLanguages()
      .then((langs) => setAvailableLanguages(langs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filteredLanguages = availableLanguages.filter(
    (lang) => {
      const q = searchQuery.toLowerCase();
      return displayName(lang).toLowerCase().includes(q) ||
        lang.name.toLowerCase().includes(q) ||
        lang.code.toLowerCase().includes(q);
    }
  );

  const isSelected = (lang: Language) =>
    selectedLanguages.some((l) => l.code === lang.code);

  const toggleLanguage = (lang: Language) => {
    if (isSelected(lang)) {
      onLanguagesChange(selectedLanguages.filter((l) => l.code !== lang.code));
    } else {
      onLanguagesChange([...selectedLanguages, lang]);
    }
  };

  const removeLanguage = (code: string) => {
    onLanguagesChange(selectedLanguages.filter((l) => l.code !== code));
  };

  // ── Inline variant: search + list directly in card ──
  if (variant === "inline") {
    return (
      <div>
        <h3 className="text-xs font-medium text-muted-foreground mb-3">
          {t("lang.title")}
        </h3>
        {loading ? (
          <div className="text-center py-2 text-muted-foreground text-xs">Loading...</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {[...availableLanguages].sort((a, b) => displayName(a).length - displayName(b).length).map((lang) => {
              const selected = isSelected(lang);
              return (
                <button
                  key={lang.code}
                  onClick={() => toggleLanguage(lang)}
                  className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                    selected
                      ? "bg-foreground/80 text-background"
                      : "bg-card text-muted-foreground hover:bg-card/80"
                  }`}
                >
                  {displayName(lang)}
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ── Compact variant (default): tags + popover ──
  return (
    <div>
      <h3 className="text-xs font-medium text-muted-foreground mb-1.5">
        {t("lang.title")}
      </h3>

      <div className="flex flex-wrap gap-1.5 items-center">
        {selectedLanguages.map((lang) => (
          <span
            key={lang.code}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-accent text-accent-foreground text-xs"
          >
            {lang.code.toUpperCase()}
            <button
              onClick={() => removeLanguage(lang.code)}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}

        <Popover>
          <PopoverTrigger asChild>
            <button className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-dashed border-border text-xs text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors">
              <Plus className="size-3" />
              {selectedLanguages.length === 0 ? t("lang.selectLanguages") : t("common.add")}
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-56 p-0">
            <div className="p-2 border-b border-border">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
                <Input
                  placeholder={t("lang.selectLanguages")}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-7 pl-7 text-xs"
                />
              </div>
            </div>
            {loading ? (
              <div className="text-center py-4 text-muted-foreground text-xs">Loading...</div>
            ) : (
              <ScrollArea className="max-h-52">
                <div className="p-1">
                  {filteredLanguages.map((lang) => {
                    const selected = isSelected(lang);
                    return (
                      <button
                        key={lang.code}
                        onClick={() => toggleLanguage(lang)}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded text-xs transition-colors ${
                          selected
                            ? "bg-accent text-accent-foreground"
                            : "text-foreground hover:bg-accent/50"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {selected && <Check className="size-3 flex-shrink-0" />}
                          {!selected && <span className="w-3" />}
                          <span>{displayName(lang)}</span>
                        </div>
                        <span className="text-xs text-muted-foreground uppercase">
                          {lang.code}
                        </span>
                      </button>
                    );
                  })}
                  {filteredLanguages.length === 0 && (
                    <div className="text-center py-4 text-muted-foreground text-xs">
                      {t("glossary.noTerms")}
                    </div>
                  )}
                </div>
              </ScrollArea>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
