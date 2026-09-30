import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeuCardProps extends HTMLAttributes<HTMLDivElement> {
  /** compact panels use the 24px radius */
  compact?: boolean;
  /** lift on hover (for clickable cards) */
  interactive?: boolean;
}

/** Extruded surface molded from the page material. */
export const NeuCard = forwardRef<HTMLDivElement, NeuCardProps>(function NeuCard({ className, compact, interactive, ...props }, ref) {
  return (
    <div
      ref={ref}
      className={cn(
        "bg-bg shadow-neu",
        compact ? "rounded-panel p-5" : "rounded-card p-6 md:p-8",
        interactive && "transition-all duration-ui ease-out hover:-translate-y-0.5 hover:shadow-neu-hover",
        className,
      )}
      {...props}
    />
  );
});
