import csv
import io
import json
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from coordinator import Coordinator, Unavailable
from shared.model import ACTIVE, TERMINAL, FIELDS
from shared.worker import Conflict
from shared.metrics import install_http
from shared import tracing

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
runtime = Coordinator()
install_http(app, runtime.metrics)
tracing.instrument_app(app)


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'controller', 'stage': 4}


@app.get('/api/deployment')
def deployment():
    return runtime.deployment_status()


@app.post('/api/deployment/prepare')
def prepare_deployment():
    return runtime.prepare_deployment()


@app.get('/api/workloads')
def catalog():
    return {**runtime.catalog(), 'observability': {'tracing_enabled': tracing.enabled()}}


@app.post('/api/runs')
def start():
    return runtime.submit(request.get_json()), 202


@app.get('/api/runs/active')
def active():
    return {'run': runtime.active()}


@app.get('/api/runs/<run_id>')
def detail(run_id):
    return runtime.get(run_id)


@app.post('/api/runs/<run_id>/stop')
def stop(run_id):
    return runtime.stop(run_id), 202


def filters():
    result = {name: request.args.get(name, '') for name in ('workload', 'state', 'q')}
    if result['workload'] and result['workload'] not in FIELDS:
        raise ValueError('Invalid workload filter.')
    if result['state'] and result['state'] not in ACTIVE | TERMINAL:
        raise ValueError('Invalid state filter.')
    if len(result['q']) > 100:
        raise ValueError('Search must be at most 100 characters.')
    return result


def positive_parameter(name, default, cap):
    value = request.args.get(name, str(default))
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= cap:
        raise ValueError(f'{name} must be from 1 to {cap}.')
    return int(value)


@app.get('/api/runs')
def history():
    return runtime.history(filters(), positive_parameter('page', 1, 1000), positive_parameter('page_size', 20, 100))


CSV_FIELDS = ['id', 'name', 'notes', 'workload', 'profile', 'target_service', 'state', 'created_at', 'started_at',
              'finished_at', 'elapsed_seconds', 'settings', 'counters', 'rates', 'error', 'persistence', 'trace_id',
              'deployment', 'target_services', 'algorithm_version', 'assignment', 'batch_results', 'instance_results']


def csv_cell(value):
    if isinstance(value, (dict,list)):
        return json.dumps(value, sort_keys=True)
    text = '' if value is None else str(value)
    # Keep names/notes literal when opened in spreadsheet applications.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


@app.get('/api/runs/export.csv')
def export():
    selected = filters()
    def rows():
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction='ignore')
        writer.writeheader()
        yield output.getvalue()
        page = 1
        while True:
            result = runtime.history(selected, page, 100)
            for run in result['items']:
                output.seek(0)
                output.truncate()
                writer.writerow({key: csv_cell(run.get(key)) for key in CSV_FIELDS})
                yield output.getvalue()
            if page * 100 >= result['total']:
                break
            page += 1
    return Response(rows(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename="experiment-history.csv"'})


@app.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 400


@app.errorhandler(KeyError)
def missing(error):
    return jsonify(error='Run not found.'), 404


@app.errorhandler(Conflict)
def conflict(error):
    return jsonify(error=str(error)), 409


@app.errorhandler(Unavailable)
def unavailable(error):
    return jsonify(error=str(error)), 503


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code
