import { Bell, BellRing } from "lucide-react";
import type { PriceAlert } from "../types";
import { alertLevels } from "../utils/alerts";

/** Small chips: armed = muted bell + levels; triggered = highlighted badge with date/price. */
export function AlertChips({ alerts }: { alerts?: PriceAlert[] }) {
  if (!alerts?.length) return null;
  return (
    <span className="alert-chips">
      {alerts.map((a) => {
        const hit = a.status === "triggered";
        const title = hit
          ? `${a.label} — triggered ${a.triggeredDate} @ ₹${a.triggeredPrice}${a.volVs20d != null ? ` (vol ${a.volVs20d}× 20d)` : ""}`
          : `${a.label} — armed since ${a.createdDate}`;
        return (
          <span key={a.id} className={`alert-chip ${hit ? "hit" : "armed"}`} title={title}>
            {hit ? <BellRing size={11} aria-hidden /> : <Bell size={11} aria-hidden />}
            {alertLevels(a)}
            {hit && a.triggeredDate ? <span className="alert-when">hit {a.triggeredDate.slice(5)}</span> : null}
          </span>
        );
      })}
    </span>
  );
}
