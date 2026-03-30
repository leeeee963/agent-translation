import { type ReactNode } from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "../ui/tooltip";

interface SidebarIconProps {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function SidebarIcon({ icon, label, active, onClick }: SidebarIconProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          className={[
            "flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-200",
            active
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
          ].join(" ")}
        >
          {icon}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right" sideOffset={8}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

interface SidebarProps {
  navItems: { icon: ReactNode; label: string; active?: boolean; onClick?: () => void }[];
  bottomItems: { icon: ReactNode; label: string; onClick?: () => void }[];
}

export function Sidebar({ navItems, bottomItems }: SidebarProps) {
  return (
    <nav aria-label="Main navigation" className="w-14 h-screen flex flex-col items-center justify-between border-r border-border bg-card flex-shrink-0 py-3">
      <div />

      <div className="space-y-8">
        {navItems.map((item) => (
          <SidebarIcon key={item.label} {...item} />
        ))}
      </div>

      <div className="space-y-1">
        {bottomItems.map((item) => (
          <SidebarIcon key={item.label} {...item} />
        ))}
      </div>
    </nav>
  );
}
