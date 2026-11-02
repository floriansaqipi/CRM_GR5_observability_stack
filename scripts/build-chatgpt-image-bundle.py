"""Build/verify a portable ChatGPT figure-context package; no application operations.

Python 3.10+ and Git are sufficient. Inputs are copied byte for byte. Generated
archives/build folders stay below .runtime by default; existing builds survive.
"""
import argparse
import ast
import base64
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tempfile
from uuid import uuid4
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
AUTHORING = Path('docs/chatgpt-image-bundle')
REPORT = Path('docs/Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx')
PACKAGE = 'cloud-lab1-chatgpt-image-context'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
KINDS = ('cpu', 'memory', 'network', 'combined')
CAPTURE_IDS = [3, 4, 10]
TEXT_SUFFIXES = {'.py', '.ps1', '.json', '.yaml', '.yml', '.txt', '.md', '.css', '.js', '.html', '.mmd'}
SOURCE_ROOTS = {'services', 'scripts', 'monitoring', 'deployment'}
SECRET_PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    re.compile(rb'\bsk-(?:proj-|svcacct-)[A-Za-z0-9_-]{40,}\b'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def plain(element):
    return ''.join(node.text or '' for node in element.iter(W + 't'))


def cell(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]])


def fenced(text, language=''):
    runs = [len(m.group()) for m in re.finditer(r'`+', text)]
    fence = '`' * max(3, max(runs, default=0) + 1)
    return f'{fence}{language}\n{text.rstrip()}\n{fence}'


def ast_values(path, names):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    return {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name) and target.id in names}


def routes(path):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    result = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in ('get', 'post') and dec.args and isinstance(dec.args[0], ast.Constant)):
                    result.append({'method': dec.func.attr.upper(), 'path': dec.args[0].value, 'handler': node.name})
    return result


def compose_facts():
    text = (ROOT / 'compose.yaml').read_text(encoding='utf-8-sig')
    service_text = text.split('services:\n', 1)[1].split('\nnetworks:\n', 1)[0]
    matches = list(re.finditer(r'^  ([\w-]+):\s*$', service_text, re.M))
    services = {}
    for index, match in enumerate(matches):
        block = service_text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(service_text)]
        cpu = re.search(r'^    cpus:\s*([\d.]+)', block, re.M)
        memory = re.search(r'^    mem_limit:\s*(\d+)([mg])', block, re.M)
        image = re.search(r'^    image:\s*(.+)', block, re.M)
        profiles = re.search(r'^    profiles:\s*\[([^]]*)\]', block, re.M)
        services[match.group(1)] = {
            'cpus': float(cpu.group(1)) if cpu else None,
            'memory_mib': int(memory.group(1)) * (1024 if memory.group(2) == 'g' else 1) if memory else None,
            'image': image.group(1).strip() if image else None,
            'profiles': [s.strip() for s in profiles.group(1).split(',')] if profiles else [],
            'published_loopback_ports': re.findall(r'127\.0\.0\.1:(\d+:\d+)', block),
        }
    volume_text = text.rsplit('\nvolumes:\n', 1)[1]
    return services, re.findall(r'^  ([\w-]+):', volume_text, re.M)


def report_inventory(data):
    """Read OOXML only. Never save/round-trip the user's Word report."""
    with ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip():
            raise ValueError('The Word report archive is damaged.')
        if any(name.startswith('word/media/') for name in archive.namelist()):
            raise ValueError('The report now embeds images; reconcile the figure catalog before packaging.')
        body = ET.fromstring(archive.read('word/document.xml')).find(W + 'body')
    figures, sections, document_text = {}, [], []
    last_table = None
    for element in body:
        if element.tag == W + 'tbl':
            last_table = element
            rows = [[plain(c).strip() for c in r.findall(W + 'tc')] for r in element.findall(W + 'tr')]
            if rows and any(any(v for v in row) for row in rows):
                columns = max(map(len, rows))
                padded = [row + [''] * (columns - len(row)) for row in rows]
                document_text.append(table(padded[0], padded[1:]))
        elif element.tag == W + 'p':
            text = plain(element)
            props = element.find(W + 'pPr')
            style = props.find(W + 'pStyle') if props is not None else None
            style_name = style.get(W + 'val') if style is not None else ''
            if text:
                document_text.append(('## ' if style_name == 'Heading1' else '### ' if style_name == 'Heading2' else '') + text)
            if style_name == 'Heading1':
                sections.append(text.replace('\t', ' '))
            match = re.match(r'^Figura (\d+): (.+)$', text)
            if match:
                if last_table is None:
                    raise ValueError('A figure caption has no preceding placeholder table.')
                height = last_table.find('./' + W + 'tr/' + W + 'trPr/' + W + 'trHeight')
                grid = last_table.find(W + 'tblGrid')
                width_twips = sum(int(c.get(W + 'w')) for c in grid) if grid is not None else 9360
                source_line = next((plain(p) for p in last_table.iter(W + 'p') if plain(p).startswith('Burimi: ')), '')
                number = int(match.group(1))
                if number in figures:
                    raise ValueError(f'Duplicate figure {number}.')
                figures[number] = {'caption': match.group(2), 'placeholder_source': source_line.removeprefix('Burimi: '),
                                   'frame_width_cm': round(width_twips / 1440 * 2.54, 2),
                                   'frame_height_cm': round(int(height.get(W + 'val')) / 1440 * 2.54, 1) if height is not None else None}
    return figures, sections, '\n\n'.join(document_text)


