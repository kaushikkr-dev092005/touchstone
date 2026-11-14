import { Icon } from "./Identity";
import type { Evidence, Go, View } from "@/siteTypes";

// Share the canonical design; the anonymous build never includes operator scripts.
export default function Workspace({ view, operator }: { view: View; evidence: Evidence | null; go: Go; operator: boolean }) {
  const ledger = view === "ledger";
  const source = operator ? "/console?embedded=1" : "/site/dashboard/index.html";
  return <section className="operator-workspace">
    <div className="operator-strip section-width">
      <span className="mono"><i className="status-dot" />{operator ? "OPERATOR WORKSPACE / CURRENT CONSOLE" : "CURRENT DASHBOARD / SAVED EVIDENCE / READ ONLY"}</span>
      <a href={source + (ledger ? "#transactions" : "#v-overview")}>Open {ledger ? "ledger" : "dashboard"} directly <Icon name="arrow" size={14} /></a>
    </div>
    <iframe key={view} src={source + (ledger ? "#transactions" : "#v-overview")}
      title={operator ? (ledger ? "Touchstone transaction ledger" : "Touchstone operator dashboard") : (ledger ? "Touchstone saved transaction ledger" : "Touchstone saved dashboard")}
      {...(!operator ? { sandbox: "allow-scripts allow-same-origin allow-downloads" } : {})} />
  </section>;
}
