"use client";

import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** A physical switch: the pressed state is inset. */
export function NeuToggle({ pressed, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { pressed: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      className={cn(
        "focus-ring min-h-touch rounded-control px-4 text-sm font-semibold transition-all duration-ui ease-out",
        pressed ? "text-accent-text shadow-neu-inset-sm" : "text-muted shadow-neu-sm hover:-translate-y-px hover:text-fg hover:shadow-neu-hover",
        className,
      )}
      {...props}
    />
  );
}
