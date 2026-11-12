// Every duration used by the intro, the Dashboard transition and the return path.
// Times are seconds. Edit here; nothing else hard-codes choreography timing.

export type VaultPhases = {
  safeIn: number;     // fade/blur/scale in
  locked: number;     // held beat, LED blink, dial ticks
  unlock: number;     // dial spins, handle turns, LED red -> green
  doorOpen: number;   // door slides out along the rail
  keyReveal: number;  // drawer out, key rises and holds
  keyStow: number;    // key down, drawer in
  doorClose: number;  // exact reverse of doorOpen, seam pulse
  safeOut: number;    // seam contracts to a point, vault dissolves
};

export const TIMELINE = {
  intro: {
    black: 0.7,
    vault: { safeIn: 1.1, locked: 0.8, unlock: 1.0, doorOpen: 1.3, keyReveal: 1.2, keyStow: 0.6, doorClose: 1.0, safeOut: 1.1 } as VaultPhases,
    /** holeIgnite starts this long before safeOut ends (overlap keeps it continuous). */
    igniteOverlap: 0.3,
    holeIgnite: 1.7,
    /** heroIn starts this long before holeIgnite ends. */
    heroOverlap: 0.4,
    heroIn: 1.4,
  },
  dashboard: {
    heroOut: 0.5,
    vault: { safeIn: 0.9, locked: 0.15, unlock: 0.8, doorOpen: 1.0, keyReveal: 0.8, keyStow: 0.45, doorClose: 0.55, safeOut: 0.8 } as VaultPhases,
    /** The seam point expands into the ledger's top edge. */
    seamExpand: 0.55,
    ledgerIn: 1.0,
  },
  returning: { black: 0.25, holeIgnite: 1.6, heroOverlap: 0.5, heroIn: 1.2 },
  reduced: { crossfade: 0.6 },
  /** Hero stagger between elements. */
  stagger: 0.08,
  /** Skip ramps timeScale up to this over `skipRamp` seconds instead of jumping. */
  skipTimeScale: 14,
  skipRamp: 0.45,
} as const;

export const vaultTotal = (v: VaultPhases) => v.safeIn + v.locked + v.unlock + v.doorOpen + v.keyReveal + v.keyStow + v.doorClose + v.safeOut;

export const INTRO_STATES = ["black", "safeIn", "locked", "unlock", "doorOpen", "keyReveal", "keyStow", "doorClose", "safeOut", "holeIgnite", "heroIn", "done"] as const;
export type IntroState = (typeof INTRO_STATES)[number];

/** Absolute start time of each state for the full intro (used by the controller and debug label). */
export function introSchedule() {
  const t = TIMELINE.intro, v = t.vault;
  const s: Record<IntroState, number> = {} as Record<IntroState, number>;
  let c = 0;
  s.black = 0; c += t.black;
  for (const k of ["safeIn", "locked", "unlock", "doorOpen", "keyReveal", "keyStow", "doorClose", "safeOut"] as const) { s[k] = c; c += v[k]; }
  s.holeIgnite = c - t.igniteOverlap;
  s.heroIn = s.holeIgnite + t.holeIgnite - t.heroOverlap;
  s.done = s.heroIn + t.heroIn;
  return s;
}
