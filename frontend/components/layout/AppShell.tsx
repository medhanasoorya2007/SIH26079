"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Gauge, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { NeuButton, NeuCard } from "@/components/neu";
import { cn } from "@/lib/utils";
import { useAppState } from "./AppState";
import { DatePicker } from "./DatePicker";
import { BRAND } from "@/lib/brand";

const NAV = [
  { href: "/", label: "Console" },
  { href: "/blindspots", label: "Blind-spots" },
  { href: "/scorecard", label: "Scorecard" },
  { href: "/evidence", label: "Evidence" },
  { href: "/replay", label: "Replay" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { meta, error } = useAppState();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-bg">
      <a href="#main" className="focus-ring sr-only rounded-control bg-bg px-4 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:shadow-neu">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 bg-bg/80 shadow-neu-sm backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 md:px-8">
          <Link href="/" className="focus-ring flex items-center gap-3 rounded-control pr-2">
            <span className="grid h-11 w-11 place-items-center rounded-control bg-bg shadow-neu-sm">
              <Gauge className="h-5 w-5 text-accent-text" aria-hidden />
            </span>
            <span className="leading-tight">
              <span className="block font-display text-lg font-extrabold tracking-tight text-fg">{BRAND}</span>
              <span className="hidden text-[11px] font-medium text-muted sm:block">Forecast bust detection · SIH26079</span>
            </span>
          </Link>
          <nav aria-label="Main" className="ml-4 hidden gap-2 lg:flex">
            {NAV.map((n) => {
              const on = n.href === "/" ? path === "/" : path.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={on ? "page" : undefined}
                  className={cn(
                    "focus-ring flex min-h-touch items-center rounded-control px-4 text-sm font-semibold transition-all duration-ui",
                    on ? "text-accent-text shadow-neu-inset-sm" : "text-muted hover:-translate-y-px hover:text-fg",
                  )}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto hidden md:block">
            <DatePicker />
          </div>
          <NeuButton size="icon" className="ml-auto md:ml-0 lg:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <X className="h-5 w-5" aria-hidden /> : <Menu className="h-5 w-5" aria-hidden />}
          </NeuButton>
        </div>
        <AnimatePresence>
          {open && (
            <motion.nav
              aria-label="Main (mobile)"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="overflow-hidden lg:hidden"
            >
              <div className="flex flex-col gap-2 px-4 pb-4">
                <div className="md:hidden">
                  <DatePicker compact />
                </div>
                {NAV.map((n) => (
                  <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className="focus-ring flex min-h-touch items-center rounded-control px-4 text-sm font-semibold text-fg shadow-neu-sm">
                    {n.label}
                  </Link>
                ))}
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>
      {meta?.is_synthetic && (
        <div role="alert" className="mx-auto mt-6 max-w-7xl px-4 md:px-8">
          <NeuCard compact className="text-sm font-bold text-risk-high-text">
            {meta.banner}
          </NeuCard>
        </div>
      )}
      {error && (
        <div role="alert" className="mx-auto mt-6 max-w-7xl px-4 md:px-8">
          <NeuCard compact className="text-sm font-semibold text-risk-high-text">
            {error}
          </NeuCard>
        </div>
      )}
      <main id="main" className="mx-auto max-w-7xl px-4 py-8 md:px-8 md:py-10">
        {children}
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-muted md:px-8">
        Forecasts: ECMWF IFS HRES via WeatherBench 2 · Truth: IMD 0.25° gridded rainfall · Moisture: ERA5. Subdivision shapes are derived from the IMD grid.
      </footer>
    </div>
  );
}