def image_size(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return list(struct.unpack('>II', data[16:24]))
    if data.startswith(b'\xff\xd8'):
        pos = 2
        while pos + 4 < len(data):
            if data[pos] != 255:
                pos += 1
                continue
            marker = data[pos + 1]
            pos += 2
            if marker in (0xD8, 0xD9) or marker == 0:
                continue
            size = struct.unpack('>H', data[pos:pos + 2])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack('>HH', data[pos + 3:pos + 7])
                return [width, height]
            pos += size
    return None


def project_files():
    listed = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    result = []
    for name in sorted(set(listed.decode('utf-8').split('\0')) - {''}):
        path = PurePosixPath(name)
        if blocked(path):
            continue
        # Include only this project's known source/docs/configuration areas.
        if path.parts[0] not in SOURCE_ROOTS | {'docs'} and path.suffix != '.md' and path.name not in {'.gitignore', '.env.example', 'compose.yaml'}:
            continue
        if path.suffix == '.docx' and name != REPORT.as_posix():
            continue  # Earlier drafts are intentionally not competing report authorities.
        absolute = ROOT / name
        if absolute.is_symlink() or not absolute.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f'Input escapes the repository or is a symlink: {name}')
        if not absolute.is_file():
            raise ValueError(f'A listed input file is missing: {name}')
        result.append(name)
    return result


def blocked(path):
    return (any(p in {'.git', '.runtime', '.idea', '.venv', '__pycache__', '.pytest_cache'} for p in path.parts)
            or path.name.startswith('~$') or (path.name.startswith('.env') and path.name != '.env.example')
            or path.suffix.lower() in {'.pyc', '.pyo', '.tmp', '.pem', '.key', '.pfx', '.p12'}
            or path.name in {'Thumbs.db', '.DS_Store'})


def scan_secrets(name, data):
    chunks = [data]
    if name.endswith('.docx'):
        with ZipFile(io.BytesIO(data)) as archive:
            chunks = [archive.read(n) for n in archive.namelist() if n.endswith('.xml')]
    if any(pattern.search(chunk) for pattern in SECRET_PATTERNS for chunk in chunks):
        raise ValueError(f'Potential credential material in {name}; inspect locally before exporting.')


def dashboard_panels():
    result = []
    def walk(panels, dashboard):
        for panel in panels:
            if panel.get('type') != 'row':
                result.append({'dashboard': dashboard['title'], 'uid': dashboard['uid'], 'id': panel['id'],
                               'title': panel.get('title', ''), 'description': panel.get('description', ''),
                               'unit': panel.get('fieldConfig', {}).get('defaults', {}).get('unit'),
                               'queries': [{'expression': q['expr'], 'legend': q.get('legendFormat', '')}
                                           for q in panel.get('targets', []) if q.get('expr')]})
            walk(panel.get('panels', []), dashboard)
    for filename in sorted((ROOT / 'monitoring/grafana/dashboards').glob('*.json')):
        dashboard = read_json(filename)
        walk(dashboard['panels'], dashboard)
    return result


