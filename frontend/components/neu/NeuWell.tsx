import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Deep inset container for numbers, icons and charts. */
export function NeuWell({ className, shallow, ...props }: HTMLAttributes<HTMLDivElement> & { shallow?: boolean }) {
  return <div className={cn("rounded-panel bg-bg p-4", shallow ? "shadow-neu-inset" : "shadow-neu-inset-deep", className)} {...props} />;
}
