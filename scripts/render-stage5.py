"""Render saved measurements and readable guide diagrams; never generate test data.

Install scripts/plot-requirements.txt in a local Python 3.12+ environment.
Run after measure-stage5.py finishes. The application does not need these packages.
"""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'docs/evidence/stage5'
ASSETS = ROOT/'docs/assets'
COLORS = {'compute':'#1684A4','data':'#B57518','mongodb':'#32815C','controller':'#386BAB'}
TITLES = {'cpu':'CPU calculation','memory':'Memory hold','network':'Network transfer','combined':'Combined Data'}


def series(data, key, service, start):
    for item in data[key]['result']:
        if item['metric'].get('service') == service:
            values = [(t-start,float(v)) for t,v in item['values'] if t >= start-30 and v not in ('NaN','+Inf','-Inf')]
            if values:
                return list(zip(*values))
    return [],[]


def resource_plot(kind, entry):
    data = json.loads((OUT/kind/'measurements.json').read_text())
    run = entry['run']
    accepted = datetime.fromisoformat(run['created_at']).timestamp()
    finished = datetime.fromisoformat(run['finished_at']).timestamp()-accepted
    services = ['compute'] if kind=='cpu' else ['data'] if kind=='memory' else ['data','compute'] if kind=='network' else ['data','mongodb','compute']
    fig, axes = plt.subplots(3,1,figsize=(11,8.4),sharex=True)
    fig.subplots_adjust(top=.80,bottom=.16,hspace=.42,left=.085,right=.975)
    fig.suptitle(TITLES[kind]+' / one measured example',x=.085,y=.965,ha='left',fontsize=18,fontweight='bold',color='#172C3B')
    fig.text(.085,.918,'Run '+run['id']+'  ·  baseline, tracing enabled  ·  '+run['created_at'][:19]+' UTC',fontsize=9,color='#526575')
    for index,(key,label) in enumerate([('cpu_30s','CPU (cores, 30-second average)'),('memory_mib','Working-set memory (MiB)'),('receive_30s','Interface traffic (MiB/s, 30-second average)')]):
        ax = axes[index]
        ax.axvspan(0,finished,color='#DCE8EE',alpha=.65,zorder=0)
        ax.axvline(0,color='#56778A',linewidth=1,linestyle='--')
        ax.axvline(finished,color='#56778A',linewidth=1,linestyle='--')
        found = False
        if index < 2:
            for service in services:
                x,y = series(data,key,service,accepted)
                if x:
                    ax.plot(x,y,label=service,color=COLORS[service],linewidth=1.8,marker='o',markersize=2.5)
                    found = True
        else:
            directions = [('receive_30s','data','Data receive'),('transmit_30s','compute','Compute transmit')] if kind in ('network','combined') else [('receive_30s',services[0],'Receive'),('transmit_30s',services[0],'Transmit')]
            for n,(query,service,title) in enumerate(directions):
                x,y = series(data,query,service,accepted)
                if x:
                    ax.plot(x,[v/1048576 for v in y],label=title,color=COLORS[service] if kind in ('network','combined') else ('#1684A4' if n==0 else '#B57518'),linewidth=1.8,marker='o',markersize=2.5)
                    found = True
        ax.set_title(label,loc='left',fontsize=10,fontweight='bold',pad=9)
        ax.set_ylim(bottom=0)
        ax.set_xlim(-30,finished+30)
        ax.grid(axis='y',color='#DCE3E8',linewidth=.65)
        ax.spines[['top','right']].set_visible(False)
        ax.spines[['left','bottom']].set_color('#BBCBD4')
        ax.tick_params(labelsize=8,colors='#425A6A')
        if found: ax.legend(loc='upper left',fontsize=8,frameon=False,ncol=3)
        else: ax.text(.5,.5,'Unavailable',transform=ax.transAxes,ha='center')
        if index==0:
            ax.text(-15,1.22,'IDLE BASELINE',transform=ax.get_xaxis_transform(),ha='center',fontsize=8,color='#526575')
            ax.text(finished/2,1.22,'EXPERIMENT ACTIVE',transform=ax.get_xaxis_transform(),ha='center',fontsize=8,color='#526575')
            ax.text(finished+15,1.22,'COOLDOWN',transform=ax.get_xaxis_transform(),ha='center',fontsize=8,color='#526575')
        primary = 'compute' if kind=='cpu' else 'data'
        resource = entry['resources'][primary]
        if index==1:
            ax.text(1,1.06,f"{primary} peak: {resource['peak_memory_mib']:.1f} MiB",transform=ax.transAxes,ha='right',va='bottom',fontsize=9,color='#344D5C')
    axes[-1].set_xlabel('Seconds relative to Start acceptance',fontsize=10,labelpad=9)
    fig.text(.085,.035,'Five-second query samples. Shading marks the Controller lifecycle, including dispatch/cleanup.\nRates are averaged; working set includes application, child and telemetry. Payload counts remain in the saved run.',fontsize=8,color='#526575')
    for extension in ('png','svg'):
        fig.savefig(OUT/kind/('resources.'+extension),dpi=160,facecolor='white')
    plt.close(fig)


