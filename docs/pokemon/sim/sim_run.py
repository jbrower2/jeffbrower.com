#!/usr/bin/env python3
"""Round-robin runner: play decks head-to-head and rank by win rate.

Usage:
  python3 sim_run.py                 # flagship of each section (fast demo)
  python3 sim_run.py --all --games 8 # all 165 decks (slow)
  python3 sim_run.py --section G --games 60
"""
import sys, time
from collections import defaultdict
from decks_build import parse_decks, build_spec
from engine import run_match

def pick(argv):
    decks = parse_decks()
    games = 40
    if '--games' in argv:
        games = int(argv[argv.index('--games') + 1])
    if '--all' in argv:
        chosen = decks
    elif '--section' in argv:
        sec = argv[argv.index('--section') + 1]
        chosen = [d for d in decks if d['section'] == sec]
    else:
        # flagship = first (strongest) deck of each section, in section order
        seen, chosen = set(), []
        for d in decks:
            if d['section'] not in seen:
                seen.add(d['section']); chosen.append(d)
    return chosen, games

def main():
    chosen, games = pick(sys.argv)
    specs = []
    for d in chosen:
        s = build_spec(d)
        if s:
            specs.append((d['name'], d['section'], s))
    print(f"{len(specs)} decks, {games} games/pairing, {len(specs)*(len(specs)-1)//2} pairings")
    W = defaultdict(int); G = defaultdict(int)
    t0 = time.time()
    for i in range(len(specs)):
        for j in range(i + 1, len(specs)):
            na, _, sa = specs[i]; nb, _, sb = specs[j]
            wa, wb, dr = run_match(sa, sb, games=games)
            W[na] += wa; G[na] += wa + wb + dr
            W[nb] += wb; G[nb] += wa + wb + dr
    dt = time.time() - t0
    print(f"ran in {dt:.1f}s\n")
    rank = sorted(specs, key=lambda x: -(W[x[0]] / max(1, G[x[0]])))
    print(f"{'WIN%':>6}  {'SECTION':<8} DECK")
    for name, sec, _ in rank:
        wr = 100 * W[name] / max(1, G[name])
        print(f"{wr:6.1f}  {sec:<8} {name}")

if __name__ == '__main__':
    main()
