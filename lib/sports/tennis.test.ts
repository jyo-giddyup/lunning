import { describe, expect, it } from "vitest";
import { summarize, type PointWinner } from "./tennis";

// Helpers to build event sequences. Side notation: A = 0, B = 1.
function events(s: string): PointWinner[] {
  return s
    .replace(/\s+/g, "")
    .split("")
    .map((c) => (c === "A" ? 0 : 1)) as PointWinner[];
}

function repeat(side: "A" | "B", n: number): string {
  return side.repeat(n);
}

describe("tennis.summarize", () => {
  it("empty state", () => {
    const s = summarize([]);
    expect(s.pointDisplay).toEqual(["0", "0"]);
    expect(s.gamesInCurrentSet).toEqual([0, 0]);
    expect(s.setsWon).toEqual([0, 0]);
    expect(s.matchWinner).toBeNull();
  });

  it("15-0, 30-0, 40-0", () => {
    expect(summarize(events("A")).pointDisplay).toEqual(["15", "0"]);
    expect(summarize(events("AA")).pointDisplay).toEqual(["30", "0"]);
    expect(summarize(events("AAA")).pointDisplay).toEqual(["40", "0"]);
  });

  it("deuce and advantage", () => {
    // 3-3 = deuce.
    expect(summarize(events("AAABBB")).pointDisplay).toEqual(["40", "40"]);
    // Ad-A.
    expect(summarize(events("AAABBBA")).pointDisplay).toEqual(["Ad", "40"]);
    // Back to deuce.
    expect(summarize(events("AAABBBAB")).pointDisplay).toEqual(["40", "40"]);
  });

  it("win a love game", () => {
    const s = summarize(events("AAAA"));
    expect(s.pointDisplay).toEqual(["0", "0"]);
    expect(s.gamesInCurrentSet).toEqual([1, 0]);
  });

  it("win a set 6-0", () => {
    // 24 points = 6 love games for A.
    const s = summarize(events(repeat("A", 24)));
    expect(s.setsWon).toEqual([1, 0]);
    expect(s.setHistory).toEqual([[6, 0]]);
    expect(s.gamesInCurrentSet).toEqual([0, 0]);
  });

  it("7-5 set without tiebreak", () => {
    // A wins 5 love games, B wins 5 love games (5-5), A wins 2 more (7-5).
    const seq = repeat("A", 20) + repeat("B", 20) + repeat("A", 8);
    const s = summarize(events(seq));
    expect(s.setHistory).toEqual([[7, 5]]);
    expect(s.setsWon).toEqual([1, 0]);
  });

  it("triggers tiebreak at 6-6", () => {
    // 6 love games for A, 6 love games for B = 6-6 → tiebreak.
    const seq = repeat("A", 24) + repeat("B", 24);
    const s = summarize(events(seq));
    expect(s.inTiebreak).toBe(true);
    expect(s.gamesInCurrentSet).toEqual([6, 6]);
    expect(s.setHistory).toEqual([]);
  });

  it("wins tiebreak 7-5", () => {
    const toTiebreak = repeat("A", 24) + repeat("B", 24);
    // A 7, B 5 in tiebreak. Build A wins 7-5 by alternation that ends with A leading by 2.
    // Simpler: A 5, B 5, then A A.
    const tb = repeat("A", 5) + repeat("B", 5) + "AA";
    const s = summarize(events(toTiebreak + tb));
    expect(s.inTiebreak).toBe(false);
    expect(s.setHistory).toEqual([[7, 6]]);
    expect(s.setsWon).toEqual([1, 0]);
  });

  it("declares match winner in best-of-3", () => {
    // Two 6-0 sets for A.
    const s = summarize(events(repeat("A", 48)));
    expect(s.setsWon).toEqual([2, 0]);
    expect(s.matchWinner).toBe(0);
  });

  it("ignores events after match is decided", () => {
    const s = summarize(events(repeat("A", 48) + repeat("B", 100)));
    expect(s.matchWinner).toBe(0);
    expect(s.setsWon).toEqual([2, 0]);
  });
});
