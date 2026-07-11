#!/usr/bin/env python3
"""Coverage checker for the trainer registry: every C/U trainer's effect text must be registered.
Also bridges Tool card-name -> effect text (mon.tools stores names). Invariant: 0 uncovered."""
import os
import sys
import json
from collections import Counter
import trainer_effects as TE
try:
    import trainers_gen
    trainers_gen.load_all()
except Exception:
    pass

TRAINERS = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deckgen', 'trainers.json')))
# Tools store their NAME on a Mon; register name -> effect text so the engine can resolve their lambdas.
TE.register_tool_texts({nm: v.get('effect', '') for nm, v in TRAINERS.items() if v.get('trainerType') == 'Tool'})


def scan():
    total = covered = 0
    uncovered = Counter()
    per_type = Counter()
    for nm, v in TRAINERS.items():
        total += 1
        key = TE.normalize(v.get('effect', ''))
        if key in TE.TRAINER_EFFECTS:
            covered += 1
        else:
            uncovered[key] += 1
            per_type[v.get('trainerType', '?')] += 1
    return total, covered, uncovered, per_type


if __name__ == '__main__':
    total, covered, unc, per_type = scan()
    n = sum(unc.values())
    print(f"pool trainers: {total} | covered: {covered} | UNCOVERED: {n} ({len(unc)} distinct)")
    print(f"COVERAGE: {100*covered/max(1,total):.1f}%  |  {len(TE.TRAINER_EFFECTS)} distinct trainer effects registered")
    print(f"uncovered by type: {dict(per_type)}")
    k = int(sys.argv[sys.argv.index('--list') + 1]) if '--list' in sys.argv else 15
    for t, v in unc.most_common(k):
        print(f"   [{v}x] {t[:100]}")
    raise SystemExit(1 if n else 0)
