import { BookOpen } from "lucide-react";
import { useLanguage } from "../contexts/LanguageContext";

interface TranslationModeSelectorProps {
  useGlossary: boolean;
  onUseGlossaryChange: (value: boolean) => void;
}

export function TranslationModeSelector({ useGlossary, onUseGlossaryChange }: TranslationModeSelectorProps) {
  const { t } = useLanguage();
  return (
    <button
      role="switch"
      aria-checked={useGlossary}
      onClick={() => onUseGlossaryChange(!useGlossary)}
      className={`
        inline-flex items-center gap-1 flex-shrink-0 cursor-pointer
        px-2.5 py-1 rounded-md text-xs font-medium
        select-none transition-all duration-200
        ${useGlossary
          ? 'bg-foreground text-background'
          : 'bg-muted text-muted-foreground'
        }
      `}
    >
      <BookOpen className="size-3" />
      {t('mode.glossaryToggle')}
    </button>
  );
}
