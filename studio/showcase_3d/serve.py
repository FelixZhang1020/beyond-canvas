"""Serve the portable exhibit without model workers or external services."""
import argparse
import json
import mimetypes
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
PUBLIC = {'classroom-ui.js', 'classroom.html', 'index.html', 'style.css', 'viewer.js', 'asset-guard.mjs', 'solid-scene.mjs', 'manifest.json',
          'figure.html', 'figure.js'}
# The walkable worlds of the sample paintings, for the hackathon showcase only. The page embeds the
# paintings, so it lives in the gitignored .studio/ and is copied in by hand; it is model-written, so it is
# sent in a sandbox: an opaque origin whose requests are refused, so it cannot reach the classroom's routes.
# Pages installed by hand rather than shipped, because both embed the sample paintings: the walkable
# worlds, and the report of an overnight run, which shows every drawing beside what was made from
# it. They live in the gitignored .studio/ and go out in the sandbox below.
INSTALLED = {name: Path('.studio') / 'showcase' / name for name in ('worlds.html', 'night.html')}
SANDBOX = ("sandbox allow-scripts allow-pointer-lock; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' "
           "blob:; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; font-src data:; "
           "connect-src data: blob:; worker-src blob:")


def resolve_file(route, root=ROOT):
    route = unquote(route) or 'index.html'
    if route in INSTALLED:
        page = INSTALLED[route]
        if not page.is_file():
            raise KeyError(f'{route} is not installed')
        return page, False
    download = route.startswith('download/')
    if download:
        relative = json.loads((root / 'lineage.json').read_text()).get(route[9:])
        if not relative:
            raise KeyError('Unknown original model')
    else:
        relative = route
        if route not in PUBLIC and not (
            route.startswith(('assets/', 'inputs/', 'vendor/'))
            and Path(route).suffix in {'.glb', '.png', '.js'}
        ):
            raise KeyError('Not an exhibit asset')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise KeyError('Exhibit asset unavailable')
    if any(part in {'.', '..'} for part in route.split('/')):
        raise KeyError('Invalid exhibit path')
    return path, download


# Text the browser runs or reads, sent gzipped. The rest (models, pictures) is already compressed.
PACKED = {'.js', '.mjs', '.html', '.css', '.json'}


def send_file(handler, route):
    path, download = resolve_file(route)
    if download:
        with path.open('rb') as source:
            handler.send_response(200)
            handler.send_header('Content-Type', 'application/octet-stream')
            handler.send_header('Content-Length', str(path.stat().st_size))
            handler.send_header('Cache-Control', 'no-cache')
            handler.send_header('X-Content-Type-Options', 'nosniff')
            handler.send_header('Referrer-Policy', 'no-referrer')
            handler.send_header('Content-Disposition', f'attachment; filename="{path.parent.parent.name}-{path.parent.name}-{path.name}"')
            handler.end_headers()
            shutil.copyfileobj(source, handler.wfile, length=256 * 1024)
        return
    # Kept by the browser and gzipped, as the class page is (page_transfer.py). Operator: the
    # figure took so long to open that its window said it could not be shown; three.js alone is 2 MB, and it
    # went out whole, uncompressed and with no tag, every time a figure or 3D model was opened.
    from studio.server.page_transfer import packed_tag, prepare
    raw, packed, tag = prepare(path, compress=path.suffix in PACKED)
    zipped = packed is not None and 'gzip' in (handler.headers.get('Accept-Encoding') or '')
    body, tag = (packed, packed_tag(tag)) if zipped else (raw, tag)
    common = (('ETag', tag), ('Cache-Control', 'no-cache'), ('Vary', 'Accept-Encoding'),
              ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'))
    if handler.headers.get('If-None-Match') == tag:
        handler.send_response(304)
        for name, value in common:
            handler.send_header(name, value)
        handler.end_headers()
        return
    handler.send_response(200)
    handler.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
    handler.send_header('Content-Length', str(len(body)))
    for name, value in common:
        handler.send_header(name, value)
    if zipped:
        handler.send_header('Content-Encoding', 'gzip')
    if path in INSTALLED.values():
        handler.send_header('Content-Security-Policy', SANDBOX)
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host', '').split(':')[0] not in {'localhost', '127.0.0.1'}:
            self.send_error(403)
            return
        from studio.server.console_panel import serve_console
        if serve_console(self):
            return
        route = urlsplit(self.path).path.lstrip('/')
        if route == 'showcase/3d':
            self.send_response(302)
            self.send_header('Location', '/showcase/3d/')
            self.end_headers()
            return
        if route.startswith('showcase/3d/'):
            route = route[len('showcase/3d/'):]
        try:
            send_file(self, route)
        except (KeyError, FileNotFoundError):
            self.send_error(404)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7080)
    args = parser.parse_args()
    print(f'Exhibit: http://127.0.0.1:{args.port}/showcase/3d/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
