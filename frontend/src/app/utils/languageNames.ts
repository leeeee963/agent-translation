/**
 * Shared display names for the supported language codes.
 *
 * Used by both LanguageSelector (file translation) and TextTranslatePanel
 * (text translation) so the two surfaces show identical labels.
 */

export const LANG_NAMES: Record<string, { zh: string; en: string }> = {
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

export function langDisplay(code: string, uiLang: "zh" | "en"): string {
  return LANG_NAMES[code]?.[uiLang] ?? code;
}
