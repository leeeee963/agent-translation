import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2 } from "lucide-react";

export interface Step {
  label: string;
  status: "pending" | "active" | "done" | "error";
}

interface StepIndicatorProps {
  steps: Step[];
}

export function StepIndicator({ steps }: StepIndicatorProps) {
  const activeIndex = steps.findIndex((s) => s.status === "active");

  return (
    <div className="flex w-full">
      {steps.map((step, i) => {
        const isFirst = i === 0;
        const isLast = i === steps.length - 1;
        const isDone = step.status === "done";
        const isActive = step.status === "active";
        const isError = step.status === "error";
        const filled = isDone || isActive;

        const leftLineFilled = i > 0 && filled && (steps[i - 1].status === "done");
        const rightLineFilled = !isLast && isDone && (steps[i + 1].status === "done" || steps[i + 1].status === "active");

        return (
          <div key={i} className="flex-1 flex flex-col items-center">
            <div className="relative w-full flex items-center justify-center h-3">
              {!isFirst && (
                <div
                  className={`absolute left-0 right-1/2 top-1/2 -translate-y-1/2 h-[1.5px] rounded-full ${
                    leftLineFilled ? "bg-foreground/40" : "bg-muted-foreground/15"
                  }`}
                />
              )}
              {!isLast && (
                <div
                  className={`absolute left-1/2 right-0 top-1/2 -translate-y-1/2 h-[1.5px] rounded-full ${
                    rightLineFilled ? "bg-foreground/40" : "bg-muted-foreground/15"
                  }`}
                />
              )}
              <div className="relative z-10">
                <div
                  className={[
                    "w-2.5 h-2.5 rounded-full",
                    isError
                      ? "bg-destructive"
                      : filled
                        ? "bg-foreground"
                        : "border-[1.5px] border-muted-foreground/30 bg-background",
                  ].join(" ")}
                />
                {isActive && (
                  <span className="absolute -inset-1 rounded-full bg-foreground/20 animate-ping" />
                )}
              </div>
            </div>
            <span
              className={[
                "text-xs mt-1.5 text-center leading-tight",
                isError
                  ? "text-destructive font-medium"
                  : isActive
                    ? "text-foreground font-semibold"
                    : isDone
                      ? "text-foreground"
                      : "text-muted-foreground",
              ].join(" ")}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Compact badge showing current step, hover to see full timeline */
export function StepBadge({ steps }: StepIndicatorProps) {
  const [hover, setHover] = useState(false);
  const badgeRef = useRef<HTMLDivElement>(null);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});

  // Position the portal popover relative to the badge
  useEffect(() => {
    if (hover && badgeRef.current) {
      const rect = badgeRef.current.getBoundingClientRect();
      setPopoverStyle({
        position: "fixed",
        top: rect.bottom + 8,
        right: window.innerWidth - rect.right,
        zIndex: 9999,
      });
    }
  }, [hover]);

  const activeStep = steps.find((s) => s.status === "active");
  const errorStep = steps.find((s) => s.status === "error");
  const allDone = steps.every((s) => s.status === "done");
  const currentStep = errorStep ?? activeStep;

  const doneCount = steps.filter((s) => s.status === "done").length;

  let label: string;
  let dotClass: string;
  let textClass: string;
  let badgeBg: string;

  if (allDone) {
    label = steps[steps.length - 1].label;
    dotClass = "";
    textClass = "text-foreground";
    badgeBg = "bg-muted/60";
  } else if (errorStep) {
    label = errorStep.label;
    dotClass = "bg-destructive";
    textClass = "text-destructive";
    badgeBg = "bg-destructive/10";
  } else if (currentStep) {
    label = currentStep.label;
    dotClass = "bg-foreground animate-pulse";
    textClass = "text-foreground";
    badgeBg = "bg-muted/60";
  } else {
    label = steps[0].label;
    dotClass = "bg-muted-foreground/40";
    textClass = "text-muted-foreground";
    badgeBg = "bg-muted/40";
  }

  return (
    <div
      ref={badgeRef}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* Compact badge */}
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs cursor-default select-none ${badgeBg}`}>
        {allDone ? (
          <CheckCircle2 className="size-3 text-foreground" />
        ) : (
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotClass}`} />
        )}
        <span className={`font-medium whitespace-nowrap ${textClass}`}>{label}</span>
        {!allDone && (
          <span className="text-muted-foreground">{doneCount}/{steps.length}</span>
        )}
      </div>

      {/* Portal popover — renders on document.body, never clipped */}
      {hover && createPortal(
        <div
          style={popoverStyle}
          className="w-72 p-4 rounded-lg border border-border bg-popover shadow-lg"
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
        >
          <StepIndicator steps={steps} />
        </div>,
        document.body,
      )}
    </div>
  );
}
