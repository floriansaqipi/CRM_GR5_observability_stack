from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException
from shared.worker import Conflict, Worker
from shared.metrics import install_http
from shared import tracing
import os
from shared.deployment import read_limits


def create_worker(service):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
    instance = os.environ.get('LAB_SERVICE', service)
    worker = Worker(service, instance)
    install_http(app, worker.metrics)
    tracing.instrument_app(app)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': instance, 'stage': 4}

    @app.get('/internal/state')
    def state():
        return {**worker.snapshot(), 'configuration': {'instance': instance, 'role': service,
                'limits': read_limits(), 'tracing_enabled': tracing.enabled(), 'boot_id': worker.boot_id}}

    @app.post('/internal/runs')
    def start():
        run = request.get_json()
        if not isinstance(run, dict):
            raise ValueError('Provide a JSON run object.')
        if service == 'data' and run.get('workload') in ('memory','combined'):
            cap = 64 if (read_limits()['memory_bytes'] or 0) <= 256*1024**2 else 128
            if run.get('settings', {}).get('memory_mib',0) > cap:
                raise ValueError(f'This Data container permits at most {cap} MiB of workload memory.')
        # Capture before leaving the short HTTP request and entering a new thread.
        run['_trace_context'] = tracing.carrier()
        return worker.submit(run), 202

    @app.post('/internal/runs/<run_id>/stop')
    def stop(run_id):
        try:
            body = request.get_json(silent=True) or {}
            return worker.stop(run_id, str(body.get('reason', ''))[:200] or None), 202
        except KeyError:
            return {'error': 'Run not found.'}, 404

    if service == 'compute':
        @app.get('/workloads/network')
        def payload():
            value = request.args.get('size_kib', '256')
            if set(request.args) - {'size_kib'} or len(request.args.getlist('size_kib')) > 1 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 1024:
                raise ValueError('size_kib must be an integer from 1 to 1024.')
            return Response(b'x' * int(value) * 1024, mimetype='application/octet-stream', headers={'Cache-Control': 'no-store'})

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(Conflict)
    def busy(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    return app, worker