def diagram(title,nodes,edges,name,subtitle):
    fig,ax = plt.subplots(figsize=(12,6.0))
    fig.subplots_adjust(left=.02,right=.98,bottom=.04,top=.82)
    ax.set(xlim=(0,1),ylim=(0,1))
    ax.axis('off')
    fig.text(.04,.94,title,fontsize=19,fontweight='bold',color='#172C3B')
    fig.text(.04,.885,subtitle,fontsize=10,color='#526575')
    for key,(x,y,w,h,label,color) in nodes.items():
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012,rounding_size=0.015',facecolor='#F5F8FA',edgecolor=color,linewidth=1.6))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10,linespacing=1.6,color='#203F50')
    for start,end,label,curve in edges:
        a,b = nodes[start],nodes[end]
        if start=='controller' and end=='mongo':
            x1=a[0]+a[2]/2; x2=b[0]+b[2]/2
            ax.plot([x1,x1,x2],[a[1],.14,.14],color='#58798A',linewidth=1.3)
            ax.add_patch(FancyArrowPatch((x2,.14),(x2,b[1]),arrowstyle='-|>',mutation_scale=13,linewidth=1.3,color='#58798A'))
            ax.text((x1+x2)/2,.095,label,ha='center',fontsize=8,color='#425D6E')
            continue
        p1=(a[0]+a[2],a[1]+a[3]/2)
        p2=(b[0],b[1]+b[3]/2)
        if start=='data' and end=='compute':
            p1=(a[0]+a[2]/2,a[1]+a[3]); p2=(b[0]+b[2]/2,b[1])
        ax.add_patch(FancyArrowPatch(p1,p2,arrowstyle='-|>',mutation_scale=13,connectionstyle=f'arc3,rad={curve}',linewidth=1.3,color='#58798A'))
        if label:
            x,y=((p1[0]+p2[0])/2,(p1[1]+p2[1])/2)
            if curve: y-=.17
            else: y+=.045
            if start=='data' and end=='compute': x+=.11; y-=.045
            ax.text(x,y,label,ha='center',va='center',fontsize=8,color='#425D6E',bbox={'facecolor':'white','edgecolor':'none','pad':2})
    for extension in ('png','svg'):
        fig.savefig(ASSETS/(name+'.'+extension),dpi=160,facecolor='white')
    plt.close(fig)


