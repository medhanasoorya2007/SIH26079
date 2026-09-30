"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { BookmarkPlus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NeuButton, NeuCard } from "@/components/neu";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { Meta } from "@/types/api";
import { AlertCard } from "./AlertCard";
import { AnalogList } from "./AnalogList";
import { DriverBreakdown } from "./DriverBreakdown";
import { LeadStrip } from "./LeadStrip";
import { PathwayChain } from "./PathwayChain";

function useIsDesktop() {
  const [d, setD] = useState(true);
  useEffect(() => {
    const q = window.matchMedia("(min-width: 1024px)");
    const on = () => setD(q.matches);
    on();
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);
  return d;
}

/** Extruded side panel (desktop) / bottom sheet (mobile) with the full region analysis. */
export function RegionDrawer({
  regionId,
  date,
  variable,
  lead,
  setLead,
  meta,
  onClose,
}: {
  regionId?: string;
  date?: string;
  variable: string;
  lead: number;
  setLead: (l: number) => void;
  meta?: Meta;
  onClose: () => void;
}) {
  const desktop = useIsDesktop();
  const reduce = useReducedMotion();
  const open = !!regionId;
  const { data, error, loading } = useApi(open && date ? `${regionId}|${date}|${variable}` : null, () => api.region(regionId!, date, variable));
  const cur = data?.leads.find((l) => l.lead_day === lead) ?? data?.leads[0];
  const [saved, setSaved] = useState<string>();
  useEffect(() => setSaved(undefined), [regionId, date, lead]);

  const save = async () => {
    if (!data || !cur) return;
    try {
      await api.saveAnalysis({ title: `${data.region.name}: Day ${cur.lead_day} ${cur.risk} risk`, date: data.date, lead: cur.lead_day, variable, region_id: data.region.id });
      setSaved("Saved to analyses");
    } catch {
      setSaved("Could not save");
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()} modal={!desktop}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            {!desktop && (
              <Dialog.Overlay asChild forceMount>
                <motion.div className="fixed inset-0 z-40 bg-fg/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
              </Dialog.Overlay>
            )}
            <Dialog.Content
              asChild
              forceMount
              onInteractOutside={(e) => desktop && e.preventDefault()}
              aria-describedby={undefined}
            >
              <motion.div
                className={
                  desktop
                    ? "fixed bottom-4 right-4 top-24 z-50 w-[min(560px,calc(100vw-2rem))] overflow-y-auto rounded-card bg-bg shadow-neu-hover focus:outline-none"
                    : "fixed inset-x-0 bottom-0 z-50 max-h-[88vh] overflow-y-auto rounded-t-card bg-bg shadow-neu-hover focus:outline-none"
                }
                initial={desktop ? { x: reduce ? 0 : 40, opacity: 0 } : { y: reduce ? 0 : 60, opacity: 0 }}
                animate={{ x: 0, y: 0, opacity: 1 }}
                exit={desktop ? { x: reduce ? 0 : 40, opacity: 0 } : { y: reduce ? 0 : 60, opacity: 0 }}
                transition={{ duration: reduce ? 0 : 0.3, ease: "easeOut" }}
              >
                <div className="space-y-6 p-6 md:p-8">
                  <div className="flex items-center justify-between gap-3">
                    <Dialog.Title className="text-xs font-bold uppercase tracking-wide text-muted">Region analysis</Dialog.Title>
                    <Dialog.Close asChild>
                      <NeuButton size="icon" aria-label="Close region analysis">
                        <X className="h-4 w-4" aria-hidden />
                      </NeuButton>
                    </Dialog.Close>
                  </div>
                  {loading && !data && <p className="text-sm text-muted">Loading…</p>}
                  {error && <p className="text-sm font-semibold text-risk-high-text">{error.message}</p>}
                  {data && cur && (
                    <>
                      <AlertCard region={data.region.name} lead={cur} variable={variable} riskWindow={data.risk_window} baseRate={meta?.headline.base_rate} />
                      <NeuCard compact>
                        <LeadStrip leads={data.leads} value={cur.lead_day} onChange={setLead} />
                      </NeuCard>
                      <NeuCard compact>
                        <DriverBreakdown families={cur.families} all={meta?.families ?? cur.families.map((f) => f.family)} labels={meta?.family_labels ?? {}} />
                      </NeuCard>
                      <NeuCard compact>
                        <PathwayChain steps={cur.pathway} regime={cur.regime} />
                      </NeuCard>
                      <NeuCard compact>
                        <h3 className="mb-3 text-sm font-bold text-fg">Why the risk is elevated</h3>
                        {cur.reasons.length ? (
                          <ul className="space-y-2 text-sm">
                            {cur.reasons.map((r) => (
                              <li key={r.feature} className="rounded-control bg-bg p-3 shadow-neu-inset-sm">
                                {r.text}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-xs text-muted">No single factor raises the risk noticeably for this forecast.</p>
                        )}
                      </NeuCard>
                      <NeuCard compact>
                        <AnalogList analogs={cur.analogs} />
                      </NeuCard>
                      <div className="flex items-center gap-3">
                        <NeuButton variant="primary" onClick={save}>
                          <BookmarkPlus className="h-4 w-4" aria-hidden />
                          Save analysis
                        </NeuButton>
                        <span role="status" className="text-xs text-muted">
                          {saved}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
