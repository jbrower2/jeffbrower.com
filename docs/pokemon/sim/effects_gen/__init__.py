# package marker for generated attack-effect batches (batch_*.py).
# Do NOT auto-import batches here — agents import their own batch while others are still being
# written concurrently. The full registry is loaded via load_all() below, called after all batches exist.
import os
import glob
import importlib


def load_all():
    """Import every batch_*.py so its @effect registrations populate attack_effects.ATTACK_EFFECTS."""
    here = os.path.dirname(__file__)
    loaded = 0
    for f in sorted(glob.glob(os.path.join(here, 'batch_*.py'))):
        importlib.import_module(f"effects_gen.{os.path.basename(f)[:-3]}")
        loaded += 1
    return loaded