def diagrams():
    ASSETS.mkdir(exist_ok=True)
    nodes={'browser':(.02,.67,.16,.18,'Your browser\nConfigure / Start / Stop','#386BAB'),
           'controller':(.27,.67,.18,.18,'Controller\nOne global run slot','#368C7B'),
           'compute':(.55,.74,.19,.18,'Compute\nCPU + payloads','#1684A4'),
           'data':(.55,.33,.19,.18,'Data\nMemory / network / DB','#B57518'),
           'mongo':(.81,.33,.17,.18,'MongoDB\nHistory + documents','#32815C')}
    edges=[('browser','controller','',0),('controller','compute','CPU',0),('controller','data','Data work',0),('data','compute','Download\npayloads',0),('data','mongo','Write/read',0),('controller','mongo','Save experiment summaries',.65)]
    diagram('The application: control, execute, remember',nodes,edges,'application-architecture','Monitoring observes these containers independently. The web application links each run to Grafana.')
    (ASSETS/'application-architecture.mmd').write_text('''flowchart LR
    Browser[Browser: configure, Start, Stop] --> Controller[Flask Controller: one active experiment]
    Controller -->|CPU work| Compute[Compute]
    Controller -->|Data work| Data[Data]
    Data -->|Download payloads| Compute
    Data -->|Write/read workload documents| MongoDB[(MongoDB)]
    Controller -->|Save experiment summaries| MongoDB
''')
    nodes={}
    edges=[]
    labels=[['Linux containers\nCPU / memory / network','cAdvisor\nResource exporter','Prometheus\nResource time series','Grafana\nContainer Resources'],
            ['Controller / Compute / Data\nApplication /metrics','Prometheus\nDirect scraping','Grafana\nApplication Performance'],
            ['Applications + children\nRelated trace spans','OTel Collector\nBatch / forward','Tempo\nTrace storage','Grafana\nTrace exploration']]
    for r,row in enumerate(labels):
        for c,label in enumerate(row):
            key=f'{r}-{c}'
            nodes[key]=(.02+c*.25,.72-r*.31,.20,.18,label,['#1684A4','#B57518','#7256A5'][r])
            if c: edges.append((f'{r}-{c-1}',key,'',0))
    diagram('Three paths, three different questions',nodes,edges,'telemetry-paths','Resources: what did containers consume?  Applications: what work happened?  Traces: how were operations connected?')
    (ASSETS/'telemetry-paths.mmd').write_text('''flowchart LR
    subgraph Resources
      C[Linux containers] --> A[cAdvisor] --> P[Prometheus] --> G[Grafana: Container Resources]
    end
    subgraph Application_metrics
      F[Controller / Compute / Data: metrics] --> P2[Prometheus] --> G2[Grafana: Application Performance]
    end
    subgraph Traces
      T[Applications and child processes] --> O[OpenTelemetry Collector] --> Tempo --> G3[Grafana: Trace exploration]
    end
''')


