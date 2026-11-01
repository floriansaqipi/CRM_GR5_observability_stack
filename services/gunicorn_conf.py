"""Each service has one owner for background threads and workload locks."""
from gunicorn.workers.gthread import ThreadWorker
import os

bind = '0.0.0.0:5000'
workers = 1
threads = 8
timeout = 30
graceful_timeout = 6
worker_class = 'gunicorn_conf.ManagedWorker'
accesslog = '-'
errorlog = '-'


class ManagedWorker(ThreadWorker):
    def handle_exit(self, sig, frame):
        from app import runtime
        runtime.shutdown()
        super().handle_exit(sig, frame)

    def handle_quit(self, sig, frame):
        from app import runtime
        runtime.shutdown()
        super().handle_quit(sig, frame)


def post_worker_init(worker):
    from app import runtime
    runtime.start()


def post_fork(server, worker):
    # The exporter owns a thread: create it in the application worker, never the master.
    from shared.tracing import configure
    configure(os.environ['LAB_SERVICE'])


def worker_exit(server, worker):
    from app import runtime
    runtime.shutdown()
    from shared.tracing import shutdown
    shutdown()
