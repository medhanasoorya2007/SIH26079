import type { Family } from "@/types/api";

/** Horizontal bars per signal family: share of the bust-raising (SHAP) signal. */
export function DriverBreakdown({ families, all, labels }: { families: Family[]; all: string[]; labels: Record<string, string> }) {
  const by = new Map(families.map((f) => [f.family, f]));
  const rows = all.map((f) => ({ family: f, label: labels[f] ?? f, item: by.get(f) }));
  rows.sort((a, b) => (b.item?.pct ?? -1) - (a.item?.pct ?? -1));
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-fg">Driver breakdown</h3>
        <span className="text-[11px] text-muted">contribution to bust risk</span>
      </div>
      <ul className="space-y-2.5">
        {rows.map(({ family, label, item }) => (
          <li key={family} className="grid grid-cols-[8.5rem_1fr_3rem] items-center gap-3 text-xs">
            <span className="truncate font-semibold text-fg">{label}</span>
            <span className="h-3 overflow-hidden rounded-full bg-bg shadow-neu-inset-sm" role="presentation">
              <span className="block h-full rounded-full bg-accent transition-all duration-dial" style={{ width: `${item?.pct ?? 0}%` }} />
            </span>
            <span className="text-right font-semibold tabular text-muted">{item ? `${item.pct.toFixed(0)}%` : "n/a"}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] leading-relaxed text-muted">
        Share of the model&apos;s bust-raising signal (TreeSHAP) per feature family. &ldquo;n/a&rdquo;: family not available in this build (e.g. no second model for disagreement).
      </p>
    </div>
  );
}