def report(manifest):
    lines=['# Four examples: what we measured','',
           'These are four single-run demonstrations on the local Docker Desktop laboratory, recorded on **1 November 2026**. They show observable behaviour, rather than a repeated benchmark or a promised performance improvement.','',
           '## Setup and method','',
           'All runs used the verified **baseline** deployment with tracing enabled: Compute and Data each had one CPU and 512 MiB memory ceilings. All nine application/monitoring images stayed unchanged. Runs used Medium intensity and 30 seconds of work, one at a time.','',
           'Each run had at least 30 seconds of idle observation and 30 seconds of cooldown. Manual preparation sometimes extended the idle period; exact windows are saved. The plots show the last 30 seconds before Start, the experiment lifecycle, and cooldown. Prometheus query samples are five seconds apart. CPU and interface rates use the existing **30-second averages**.','',
           '## Actual work','',
           '| Example | Resolved inputs | Work elapsed | Reported work / achieved rate | Errors |','|---|---|---:|---|---:|']
    for kind,entry in manifest['runs'].items():
        r=entry['run']; c=r['counters']; rates=r['rates']
        if kind=='cpu': settings='50% busy time'; work=f"{c['cpu_batches']:,} calculation batches; {rates['cpu_batches_per_second']:,.1f}/s"
        elif kind=='memory': settings='64 MiB'; work=f"{c['allocated_mib']} MiB allocated; {c['touched_pages']:,} pages touched"
        elif kind=='network': settings='256 KiB at 5 requests/s'; work=f"{c['network_requests']} responses, {c['network_bytes']/1048576:.2f} MiB; {rates['network_requests_per_second']:.3f} requests/s"
        else: settings='64 MiB; 256 KiB network; 16 KiB DB; 5 cycles/s'; work=f"{c['network_requests']} responses, {c['database_cycles']} DB cycles; {rates['network_requests_per_second']:.3f} requests/s and {rates['database_cycles_per_second']:.3f} cycles/s"
        lines.append(f"| {TITLES[kind]} | {settings} | {r['elapsed_seconds']:.3f} s | {work} | {c['errors']} |")
    lines+=['','A database cycle contains one successful write and one read. Network bytes above are payload bytes actually received by Data. Exact counters come from the saved run, not from counting graph peaks. The timed CPU counter counts individual calculation-loop batches; these are different from the 2,500-unit logical batches in CPU comparison.','','## Resource observations','','Peaks below are sampled within each saved baseline/work/cooldown window; CPU peaks are 30-second averages. Memory values are baseline median → sampled peak → final cooldown median.','','| Example / main service | Peak CPU cores | Working set (MiB) | Peak receive / transmit (MiB/s) |','|---|---:|---|---:|']
    for kind,entry in manifest['runs'].items():
        service='compute' if kind=='cpu' else 'data'; v=entry['resources'][service]
        lines.append(f"| {TITLES[kind]} / {service} | {v['peak_cpu_30s']:.3f} | {v['baseline_memory_mib']:.1f} → {v['peak_memory_mib']:.1f} → {v['cooldown_memory_mib']:.1f} | {v['peak_receive_30s']/1048576:.3f} / {v['peak_transmit_30s']/1048576:.3f} |")
    for kind,entry in manifest['runs'].items():
        run=entry['run']; resource=entry['resources']['compute' if kind=='cpu' else 'data']; c=run['counters']
        lines += ['', '## '+TITLES[kind], '', f"Run `{run['id']}` · [saved result](evidence/stage5/{kind}/run.json) · [CSV](evidence/stage5/{kind}/export.csv)", '']
        if kind=='cpu': lines += [f"Compute reached a sampled 30-second-average peak of **{resource['peak_cpu_30s']:.3f} cores** while completing {c['cpu_batches']:,} batches. Medium controls the busy/idle input; service and telemetry overhead are included in the resource graph. The cooldown makes the end of the activity visible."]
        elif kind=='memory': lines += [f"Data's working set rose from about **{resource['baseline_memory_mib']:.1f} MiB to {resource['peak_memory_mib']:.1f} MiB**, then reached about {resource['cooldown_memory_mib']:.1f} MiB in cooldown. The increase is larger than the 64 MiB buffer because a Python child and its libraries/telemetry also run. The buffer was released when that child exited."]
        elif kind=='network': lines += [f"Data received **{c['network_requests']} successful responses / {c['network_bytes']/1048576:.2f} MiB**. The paired lines show Data receiving payloads and Compute transmitting them. Interface traffic includes protocol/control traffic, so it should not be equated exactly with the payload counter."]
        else: lines += [f"The same run held **{c['allocated_mib']} MiB**, received **{c['network_requests']} payload responses**, and completed **{c['database_cycles']} database cycles** ({c['database_writes']} writes and {c['database_reads']} reads). The measured activity spans Data, Compute and MongoDB. Temporary workload documents were removed afterward; the run summary remains saved."]
        lines += ['',f'![{TITLES[kind]}: real measurements with labelled baseline, active work and cooldown](evidence/stage5/{kind}/resources.png)']
    trace=json.loads((OUT/'combined/trace.json').read_text())
    spans=[span for batch in trace.get('batches',trace.get('resourceSpans',[])) for group in batch.get('scopeSpans',[]) for span in group['spans']]
    lines += ['', '## Connected trace', '',f"The Combined trace `{manifest['runs']['combined']['run']['trace_id']}` has **{len(spans)} recorded spans** connected across Controller, Data and Compute, including MongoDB client calls. The short Start request is distinct from the longer background experiment. Selected successful I/O cycles keep the trace readable; all reported operations contribute to metrics.", '', '![Saved connected Combined trace](evidence/stage5/combined/trace.jpg)', '',
              '## What these examples establish', '',
              'All four runs completed, saved their results, reported zero operation errors, and left no active workload processes or temporary workload documents. The application images and tracing mode stayed constant. CPU, memory and network changes can be connected to the settings and actual work.', '',
              'These are synthetic examples on one laptop with one execution per scenario. Five-second sampling can miss short peaks; 30-second and two-minute dashboard windows smooth activity and can include preceding work. Working set and container traffic include overhead. No CPU-allocation speedup, scaling efficiency, or statistical conclusion is established by this set.', '',
              '## Reproduce or inspect', '',
              '[All run records, configuration, checks and image IDs](evidence/stage5/experiments.json) · [four-run CSV](evidence/stage5/experiment-history.csv) · [query responses and evidence index](evidence/stage5/README.md). Each scenario folder also contains its exact Prometheus queries/responses and standalone SVG plot.', '',
              'Use the [classroom guide](classroom-demo.md) to repeat the examples manually, or the evidence collector described in the evidence index. The formal repeated study and university submission documents remain future work.']
    (ROOT/'docs/experiment-results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    manifest=json.loads((OUT/'experiments.json').read_text())
    assert set(manifest['runs'])=={'cpu','memory','network','combined'} and all(manifest['checks'].values())
    for kind,entry in manifest['runs'].items(): resource_plot(kind,entry)
    diagrams()
    report(manifest)
    print('Rendered four plots, two guide diagrams, editable SVG/Mermaid sources, and the results report.')


if __name__=='__main__':
    main()
