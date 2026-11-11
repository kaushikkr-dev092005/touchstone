export type View = "home" | "dashboard" | "ledger";
export type Go = (view: View, anchor?: string) => void;
export type RecordRow = { id: string; task: string; provider: string; state: string; costMicro: number | null; receipt: string | null; verification: string };
export type Evidence = { date: string; calibrationCorrect: number; calibrationTotal: number; holdoutCorrect: number; holdoutTotal: number; holdUsd: number; captureUsd: number; modelUsdz: number; creditUsd: number; creditCeilingUsd: number; products: number; oauthVerified: boolean; records: RecordRow[] };
