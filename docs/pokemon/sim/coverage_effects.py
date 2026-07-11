#!/usr/bin/env python3
"""Coverage checker: every attack in the C/U pool must resolve through the registry (or be vanilla).
Reports coverage % and the most-common UNIMPLEMENTED effects (the work queue). The invariant we drive
to: 0 uncovered. Run: python3 coverage_effects.py [--list N]."""
import sys
from collections import Counter
from cards import load_cards
import attack_effects as AE
try:
    import effects_gen
    effects_gen.load_all()   # register every generated batch's effects
except Exception:
    pass

BK, BN = load_cards()


def scan():
    total = vanilla = covered = 0
    uncovered = Counter()
    for c in BK.values():
        if c.cat != 'cat-green':
            continue
        for a in c.attacks:
            total += 1
            key = AE.normalize(a.get('text'))
            if not key:
                vanilla += 1
            elif key in AE.ATTACK_EFFECTS:
                covered += 1
            else:
                uncovered[key] += 1
    return total, vanilla, covered, uncovered


if __name__ == '__main__':
    total, vanilla, covered, uncovered = scan()
    impl = vanilla + covered
    n_unc = sum(uncovered.values())
    print(f"pool attacks: {total}")
    print(f"  vanilla (damage only, default handler): {vanilla}")
    print(f"  covered by a registered effect:         {covered}")
    print(f"  UNCOVERED:                              {n_unc}  ({len(uncovered)} distinct)")
    print(f"COVERAGE: {100*impl/total:.1f}%  of attack instances  |  "
          f"{len(AE.ATTACK_EFFECTS)} distinct effects implemented, {len(uncovered)} distinct remaining")
    n = 25
    if '--list' in sys.argv:
        n = int(sys.argv[sys.argv.index('--list') + 1])
    print(f"\ntop {n} unimplemented effects (count x text) — the work queue:")
    for t, v in uncovered.most_common(n):
        print(f"   [{v:3}x] {t[:96]}")
    raise SystemExit(1 if n_unc else 0)