def derive_facts(check):
    services, volumes = compose_facts()
    expected = {'compute': (1, 512), 'data': (1, 512), 'controller': (.5, 256), 'mongodb': (1, 768),
                'cadvisor': (.5, 256), 'prometheus': (1, 768), 'grafana': (.5, 512),
                'otel-collector': (.5, 256), 'tempo': (1, 768), 'compute-2': (1, 512)}
    check('service_limits_match_context', set(services) == set(expected) and all((services[k]['cpus'], services[k]['memory_mib']) == v for k, v in expected.items()))
    check('optional_profiles_match_context', services['compute-2']['profiles'] == ['replica'] and all(services[n]['profiles'] == ['tracing'] for n in ['otel-collector', 'tempo']))
    baseline = [s for s in services.values() if not s['profiles']]
    check('seven_nine_eight_ten_service_modes', len(baseline) == 7 and len(services) == 10)
    check('memory_ceiling_totals_match', sum(s['memory_mib'] for s in baseline) == 3584 and sum(s['memory_mib'] for n, s in services.items() if n != 'compute-2') == 4608)
    check('published_ports_are_loopback_and_correct', {n: s['published_loopback_ports'] for n, s in services.items() if s['published_loopback_ports']} == {'controller': ['5000:5000'], 'mongodb': ['27017:27017'], 'prometheus': ['9090:9090'], 'grafana': ['3000:3000']})
    model = ast_values('services/shared/model.py', {'ACTIVE', 'TERMINAL', 'FIELDS', 'LIMITS', 'PRESETS'})
    check('six_final_workloads', set(model['FIELDS']) == {'cpu', 'cpu_fixed', 'memory', 'network', 'database', 'combined'})
    check('workload_limits_match_context', model['LIMITS'] == {'duration_seconds':[15,180], 'cpu_percent':[10,95], 'memory_mib':[1,128], 'payload_kib':[1,1024], 'rate_per_second':[1,20], 'document_kib':[1,64], 'batch_count':[4,64]})
    check('workload_presets_match_context', model['PRESETS'] == {p:dict(zip(['cpu_percent','memory_mib','payload_kib','rate_per_second','document_kib'], values)) for p,values in [('low',[25,32,64,2,4]),('medium',[50,64,256,5,16]),('high',[90,128,1024,10,64])]})
    algorithm = ast_values('services/shared/fixed_work.py', {'ALGORITHM', 'UNITS_PER_BATCH', 'UNIT_CHECKSUM'})
    tree = ast.parse((ROOT / 'services/shared/fixed_work.py').read_text(encoding='utf-8-sig'))
    calculation = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'calculate_unit').body[0].value
    check('fixed_algorithm_matches_context', ast.dump(calculation) == ast.dump(ast.parse('sum(n*n % 104729 for n in range(3000))', mode='eval').body) and algorithm == {'ALGORITHM':'sum-squares-v1','UNITS_PER_BATCH':2500,'UNIT_CHECKSUM':150089160})
    experiments = read_json('docs/evidence/stage5/experiments.json')
    check('all_36_archived_collection_checks_passed', len(experiments['checks']) == 36 and all(experiments['checks'].values()))
    examples = {}
    for kind in KINDS:
        entry = read_json(f'docs/evidence/stage5/{kind}/run.json')
        run = entry['run']
        check(f'{kind}_archived_records_agree', run == experiments['runs'][kind]['run'])
        check(f'{kind}_archived_cleanup_checks_passed', all(entry['checks'].values()))
        check(f'{kind}_completed_saved_zero_errors', run['state'] == 'completed' and run['persistence'] == 'saved' and run['counters']['errors'] == 0)
        expected_settings = {key:model['PRESETS']['medium'][key] for key in model['FIELDS'][kind]}
        expected_settings['duration_seconds'] = 30
        check(f'{kind}_settings_and_duration_match_figure_brief', run['settings'] == expected_settings and f"{run['elapsed_seconds']:.3f}" == {'cpu':'30.000','memory':'30.003','network':'30.000','combined':'30.005'}[kind])
        check(f'{kind}_verified_baseline_tracing', run['deployment']['preset'] == 'baseline' and run['deployment']['tracing'] and run['deployment']['verified'])
        with (ROOT / f'docs/evidence/stage5/{kind}/export.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        check(f'{kind}_csv_agrees_with_run', len(rows) == 1 and rows[0]['id'] == run['id'] and json.loads(rows[0]['counters']) == run['counters'] and json.loads(rows[0]['settings']) == run['settings'])
        matrix = read_json(f'docs/evidence/stage5/{kind}/measurements.json')
        check(f'{kind}_real_resource_matrices_present', all(matrix[k]['result'] for k in ['cpu_30s','memory_mib','receive_30s','transmit_30s']))
        examples[kind] = entry
    check('same_images_across_examples', all(examples[k]['run']['deployment']['images'] == examples['cpu']['run']['deployment']['images'] for k in KINDS))
    check('documented_example_counts_match', examples['cpu']['run']['counters']['cpu_batches'] == 44953 and all(examples[k]['run']['counters']['network_requests'] == 150 and examples[k]['run']['counters']['network_bytes'] == 39321600 for k in ['network','combined']) and all(examples['combined']['run']['counters'][n] == 150 for n in ['database_reads','database_writes','database_cycles']))
    trace = read_json('docs/evidence/stage5/combined/trace.json')
    spans = [span for batch in trace['batches'] for scope in batch['scopeSpans'] for span in scope['spans']]
    span_ids = {s['spanId'] for s in spans}
    check('combined_trace_142_connected_spans', len(spans) == 142 and len(span_ids) == 142 and {base64.b64decode(s['traceId']).hex() for s in spans} == {examples['combined']['run']['trace_id']} and all(not s.get('parentSpanId') or s['parentSpanId'] in span_ids for s in spans))
    stage4 = read_json('docs/evidence/stage4/acceptance.json')
    comparisons = ['cpu-05','cpu-1','cpu-2','replica-1','replica-2']
    check('fixed_comparisons_identical_work_checksum_concurrency', all(stage4['runs'][p]['state'] == 'completed' and len(stage4['runs'][p]['batch_results']) == 32 and sum(b['checksum'] for b in stage4['runs'][p]['batch_results']) == 12007132800000 and stage4['measurements'][p]['peak_calculation_processes'] == 2 for p in comparisons))
    check('memory_comparisons_same_buffer', all(stage4['runs'][p]['state'] == 'completed' and stage4['runs'][p]['settings']['memory_mib'] == 64 for p in ['memory-256','memory-512','memory-1024']))
    verification = read_json('docs/evidence/stage5/verification.json')
    check('automated_tests_distinct_from_stage5_checks', 'Ran 31 tests' in (ROOT / 'docs/evidence/stage5/unit-tests.txt').read_text(encoding='utf-8-sig') and len(verification) == 127 and all(verification.values()))
    check('stage4_acceptance_checks_passed', len(stage4['checks']) == 140 and all(stage4['checks'].values()))
    gunicorn = ast_values('services/gunicorn_conf.py', {'workers','threads'})
    check('one_gunicorn_worker_eight_threads', gunicorn == {'workers':1,'threads':8})
    # Convert literal sets into stable JSON arrays, retaining the real names.
    for key in ['ACTIVE','TERMINAL']:
        model[key] = sorted(model[key])
    return {'services': services, 'volumes': volumes, 'model': model, 'deployment_presets': read_json('services/shared/presets.json'),
            'algorithm': algorithm, 'controller_routes': routes('services/controller/app.py'), 'worker_routes': routes('services/shared/worker_app.py'),
            'csv_fields': ast_values('services/controller/app.py', {'CSV_FIELDS'})['CSV_FIELDS'],
            'examples': examples, 'stage4': stage4, 'trace_span_count': len(spans), 'dashboard_panels': dashboard_panels()}


def render_facts(facts):
    out = ['# Verified facts extracted during packaging',
           'These tables are derived offline from the copied configuration and archived records, not live queries. Full originals are in `source/`.']
    out += ['## Services and deployment', table(['Service','CPU ceiling','Memory MiB','Profile','Loopback publication'],
             [(n,s['cpus'],s['memory_mib'],','.join(s['profiles']) or 'base',','.join(s['published_loopback_ports']) or 'internal only') for n,s in facts['services'].items()]),
            'Named volumes: ' + ', '.join('`'+v+'`' for v in facts['volumes']) + '.',
            table(['Preset','Compute CPU each','Data memory MiB','Compute instances'],
                  [(n,p['compute_cpus'],p['data_memory_mib'],p['replicas']) for n,p in facts['deployment_presets'].items()])]
    out += ['## Public Controller routes', table(['Method','Route','Handler'],[(r['method'],r['path'],r['handler']) for r in facts['controller_routes']]),
            '`GET /metrics` is additionally installed by shared metrics support.',
            '## Internal worker routes', table(['Method','Route','Handler'],[(r['method'],r['path'],r['handler']) for r in facts['worker_routes']]),
            'The payload route exists only on Compute. Health/state/metrics are internal for Compute/Data; host publications are listed above.',
            '## CSV columns', fenced(json.dumps(facts['csv_fields'],ensure_ascii=False,indent=2),'json'),
            '## Resolved input model', fenced(json.dumps(facts['model'],ensure_ascii=False,indent=2),'json')]
    rows = []
    for kind,entry in facts['examples'].items():
        run = entry['run']
        rows.append((kind,run['id'],f"{run['elapsed_seconds']:.3f}",run['state'],run['persistence'],run['counters']['errors']))
    out += ['## Stage 5 examples — one run each', table(['Scenario','Run ID','Elapsed s','Outcome','History','Operation errors'],rows)]
    for kind,entry in facts['examples'].items():
        run = entry['run']
        selected = {key:run.get(key) for key in ['id','name','workload','profile','settings','created_at','started_at','finished_at','elapsed_seconds','state','persistence','counters','rates','target_service','target_services','trace_id','deployment']}
        out += [f'### {kind}: exact saved configuration/results', fenced(json.dumps(selected,ensure_ascii=False,indent=2),'json'),
                f'Source: `source/docs/evidence/stage5/{kind}/run.json`. Resource summaries below use 30-second CPU/interface averages; working-set values are MiB.',
                table(['Service','Peak CPU 30 s, cores','Working set baseline → peak → cooldown, MiB','Peak receive / transmit 30 s, MiB/s'],
                      [(s,f"{v['peak_cpu_30s']:.6f}", ' → '.join(f"{v[k]:.6f}" for k in ['baseline_memory_mib','peak_memory_mib','cooldown_memory_mib']),
                        f"{v['peak_receive_30s']/1048576:.6f} / {v['peak_transmit_30s']/1048576:.6f}") for s,v in entry['resources'].items()]),
                'Exact evidence window: ' + fenced(json.dumps(entry['window'],ensure_ascii=False,indent=2),'json')]
    out += ['## Stage 4 fixed-work acceptance observations',
            'Each row is a saved acceptance run, not a mean over repeated trials. Recent CPU uses irate observations, not the Stage 5 30-second average. All rows below complete 32 logical batches / 80,000 units / checksum 12,007,132,800,000 with two calculation processes total.',
            table(['Preset','Run ID','Elapsed s','Recent CPU peaks, cores','Observed calculation processes'],
                  [(p,facts['stage4']['runs'][p]['id'],f"{facts['stage4']['runs'][p]['elapsed_seconds']:.3f}",
                    ', '.join(f'{s}: {v:.6f}' for s,v in facts['stage4']['measurements'][p]['peak_cpu_cores'].items()),
                    facts['stage4']['measurements'][p]['peak_calculation_processes']) for p in ['cpu-05','cpu-1','cpu-2','replica-1','replica-2']]),
            'Independent Docker CPU sample for cpu-2: ' + str(facts['stage4']['measurements']['cpu-2']['docker_cpu_sample_cores']) + ' cores.',
            table(['Data preset','Run ID','Buffer MiB','Elapsed s','Sampled peak working set MiB'],
                  [(p,facts['stage4']['runs'][p]['id'],facts['stage4']['runs'][p]['settings']['memory_mib'],
                    f"{facts['stage4']['runs'][p]['elapsed_seconds']:.3f}",f"{facts['stage4']['measurements'][p]['peak_working_set_bytes']['data']/1048576:.6f}") for p in ['memory-256','memory-512','memory-1024']]),
            'The full assignments, per-batch checksums and interrupted/cancelled/recovery cases remain in `source/docs/evidence/stage4/acceptance.json`.',
            '## Verification categories', table(['Category','Archived count'], [('Automated regression tests',31),('Stage 4 live acceptance',140),('Stage 4 dashboard checks',22),('Stage 4 lifecycle checks',20),('Final Stage 5 checks',127),('Report checks',46)]),
            'Packaging performs its own offline checks and records them separately. It does not rerun those application suites.']
    return '\n\n'.join(out)


def render_queries(panels):
    out = ['# Exact provisioned dashboard queries', 'These are the copied expressions, not simplified approximations. `$service` is a dashboard variable. Panel IDs/UIDs identify the original provisioned dashboards.']
    for panel in panels:
        out += [f"## {panel['uid']} / panel {panel['id']}: {panel['title']}",
                f"Unit setting: `{panel['unit']}`. {panel['description']}"]
        for query in panel['queries']:
            out += [f"Legend: `{query['legend']}`", fenced(query['expression'],'promql')]
    return '\n\n'.join(out)


def figure_prompt(figure):
    assets = '\n'.join('- source/' + p for p in figure['inputs'])
    required = '\n'.join('- ' + r for r in figure['requirements'])
    limits = '\n'.join('- ' + r for r in figure['limitations'])
    captures = '\n'.join(f'{i}. {s}' for i,s in enumerate(figure.get('capture_steps',[]),1))
    action = ('Use only a genuine capture. If absent, give the exact capture steps and identify the missing attachment; do not fabricate it.'
              if figure['method']=='capture_required' else
              'Reuse the genuine screenshot; crop only without changing evidence.' if figure['method']=='reuse_screenshot' else
              'Reuse the measured PNG/SVG. An Albanian redraw must use a plotting tool and the attached actual sample matrix, never generated curves.' if figure['method']=='reuse_measured_plot' else
              'Create a conceptual diagram with the shared white-background style, correct topology and Albanian labels. Keep editable diagram source when your tools support it.')
    return (f"I need Figure {figure['number']} for the attached Albanian report.\n\n{figure['request']}\n\n"
            f"Exact separate Word caption: Figura {figure['number']}: {figure['caption']}\n"
            f"Report section: {figure['section']}; original report page {figure['page']}.\n"
            f"Output filename: {figure['output']}\n\nProduction rule: {action}\n\n"
            f"Use these supplied files (ask me to attach any that are not accessible):\n{assets}\n\n"
            f"Required facts/content:\n{required}\n\nCropping/composition: {figure['crop']}\n\n"
            f"Limitations to preserve:\n{limits}\n\n" + (f"Genuine capture checklist:\n{captures}\n\n" if captures else '') +
            "Read 01_PROJECT_CONTEXT.md for full implementation and the three style images for appearance only. "
            "Return a downloadable PNG when possible, editable source where available, the exact Albanian caption, a short check naming the source files, and Albanian placement instructions. "
            "Preserve aspect ratio at up to 16.51 cm Word width; report whether the original frame height permits readable text. "
            "Do not bake the figure number/caption into the pixels, alter the Word report, run experiments, invent missing UI/data, or claim tool capabilities/files you do not have.")


def render_catalog(figures):
    out = ['# Figure catalog and ready-to-use prompts',
           'The section/page numbers refer to the unchanged 25-page Word report before images are inserted. The caption text and frame sizes are checked directly against OOXML. Three genuine captures remain missing; no final generated figures are created by this bundle.',
           table(['Figure','Exact Albanian title','Method','Report page','Original frame cm'],
                 [(f['number'],f['caption'],f['method'],f['page'],f"{f['frame_width_cm']:.2f} × {f['frame_height_cm']:.1f}") for f in figures])]
    for f in figures:
        out += [f"## Figure {f['number']} — {f['caption']}", f['purpose'],
                f"**Location:** {f['section']}, page {f['page']}. **Action:** {f['method']}. **Output:** `{f['output']}`.",
                f"**Placeholder:** {f['frame_width_cm']:.2f} × {f['frame_height_cm']:.1f} cm. Preserve aspect ratio; this is not a fixed crop instruction.",
                '**Attachments:**\n' + '\n'.join(f'- [{p}](source/{p})' for p in f['inputs']),
                '**Required content:**\n' + '\n'.join('- '+r for r in f['requirements']),
                '**Crop/composition:** '+f['crop'], '**Limitations:**\n'+'\n'.join('- '+s for s in f['limitations'])]
        if f.get('capture_steps'):
            out += ['**Capture steps:**\n'+'\n'.join(f'{i}. {s}' for i,s in enumerate(f['capture_steps'],1))]
        out += ['### Ready-to-use request', fenced(figure_prompt(f),'text')]
    return '\n\n'.join(out)


def placement_guide(figures, inputs):
    rows = []
    for f in figures:
        size = image_size(inputs[f['primary']]) if f['primary'] else None
        if size:
            scale = min(f['frame_width_cm']/size[0], f['frame_height_cm']/size[1])
            fit = f'{size[0]*scale:.2f} × {size[1]*scale:.2f}'
        else:
            fit = 'Measure the genuine new capture first'
        rows.append((f['number'],f['output'],f"{f['frame_width_cm']:.2f} × {f['frame_height_cm']:.1f}",
                     ' × '.join(map(str,size)) if size else 'capture missing',fit))
    return ('# Udhëzuesi i vendosjes së figurave\n\n'
            'Dokumenti burimor mbetet i pandryshuar. Punoni në një kopje kur të vendosni figurat. Mos e futni titrin dy herë: ai ekziston poshtë kornizës në Word. Zëvendësoni vetëm përmbajtjen e kornizës dhe hiqni udhëzimet e përkohshme të burimit pasi të keni vendosur pamjen.\n\n'
            'Gjerësia e përdorshme është rreth 16.51 cm. Ruani raportin gjerësi/lartësi. Për figurat e reja përdorni dimensionet reale të PNG-së. Tabela më poshtë llogarit përshtatjen pa prerje për pamjen ekzistuese, jo madhësinë e detyrueshme të një diagrami të ridizenjuar.\n\n' +
            table(['Figura','Skedari i kërkuar','Korniza origjinale, cm','Pamja ekzistuese, px','Përshtatja pa shtrembërim, cm'],rows) +
            '\n\nNëse etiketat nuk lexohen në madhësinë e kornizës, kërkoni diagram më të përmbledhur ose riparaqitje të grafikut nga të dhënat reale me fonte të përshtatshme. Nëse nevojitet figurë më e madhe, lejoni ndryshimin e lartësisë dhe kontrolloni faqosjen; mos shtrini figurën dhe mos hiqni boshte ose prova për ta futur me detyrim. Raporti ka 25 faqe përpara vendosjes së imazheve.\n\n'
            'Pamjet reale mund të mbajnë tekstin e ndërfaqes në anglisht. Titrat dhe shpjegimet mbeten në shqip. Fotot e ekranit nuk duhen ripikturuar për të ndryshuar numra/gjendje. Për Figurën 4 përgatitni realisht baseline me gjurmim dhe nëntë shërbime; mos përdorni një pamje me dhjetë si provë të nëntë.\n\n'
            'Pas futjes, kontrolloni ndarjen e tabelave/figurave ndërmjet faqeve, titrat, madhësinë e tekstit dhe numrat. Përditësoni përmbajtjen automatike dhe fushat në Word. Ruani veçmas versionin e plotësuar.\n\n'
            '## Titrat që duhen ruajtur\n\n' + '\n\n'.join(f"Figura {f['number']}: {f['caption']}" for f in figures))


def verify_archive(path, extraction_parent=None):
    """Verify hashes and independently extract into a fresh private temporary folder."""
    with ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('ZIP CRC verification failed.')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP paths.')
        for info in archive.infolist():
            name = info.filename
            parts = PurePosixPath(name)
            if ('\\' in name or parts.is_absolute() or '..' in parts.parts or ':' in name
                    or not parts.parts or parts.parts[0] != PACKAGE
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe archive member: ' + name)
            if blocked(parts):
                raise ValueError('Local-only material in archive: ' + name)
        manifest_path = PACKAGE + '/manifest.json'
        manifest = json.loads(archive.read(manifest_path))
        expected = {PACKAGE + '/' + f['path']: f for f in manifest['files']}
        if set(names) != set(expected) | {manifest_path}:
            raise ValueError('ZIP contents differ from the manifest.')
        for name,item in expected.items():
            data = archive.read(name)
            if len(data) != item['bytes'] or digest(data) != item['sha256']:
                raise ValueError('Hash/size mismatch: ' + name)
        with tempfile.TemporaryDirectory(prefix='cloud-lab-archive-check-', dir=extraction_parent) as temp:
            destination = Path(temp).resolve()
            intended_parent = Path(extraction_parent).resolve() if extraction_parent else Path(tempfile.gettempdir()).resolve()
            if not destination.is_relative_to(intended_parent):
                raise ValueError('Extraction target is outside its verified build directory.')
            for name in names:
                if not (destination / name).resolve().is_relative_to(destination):
                    raise ValueError('Extraction target escapes its temporary directory.')
            archive.extractall(destination)
            for name,item in expected.items():
                if digest((destination / name).read_bytes()) != item['sha256']:
                    raise ValueError('Extracted content mismatch: ' + name)
            report = destination / PACKAGE / REPORT.name
            if digest(report.read_bytes()) != manifest['report']['sha256']:
                raise ValueError('The extracted report differs from its source.')
        return {'zip_crc':True, 'safe_unique_paths':True, 'exact_manifest_inventory':True,
                'all_hashes_match':True, 'fresh_extraction_succeeded':True, 'extracted_hashes_match':True,
                'extracted_report_unchanged':True, 'payload_file_count':len(expected), 'zip_sha256':digest(Path(path).read_bytes())}


def build(output_dir):
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise ValueError('Bundle acceptance check failed: ' + name)
    names = project_files()
    inputs = {name:(ROOT/name).read_bytes() for name in names}
    input_hashes = {name:digest(data) for name,data in inputs.items()}
    check('current_report_in_snapshot', REPORT.as_posix() in inputs)
    report_bytes = inputs[REPORT.as_posix()]
    proof = read_json('docs/raporti/verifikimi-raporti-plote.json')
    check('report_matches_25_page_verified_delivery', proof['pages'] == 25 and digest(report_bytes) == proof['delivered_sha256'] and len(proof['checks']) == 46 and all(proof['checks'].values()))
    placeholders, chapters, report_text = report_inventory(report_bytes)
    check('abstract_and_five_report_chapters', len(chapters) == 6 and chapters[0] == 'Abstrakti' and all(chapters[i].startswith(prefix) for i,prefix in enumerate(['I.','II.','III.','IV.','V.'],1)))
    figures = read_json(AUTHORING/'figures.json')
    check('sixteen_unique_numbered_figures', [f['number'] for f in figures] == list(range(1,17)) and set(placeholders) == set(range(1,17)))
    chapter_sources = '\n'.join((ROOT/f'docs/raporti/kapitulli-{n}.md').read_text(encoding='utf-8') for n in [2,3])
    source_figures = {int(parts[1]):parts for line in chapter_sources.splitlines() if line.startswith('[[FIGURE|') for parts in [line[2:-2].split('|')]}
    for f in figures:
        n = f['number']
        info = placeholders[n]
        check(f'figure_{n:02}_caption_and_source_match_report', f['caption'] == info['caption'] == source_figures[n][2] and info['placeholder_source'] == source_figures[n][3])
        check(f'figure_{n:02}_all_supporting_inputs_present', all(p in inputs for p in f['inputs']))
        f.update(info)
        if f['primary']:
            check(f'figure_{n:02}_primary_image_valid', f['primary'] in inputs and image_size(inputs[f['primary']]) is not None)
        if f.get('scenario'):
            run = read_json(f"docs/evidence/stage5/{f['scenario']}/run.json")['run']
            check(f'figure_{n:02}_run_id_matches_prompt', any(run['id'] in text for text in f['requirements']))
    check('exactly_three_missing_genuine_captures', [f['number'] for f in figures if f['primary'] is None] == CAPTURE_IDS and [f['number'] for f in figures if f['method']=='capture_required'] == CAPTURE_IDS)
    check('only_two_diagram_redesigns', [f['number'] for f in figures if f['method']=='redesign_diagram'] == [1,2])
    check('exactly_four_measured_plot_entries', [f['number'] for f in figures if f['method']=='reuse_measured_plot'] == [13,14,15,16])
    for i in range(1,4):
        style = (AUTHORING / f'style-references/style-reference-{i:02}.png').as_posix()
        check(f'style_reference_{i}_is_valid_original_png', style in inputs and image_size(inputs[style])[0] == 975)
    style_origins = read_json(AUTHORING/'style-references/origins.json')['references']
    check('style_bytes_match_recorded_user_attachments', len(style_origins) == 3 and all(digest(inputs[(AUTHORING/'style-references'/s['file']).as_posix()]) == s['sha256'] for s in style_origins))
    for name,data in inputs.items():
        scan_secrets(name,data)
    check('snapshot_excludes_local_only_files_and_obvious_secrets', all(not blocked(PurePosixPath(name)) for name in inputs))
    facts = derive_facts(check)
    revision = git('rev-parse','HEAD')
    status = git('status','--porcelain=v1','--untracked-files=all')
    now = datetime.now(timezone.utc)
    build_dir = output_dir.resolve() / (now.strftime('%Y%m%dT%H%M%SZ') + '-' + revision[:7] + '-' + uuid4().hex[:6])
    build_dir.mkdir(parents=True, exist_ok=False)
    package_dir = build_dir / PACKAGE
    package_dir.mkdir()
    origins = {}
    def write(relative, value, origin=None):
        path = package_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        if origin:
            origins[relative] = origin
    for name,data in inputs.items():
        write('source/'+name,data,name)
    write(REPORT.name,report_bytes,REPORT.as_posix())
    for i in range(1,4):
        original = (AUTHORING/f'style-references/style-reference-{i:02}.png').as_posix()
        write(f'style-reference-{i:02}.png',inputs[original],original)
    for source,dest in [('project-instructions.md','PROJECT_INSTRUCTIONS.md'),('opening-prompt.md','OPENING_PROMPT.md'),('style-guide.md','STYLE_GUIDE.md')]:
        original = (AUTHORING/source).as_posix()
        write(dest,inputs[original],original)
    catalog = render_catalog(figures)
    write('FIGURE_CATALOG.md',catalog)
    write('PLACEMENT_GUIDE.md',placement_guide(figures,inputs))
    write('PROJECT_FACTS.json',json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    for f in figures:
        write(f"prompts/figure-{f['number']:02}.md",figure_prompt(f)+'\n')
    write('outputs/README.md','# Future figure outputs\n\nNo final figures are generated in this bundle. Save approved PNGs under the sixteen catalog filenames, keeping captions separate. Word insertion remains manual.\n')
    initial = ['01_PROJECT_CONTEXT.md',REPORT.name,'style-reference-01.png','style-reference-02.png','style-reference-03.png']
    write('START_HERE.md', '# Start here — ChatGPT report-figure bundle\n\n'
          '1. Extract this ZIP. Create a new ChatGPT Project for the Cloud Lab report figures.\n'
          '2. Upload the following five files as the initial Sources:\n\n' + '\n'.join('- `'+p+'`' for p in initial) + '\n\n'
          '3. Paste PROJECT_INSTRUCTIONS.md into Project instructions, then paste OPENING_PROMPT.md into the first chat.\n'
          '4. Ask for one figure number at a time. Copy its request from FIGURE_CATALOG.md or prompts/figure-NN.md. Attach its listed originals from source/ when needed.\n'
          '5. Collect PNGs, exact Albanian captions and placement guidance. Insert them into a copy of Word yourself; update fields and check pagination afterward.\n\n'
          'The ZIP is a transport package, not a promise of automatic knowledge indexing. Do not assume prior chats, local folders, live dashboards or embedded PDF images are available. Account upload limits vary; only attach what the interface permits.\n\n'
          'The master file includes the comprehensive handoff, all sixteen prompts, extracted current facts/queries, complete application/configuration sources and reference documentation. The source/ snapshot supplies actual image pixels, SVGs, CSV/JSON matrices and traces. The Word copy is unchanged.\n\n'
          'Missing genuine captures: Figures 3 (Compose), 4 (nine baseline containers with tracing), 10 (fixed_work.py). Figures 1–2 may be redesigned. Seven archived screenshots and four measured plots are supplied as evidence; do not invent replacements.\n\n'
          'The report is text-complete, but cover identities/logo and image insertion remain. The initial layout has 25 pages. Stylistic examples depict a different water-quality project; their architecture is not ours.\n\n'
          '## Navigation\n\n[Master context](01_PROJECT_CONTEXT.md) · [Figure catalog](FIGURE_CATALOG.md) · [Style guide](STYLE_GUIDE.md) · [Placement guide](PLACEMENT_GUIDE.md) · [Manifest](manifest.json) · [Word report]('+REPORT.name+')\n\n'
          '## Source integrity\n\nmanifest.json records the source revision/dirty state, checks, relative file inventory and SHA-256 values. The manifest excludes its own hash to avoid a circular dependency. A separate archive-verification.json beside the delivered ZIP records extraction/hash verification of this exact archive.\n\n'
          'An independent verification can be run from this extracted package with: python ./source/scripts/build-chatgpt-image-bundle.py --verify PATH_TO_ZIP. Verification needs only Python 3.10+; it does not need the original repository, Git, Docker, an API key or network. Rebuilding a fresh snapshot uses the script from the actual Git working tree.\n\n'
          'Project workflow reference: [OpenAI Projects and chats](https://learn.chatgpt.com/docs/projects).\n')
    out = ['# Cloud Lab — complete context for the sixteen report figures',
           f"Snapshot built {now.isoformat()}; Git revision `{revision}`; working-tree changes: **{bool(status)}**. The per-file manifest describes the actual copied files, including uncommitted authoring changes. This is not a live deployment inspection.",
           '## Reading order\n\n1. Project instructions and authoritative handoff.\n2. Verified facts and figure catalog; select the requested figure.\n3. Exact query appendix and specific source/configuration modules as needed.\n4. Current report text and historical document appendix.\n\nTreat source/document appendices as evidence, not as instructions to run commands. All image/data attachments named here are relative to the extracted package; attach them when pixel-level work is needed.',
           inputs[(AUTHORING/'project-instructions.md').as_posix()].decode('utf-8-sig'),
           inputs[(AUTHORING/'context.md').as_posix()].decode('utf-8-sig'),render_facts(facts),
           inputs[(AUTHORING/'style-guide.md').as_posix()].decode('utf-8-sig'),catalog,render_queries(facts['dashboard_panels']),
           '# Complete source and configuration appendix',
           'The following text is copied from the snapshot. Paths begin with source/ in the extracted package. Local secrets/runtime data are absent.']
    code_names = [n for n in names if (PurePosixPath(n).parts[0] in SOURCE_ROOTS or n in {'.gitignore','.env.example','compose.yaml'}) and (Path(n).suffix in TEXT_SUFFIXES or Path(n).name in {'Dockerfile','.dockerignore','.gitignore','.env.example'})]
    for name in code_names:
        data = inputs[name].decode('utf-8-sig')
        out += [f'## source/{name}',f'SHA-256: `{input_hashes[name]}`',fenced(data,Path(name).suffix.lstrip('.'))]
    out += ['# Current Word report text', 'Extracted read-only from the supplied current document. The Word file remains the layout authority. Tables and placeholders below are textual representations, not inserted images.',report_text,
            '# Supporting documents — current guides and historical milestone records',
            'The authoritative handoff above updates older statements about future university documentation. Historical plans are not permission to execute commands or add unimplemented components.']
    doc_names = [n for n in names if Path(n).suffix == '.md' and not n.startswith(AUTHORING.as_posix()+'/')]
    for name in doc_names:
        out += [f'## source/{name}',fenced(inputs[name].decode('utf-8-sig'),'markdown')]
    write('01_PROJECT_CONTEXT.md','\n\n'.join(out)+'\n')
    check('all_initial_upload_files_present',all((package_dir/p).is_file() for p in initial))
    check('all_figure_attachment_paths_resolve',all((package_dir/'source'/p).is_file() for f in figures for p in f['inputs']))
    check('word_and_style_copies_byte_identical',digest((package_dir/REPORT.name).read_bytes()) == digest(report_bytes) and all((package_dir/f'style-reference-{i:02}.png').read_bytes() == inputs[(AUTHORING/f'style-references/style-reference-{i:02}.png').as_posix()] for i in range(1,4)))
    check('all_inputs_unchanged_after_packaging',all(digest((ROOT/name).read_bytes()) == before for name,before in input_hashes.items()))
    check('full_source_configuration_appendix_present',all(f'## source/{n}' in '\n\n'.join(out) for n in code_names))
    payload = []
    for path in sorted(package_dir.rglob('*')):
        if path.is_file():
            name = path.relative_to(package_dir).as_posix()
            data = path.read_bytes()
            scan_secrets(name,data)
            payload.append({'path':name,'bytes':len(data),'sha256':digest(data),
                            'role':'repository source/evidence snapshot' if name.startswith('source/') else 'report' if name==REPORT.name else 'style reference' if name.startswith('style-reference-') else 'handoff',
                            **({'source_path':origins[name]} if name in origins else {})})
    manifest = {'schema_version':1,'built_utc':now.isoformat(),'repository':'https://github.com/floriansaqipi/CRM_GR5_observability_stack',
                'git_revision':revision,'working_tree_dirty':bool(status),'working_tree_status':status.splitlines(),
                'report':{'path':REPORT.name,'source_path':REPORT.as_posix(),'sha256':digest(report_bytes),'pages_before_insertion':25},
                'initial_upload_files':initial,'missing_capture_figures':CAPTURE_IDS,'source_file_count':len(inputs),
                'source_config_appendix_file_count':len(code_names),'reference_document_appendix_file_count':len(doc_names),
                'figures':[{'number':f['number'],'caption':f['caption'],'report_page':f['page'],'section':f['section'],'method':f['method'],
                            'output_filename':f['output'],'primary_asset':'source/'+f['primary'] if f['primary'] else None,
                            'supporting_files':['source/'+p for p in f['inputs']], 'placeholder_source':f['placeholder_source'],
                            'frame_width_cm':f['frame_width_cm'],'frame_height_cm':f['frame_height_cm']} for f in figures],
                'checks':checks,'files':payload}
    write('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive_path = build_dir / (PACKAGE+'.zip')
    with ZipFile(archive_path,'w',compression=ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(package_dir.rglob('*')):
            if path.is_file():
                archive.write(path,PACKAGE+'/'+path.relative_to(package_dir).as_posix())
    archive_checks = verify_archive(archive_path,build_dir)
    result = {'built_utc':now.isoformat(),'archive':archive_path.name,'zip_bytes':archive_path.stat().st_size,
              'acceptance_check_count':len(checks),'acceptance_checks':checks,'archive_checks':archive_checks,
              'note':'No final images generated, no Word edits, no workload/deployment operations. Source snapshot is identified by revision plus working-tree file hashes.'}
    (build_dir/'archive-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'zip':str(archive_path),'extracted_package':str(package_dir),'verification':str(build_dir/'archive-verification.json'),
                      'zip_bytes':archive_path.stat().st_size,'payload_files':len(payload),'source_files':len(inputs),'offline_checks':len(checks),'archive_checks_passed':True},ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'.runtime/chatgpt-image-bundle',help='Parent directory for a new uniquely named build; existing outputs are never deleted.')
    parser.add_argument('--verify',type=Path,help='Verify and safely test-extract an existing bundle instead of building.')
    args = parser.parse_args()
    try:
        if args.verify:
            print(json.dumps(verify_archive(args.verify),ensure_ascii=False))
        else:
            build(args.output_dir)
    except (ValueError,KeyError,OSError,BadZipFile,ET.ParseError) as error:
        parser.exit(1,f'Bundle error: {error}\n')


if __name__ == '__main__':
    main()
