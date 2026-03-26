import { type ReactNode, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

type PhaseStatus = "pending" | "active" | "done";

interface PhaseCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  status: PhaseStatus;
  defaultOpen?: boolean;
  children?: ReactNode;
}

export function PhaseCard({
  icon,
  title,
  description,
  status,
  defaultOpen = true,
  children,
}: PhaseCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const hasChildren = children != null;

  return (
    <div
      className={[
        "bg-card border border-border rounded-lg px-3 py-2.5",
        "shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)]",
        "transition-[transform,box-shadow,background-color] duration-300 ease-out",
        "hover:-translate-y-px hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),0_4px_12px_rgba(0,0,0,0.04)] hover:bg-accent/30",
        status === "active" ? "shadow-[0_2px_6px_rgba(0,0,0,0.06),0_4px_14px_rgba(0,0,0,0.04)]" : "",
        status === "done" ? "opacity-70" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        className={[
          "flex items-center gap-2",
          hasChildren ? "cursor-pointer select-none" : "",
        ].join(" ")}
        onClick={hasChildren ? () => setOpen((v) => !v) : undefined}
      >
        {hasChildren ? (
          <span className="text-muted-foreground flex-shrink-0">
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </span>
        ) : (
          <span className="text-muted-foreground flex-shrink-0">{icon}</span>
        )}
        <span className="text-sm font-medium">{title}</span>
        {description && <span className="text-xs text-muted-foreground">{description}</span>}
      </div>
      {hasChildren && open && <div className="overflow-hidden">{children}</div>}
    </div>
  );
}
