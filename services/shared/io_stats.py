"""Fixed-size latency summaries passed from a child to its owning service."""
import time
from contextlib import contextmanager

IO_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, float('inf'))


class IOStats:
    def __init__(self):
        self.values = {}

    @contextmanager
    def measure(self, operation):
        started, outcome = time.monotonic(), 'success'
        try:
            yield
        except Exception:
            outcome = 'error'
            raise
        finally:
            elapsed = time.monotonic() - started
            entry = self.values.setdefault(operation + ':' + outcome,
                                           {'buckets': [0] * len(IO_BUCKETS), 'count': 0, 'sum': 0})
            entry['count'] += 1
            entry['sum'] += elapsed
            for index, bound in enumerate(IO_BUCKETS):
                if elapsed <= bound:
                    entry['buckets'][index] += 1
