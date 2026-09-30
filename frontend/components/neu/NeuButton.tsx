import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "focus-ring inline-flex min-h-touch items-center justify-center gap-2 rounded-control px-5 text-sm font-semibold transition-all duration-ui ease-out hover:-translate-y-px active:translate-y-0.5 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        // dark accent shade keeps white text at >= 4.5:1 contrast
        primary: "bg-accent-text text-white shadow-neu-sm hover:shadow-neu-hover active:shadow-neu-inset-sm",
        secondary: "bg-bg text-fg shadow-neu-sm hover:shadow-neu-hover active:shadow-neu-inset-sm",
        ghost: "bg-bg text-muted hover:text-fg active:shadow-neu-inset-sm",
      },
      size: { md: "", sm: "px-4 text-xs", icon: "w-11 px-0" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface NeuButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const NeuButton = forwardRef<HTMLButtonElement, NeuButtonProps>(function NeuButton({ className, variant, size, asChild, ...props }, ref) {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
});
