#!/usr/bin/env python3
"""Coverage checker for the ability registry: every C/U ability must be registered. Reports coverage %
and the unimplemented work queue. Invariant: 0 uncovered. Run: python3 coverage_abilities.py."""
import sys
from collections import Counter
from cards import load_cards
import ability_effects as AB
try:
    import abilities_gen
    abilities_gen.load_all()
except Exception:
    pass

BK, BN = load_cards()


def scan():
    total = covered = 0
    uncovered = Counter()
    for c in BK.values():
        if c.cat != 'cat-green':
            continue
        for ab in c.abilities:
            total += 1
            key = AB.normalize(ab['text'])
            if key in AB.ABILITY_EFFECTS:
                covered += 1
            else:
                uncovered[key] += 1
    return total, covered, uncovered


if __name__ == '__main__':
    total, covered, unc = scan()
    n_unc = sum(unc.values())
    print(f"pool abilities: {total} | covered: {covered} | UNCOVERED: {n_unc} ({len(unc)} distinct)")
    print(f"COVERAGE: {100*covered/max(1,total):.1f}%  |  {len(AB.ABILITY_EFFECTS)} distinct abilities registered")
    n = int(sys.argv[sys.argv.index('--list') + 1]) if '--list' in sys.argv else 20
    print(f"\ntop {n} unimplemented (count x text):")
    for t, v in unc.most_common(n):
        print(f"   [{v:2}x] {t[:100]}")
    raise SystemExit(1 if n_unc else 0)
