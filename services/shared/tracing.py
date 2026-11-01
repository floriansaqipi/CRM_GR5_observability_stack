"""Explicit trace ownership and propagation, independent of experiment success."""
from contextlib import contextmanager
import os
from uuid import uuid4
from opentelemetry import context, propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, ALWAYS_ON
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, Status, StatusCode

provider = None
EXCLUDED = r'/health(?:\?|$),/metrics(?:\?|$),/static/,/internal/state(?:\?|$),/api/workloads(?:\?|$),/api/runs/active(?:\?|$),/api/runs/[0-9a-f-]+(?:\?|$)'


def enabled():
    return os.environ.get('LAB_TRACING_ENABLED', 'false').lower() == 'true'


def configure(service):
    global provider
    if provider is not None or not enabled():
        return
    provider = TracerProvider(resource=Resource.create({'service.name': service, 'service.namespace': 'cloud-lab1',
                              'service.instance.id': str(uuid4()), 'deployment.environment.name': 'local'}),
                              sampler=ParentBased(ALWAYS_ON), shutdown_on_exit=False)
    exporter = OTLPSpanExporter(endpoint=os.environ.get('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT',
                                'http://otel-collector:4318/v1/traces'), timeout=0.5)
    provider.add_span_processor(BatchSpanProcessor(exporter, max_queue_size=512, max_export_batch_size=128,
                                                   schedule_delay_millis=1000, export_timeout_millis=500))
    trace.set_tracer_provider(provider)
    RequestsInstrumentor().instrument(excluded_urls=EXCLUDED)
    PymongoInstrumentor().instrument(capture_statement=False)


def instrument_app(app):
    if enabled():
        FlaskInstrumentor().instrument_app(app, excluded_urls=EXCLUDED)


def shutdown():
    if provider:
        # Never wait for a missing backend during Stop or application shutdown.
        provider.force_flush(timeout_millis=500)
        provider.shutdown()


def carrier(span=None):
    result = {}
    propagate.inject(result, context=trace.set_span_in_context(span) if span else None)
    return result


@contextmanager
def attached(headers):
    token = context.attach(propagate.extract(headers or {}))
    try:
        yield
    finally:
        context.detach(token)


def begin_run(run):
    span = trace.get_tracer('cloud-lab1').start_span('experiment.run', attributes=attributes(run))
    ctx = span.get_span_context()
    run['trace_id'] = format(ctx.trace_id, '032x') if ctx.is_valid else None
    run['_trace_context'] = carrier(span)
    return span


def attributes(run):
    values = {'lab.run.id': run['id'], 'lab.workload': run['workload'],
              **{'lab.setting.' + key: value for key, value in run['settings'].items()}}
    if run.get('algorithm_version'):
        values['lab.algorithm.version'] = run['algorithm_version']
    if run.get('deployment'):
        values['lab.deployment.preset'] = run['deployment']['preset']
    if run.get('instance'):
        values['lab.instance'] = run['instance']
    return values


def finish_span(span, run):
    span.set_attribute('lab.outcome', run['state'])
    if run['state'] in ('failed', 'interrupted'):
        span.set_status(Status(StatusCode.ERROR, run.get('error') or run['state']))
    elif run['state'] == 'cancelled':
        span.add_event('experiment.cancelled')
    span.end()


@contextmanager
def operation_cycle(detail, parent_context):
    """Unselected calls propagate an unsampled parent, including to Compute."""
    if detail:
        with trace.get_tracer('cloud-lab1').start_as_current_span('workload.io_cycle'):
            yield
    else:
        parent = trace.get_current_span().get_span_context()
        muted = NonRecordingSpan(SpanContext(parent.trace_id, parent.span_id, parent.is_remote,
                                            TraceFlags(0), parent.trace_state))
        token = context.attach(trace.set_span_in_context(muted))
        try:
            yield
        except Exception as exc:
            with trace.get_tracer('cloud-lab1').start_as_current_span('workload.failed_cycle', context=parent_context) as span:
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                span.record_exception(exc)
            raise
        finally:
            context.detach(token)
