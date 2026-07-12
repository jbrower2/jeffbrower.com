#!/usr/bin/env python3
"""Run the full attack-effect test suite: the proof-batch tests plus every generated batch's tests.
Each file runs as a module in its own process (isolated import state). Exits non-zero on any failure."""
import sys
import os
import glob
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def module_name(path):
    rel = os.path.relpath(path, HERE)
    return rel[:-3].replace(os.sep, '.')


mods = (['test_effects', 'test_abilities', 'test_trainers', 'test_ramp_expiry']
        + [module_name(f) for f in sorted(glob.glob(os.path.join(HERE, 'effects_gen', 'test_batch_*.py')))]
        + [module_name(f) for f in sorted(glob.glob(os.path.join(HERE, 'abilities_gen', 'test_batch_*.py')))]
        + [module_name(f) for f in sorted(glob.glob(os.path.join(HERE, 'trainers_gen', 'test_batch_*.py')))])
fails, total_pass = [], 0
for m in mods:
    r = subprocess.run([sys.executable, '-m', m], cwd=HERE, capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or ['(no output)'])[-1]
    print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {m:38} {tail}")
    if r.returncode:
        fails.append(m)
        err = (r.stderr.strip().splitlines() or [''])[-1]
        if err:
            print('       ' + err)
print(f"\n=== {len(mods)} test files | {len(mods)-len(fails)} passed | {len(fails)} failed ===")
if fails:
    print('failing:', fails)
raise SystemExit(1 if fails else 0)
