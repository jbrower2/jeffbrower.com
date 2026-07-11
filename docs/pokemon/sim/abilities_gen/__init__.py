# package marker for generated ability batches (batch_*.py). Loaded via load_all() after all exist.
import os
import glob
import importlib


def load_all():
    here = os.path.dirname(__file__)
    loaded = 0
    for f in sorted(glob.glob(os.path.join(here, 'batch_*.py'))):
        importlib.import_module(f"abilities_gen.{os.path.basename(f)[:-3]}")
        loaded += 1
    return loaded
