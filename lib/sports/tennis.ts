// Pure tennis-scoring rule engine.
// Events are points won by side 0 or 1 (in order). The engine reduces a sequence
// of point-winners into a structured tennis state. Append-only — undo is done by
// dropping the last event upstream, never by mutating state.

export type PointWinner = 0 | 1;

export type TennisFormat = {
  setsToWin: number; // best of (2*setsToWin - 1)
  gamesPerSet: number; // standard 6
  tiebreakAt: [number, number]; // standard [6, 6]
  tiebreakPointsToWin: number; // standard 7
};

export const STANDARD_FORMAT: TennisFormat = {
  setsToWin: 2,
  gamesPerSet: 6,
  tiebreakAt: [6, 6],
  tiebreakPointsToWin: 7,
};

export type TennisState = {
  pointDisplay: [string, string]; // "0" | "15" | "30" | "40" | "Ad" | tiebreak number
  gamesInCurrentSet: [number, number];
  setHistory: Array<[number, number]>; // games won per side per completed set
  setsWon: [number, number];
  inTiebreak: boolean;
  matchWinner: PointWinner | null;
};

function emptyState(): TennisState {
  return {
    pointDisplay: ["0", "0"],
    gamesInCurrentSet: [0, 0],
    setHistory: [],
    setsWon: [0, 0],
    inTiebreak: false,
    matchWinner: null,
  };
}

const REGULAR_DISPLAY = ["0", "15", "30", "40"] as const;

/**
 * Reduce a sequence of point winners to a TennisState. Pure function.
 */
export function summarize(
  events: ReadonlyArray<PointWinner>,
  format: TennisFormat = STANDARD_FORMAT,
): TennisState {
  let pointsInGame: [number, number] = [0, 0];
  let gamesInSet: [number, number] = [0, 0];
  const setHistory: Array<[number, number]> = [];
  let setsWon: [number, number] = [0, 0];
  let inTiebreak = false;
  let matchWinner: PointWinner | null = null;
  const setsRequired = format.setsToWin;

  for (const winner of events) {
    if (matchWinner !== null) break;

    pointsInGame[winner]++;

    if (inTiebreak) {
      const need = format.tiebreakPointsToWin;
      const [a, b] = pointsInGame;
      const leader = a >= need || b >= need ? (a > b ? 0 : 1) : null;
      if (leader !== null && Math.abs(a - b) >= 2) {
        // Tiebreak — and set — ends.
        gamesInSet[leader]++;
        setHistory.push([gamesInSet[0], gamesInSet[1]]);
        setsWon[leader]++;
        gamesInSet = [0, 0];
        pointsInGame = [0, 0];
        inTiebreak = false;
        if (setsWon[leader] >= setsRequired) matchWinner = leader as PointWinner;
      }
      continue;
    }

    // Regular game scoring.
    const [a, b] = pointsInGame;
    if (a >= 4 || b >= 4) {
      const leader = a > b ? 0 : 1;
      if (Math.abs(a - b) >= 2) {
        // Game won.
        gamesInSet[leader]++;
        pointsInGame = [0, 0];

        const [ga, gb] = gamesInSet;
        // Tiebreak trigger.
        if (ga === format.tiebreakAt[0] && gb === format.tiebreakAt[1]) {
          inTiebreak = true;
          continue;
        }
        // Set won outright (e.g. 6–4, 7–5).
        if ((ga >= format.gamesPerSet || gb >= format.gamesPerSet) && Math.abs(ga - gb) >= 2) {
          const setLeader = ga > gb ? 0 : 1;
          setHistory.push([ga, gb]);
          setsWon[setLeader]++;
          gamesInSet = [0, 0];
          if (setsWon[setLeader] >= setsRequired) matchWinner = setLeader as PointWinner;
        }
      }
    }
  }

  // Build display.
  let pointDisplay: [string, string];
  if (inTiebreak) {
    pointDisplay = [String(pointsInGame[0]), String(pointsInGame[1])];
  } else {
    const [a, b] = pointsInGame;
    if (a >= 3 && b >= 3) {
      if (a === b) pointDisplay = ["40", "40"];
      else if (a > b) pointDisplay = ["Ad", "40"];
      else pointDisplay = ["40", "Ad"];
    } else {
      pointDisplay = [REGULAR_DISPLAY[Math.min(a, 3)], REGULAR_DISPLAY[Math.min(b, 3)]];
    }
  }

  return {
    pointDisplay,
    gamesInCurrentSet: [...gamesInSet] as [number, number],
    setHistory,
    setsWon,
    inTiebreak,
    matchWinner,
  };
}

export const _emptyTennisStateForTesting = emptyState;
