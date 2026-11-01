"""Allow old script entry points to call the current acceptance script."""
from pathlib import Path
import runpy


def run():
    print('The workload API changed in Stage 2. Running its full acceptance workflow, including restarts.', flush=True)
    runpy.run_path(str(Path(__file__).with_name('verify-stage2.py')), run_name='__main__')
