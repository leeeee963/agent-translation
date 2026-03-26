interface TranslationModeSelectorProps {
  useGlossary: boolean;
  onUseGlossaryChange: (value: boolean) => void;
}

export function TranslationModeSelector({ useGlossary, onUseGlossaryChange }: TranslationModeSelectorProps) {
  return (
    <button
      role="switch"
      aria-checked={useGlossary}
      onClick={() => onUseGlossaryChange(!useGlossary)}
      className={`
        inline-flex items-center justify-center flex-shrink-0 cursor-pointer
        px-3 py-1.5 rounded-md text-xs font-bold tracking-widest
        select-none transition-all duration-200
        ${useGlossary
          ? 'bg-foreground text-background'
          : 'bg-muted text-muted-foreground'
        }
      `}
    >
      PRO
    </button>
  );
}
