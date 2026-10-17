import type { ZoneKind } from "../utils/zone";
import { ZONE_LABEL } from "../utils/zone";

export function ZoneChip({ kind, short }: { kind: ZoneKind; short?: boolean }) {
  const label = short && kind === "wait" ? "Waiting" : ZONE_LABEL[kind];
  return (
    <span className={`zone zone-${kind}`} title={ZONE_LABEL[kind]}>
      <span className="zone-dot" aria-hidden />
      {label}
    </span>
  );
}
