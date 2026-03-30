import { type ReactNode } from "react";

interface WorkspaceLayoutProps {
  showLeft?: boolean;
  leftPanel: ReactNode;
  rightPanel: ReactNode;
  overlay?: ReactNode;
  showOverlay?: boolean;
}

export function WorkspaceLayout({ showLeft = true, leftPanel, rightPanel, overlay, showOverlay = false }: WorkspaceLayoutProps) {
  return (
    <div className="flex-1 min-w-0 relative h-screen overflow-hidden">
      {/* Main dual-column layout */}
      <div className="h-full flex gap-5 p-8">
        {/* Left panel */}
        {showLeft && (
          <div className="w-1/4 flex-shrink-0 min-w-0 flex">
            {leftPanel}
          </div>
        )}
        {/* Right panel */}
        <div className="flex-1 min-w-0 flex">
          {rightPanel}
        </div>
      </div>

      {/* Full-screen overlay (e.g. library) */}
      {overlay && (
        <div
          className={`absolute inset-0 z-50 bg-background p-8 transition-all duration-300 ease-out ${
            showOverlay
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-2 pointer-events-none"
          }`}
        >
          {overlay}
        </div>
      )}
    </div>
  );
}
