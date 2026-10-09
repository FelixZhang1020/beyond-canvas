"""Shared read-only console routes; inspecting progress never initializes a driver."""
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

ASSET = Path(__file__).parents[1] / 'showpiece' / 'page' / 'floating-console.js'
PARTS = [{key: station[key] for key in ('id', 'name')}
         for station in json.loads((ASSET.parent / 'harness-roster.json').read_text())['stations']]


def finite_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def stage_events(updates):
    """Only operational metadata, never messages, partial text, paths or outputs."""
    events = []
    for data in updates:
        ledger = data.get('ledger') or {}
        events.append({'stage': str(data.get('stage', '')), 'status': str(data['status']),
                       'seconds': finite_number(ledger.get('wall_s'))})
    return events


def module_data(events):
    stages = {}
    for event in events:
        name = event['stage']
        if not name:
            continue
        row = stages.setdefault(name, {'name': name, 'status': '', 'seconds': None, 'events': 0})
        row['status'] = event['status']
        row['events'] += 1
        if event.get('seconds') is not None:
            row['seconds'] = event['seconds']
    return {'processes': list(stages.values()), 'events': events[-30:]}


def progress(server):
    rows = []
    classroom = getattr(server, 'classroom', None)
    for key, request in list(getattr(classroom, 'requests', {}).items()):
        with request.stream.cond:
            updates = [data for _, data in request.stream.updates if data.get('status')]
            last = updates[-1] if updates else {}
            percent = last.get('partial', {}).get('percent') if isinstance(last.get('partial'), dict) else None
            if not isinstance(percent, (int, float)) or isinstance(percent, bool) or not math.isfinite(percent) or not 0 <= percent <= 100:
                percent = None
            rows.append({'id': f'classroom:{key}', 'source': 'classroom',
                         'skill': request.skill, 'done': request.stream.finished,
                         'stage': last.get('stage', ''), 'status': last.get('status', 'submitted'),
                         'steps': len(updates), 'percent': percent,
                         'trail': [f"{d.get('stage', '')} · {d['status']}" for d in updates[-6:]],
                         **module_data(stage_events(updates)),
                         'parts': {'request': last.get('status', 'submitted'),
                                   'skills': request.skill,
                                   **({'evals': next(d['status'] for d in reversed(updates) if d.get('stage') == 'rubric')}
                                      if any(d.get('stage') == 'rubric' for d in updates) else {})}})
    holder = getattr(server, 'showpiece', None)
    driver = getattr(holder, '_driver', None) if holder else getattr(server, 'driver', None)
    for key, run in list(getattr(driver, 'runs', {}).items()):
        with run.cond:
            busy = run.busy or {}
            events = [{'stage': str(e.get('skill') or e.get('tool') or e.get('kind', '')),
                       'status': 'error' if e.get('ok') is False else str(e.get('kind', '')),
                       'seconds': finite_number(e.get('seconds'))} for e in run.events]
            if busy:
                events.append({'stage': str(busy.get('skill') or busy.get('phase', '')),
                               'status': 'running', 'seconds': None})
            rows.append({'id': f'showpiece:{key}', 'source': 'showpiece',
                         'skill': 'showpiece', 'done': run.done, 'stage': busy.get('skill', ''),
                         'status': 'done' if run.done else busy.get('phase', 'running'),
                         'steps': len(run.events), 'trail': [str(e.get('tool') or e.get('kind', '')) for e in run.events[-6:]],
                         **module_data(events)})
    # Keep active jobs visible even if many completed jobs follow them.
    return ([r for r in rows if not r['done']] + [r for r in rows if r['done']][-3:])[:12]


def serve_console(handler):
    path = urlsplit(handler.path).path
    if path == '/console.js':
        # As the page itself (page_transfer.py): compressed once and kept by a browser that has it. It used
        # to go whole under no-store, 29 KB on every visit over a link measured at 5 KB/s.
        from studio.server.page_transfer import send
        send(handler, ASSET, 'text/javascript; charset=utf-8')
        return True
    if path == '/api/console':
        from studio.making.media_services import snapshot
        from studio.showpiece.routes import machine_stats
        from studio.ops.spark_monitor import picture
        classroom = getattr(handler.server, 'classroom', None)
        body = json.dumps({'machine': machine_stats(), 'jobs': progress(handler.server), 'parts': PARTS,
                           # Work already on the machine, whoever asked for it: a class that has
                           # ended keeps no request here, but its clip keeps rendering.
                           'services': snapshot(getattr(classroom, 'deployment', None)),
                           # Everything on the chip, as the Spark's terminal monitor shows it.
                           'chip': picture(),
                           'sources': (['classroom'] if classroom is not None else []) +
                                      (['showpiece'] if hasattr(handler.server, 'showpiece') or hasattr(handler.server, 'driver') else [])}).encode()
        mime = 'application/json'
    else:
        return False
    handler.send_response(200)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.end_headers()
    handler.wfile.write(body)
    return True
