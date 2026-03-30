import { type ReactNode } from "react";
import { cn } from "../ui/utils";

interface PanelProps {
  title?: string;
  headerRight?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, headerRight, footer, children, className }: PanelProps) {
  return (
    <div className={cn("flex flex-col bg-card border border-border rounded-xl overflow-hidden", className)}>
      {title && (
        <div className="px-6 py-3.5 border-b border-border flex items-center justify-between flex-shrink-0">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {headerRight}
        </div>
      )}
      <div className="flex-1 overflow-y-auto">{children}</div>
      {footer && <div className="border-t border-border flex-shrink-0">{footer}</div>}
    </div>
  );
}
