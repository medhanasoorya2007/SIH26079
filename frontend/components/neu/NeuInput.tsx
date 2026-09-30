import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const field =
  "focus-ring min-h-touch w-full rounded-control bg-bg px-4 text-sm text-fg shadow-neu-inset-sm transition-shadow duration-ui placeholder:text-placeholder";

export const NeuInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function NeuInput({ className, ...p }, ref) {
  return <input ref={ref} className={cn(field, className)} {...p} />;
});

export const NeuSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function NeuSelect({ className, ...p }, ref) {
  return <select ref={ref} className={cn(field, "appearance-none pr-8", className)} {...p} />;
});
