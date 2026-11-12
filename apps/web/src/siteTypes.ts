export type View = "home" | "dashboard" | "ledger";
export type Go = (view: View, anchor?: string) => void;
export type RecordRow = { id: string; task: string; provider: string; state: string; costMicro: number | null; receipt: string | null; verification: string; apiCreditMicro?: number | null };
export type PolicyRow = { policy: string; outcomes: number; strict_correct: number; actual_paid_receipts: number; provider_micro_usdz: number; provider_micro_usdz_per_strict_correct: number | null; reported_api_credit_estimate_micro_usd: number; api_calls_with_unreported_usage: number; conservative_api_credit_exposure_micro_usd: number };
export type PolicyComparisonData = { completed: number; expected: number; complete: boolean; liveGatePassed: boolean; paidReceipts: number; attempts: number; providerUsdz: number; policies: PolicyRow[] };
export type Evidence = { date: string; calibrationCorrect: number; calibrationTotal: number; holdoutCorrect: number; holdoutTotal: number; holdUsd: number; captureUsd: number; modelUsdz: number; creditUsd: number; creditCeilingUsd: number; products: number; oauthVerified: boolean; records: RecordRow[]; comparison?: PolicyComparisonData | null };
