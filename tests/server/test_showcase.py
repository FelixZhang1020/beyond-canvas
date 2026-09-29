"""Read-only exhibit routes: portable assets, bounded streaming, private-file denial."""
import json
from pathlib import Path

import pytest

from studio.showcase_3d.serve import resolve_file


def test_exhibit_allowlist_and_portability(tmp_path):
    (tmp_path / 'index.html').write_text('exhibit')
    (tmp_path / 'originals').mkdir()
    (tmp_path / 'originals/model.obj').write_text('v 0 0 0')
    (tmp_path / 'lineage.json').write_text(json.dumps({'portrait/triposg': 'originals/model.obj'}))
    assert resolve_file('', tmp_path) == (tmp_path / 'index.html', False)
    assert resolve_file('download/portrait/triposg', tmp_path) == (tmp_path / 'originals/model.obj', True)
    for route in ['lineage.json', 'originals/model.obj', '.env', 'download/unknown', 'assets/%2e%2e/index.html']:
        with pytest.raises(KeyError):
            resolve_file(route, tmp_path)
    outside = tmp_path.parent / 'outside.glb'
    outside.write_bytes(b'private')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/link.glb').symlink_to(outside)
    with pytest.raises(KeyError):
        resolve_file('assets/link.glb', tmp_path)
    (tmp_path / 'lineage.json').write_text(json.dumps({'bad': str(outside)}))
    with pytest.raises(KeyError):
        resolve_file('download/bad', tmp_path)


class Recorder:
    """Stands in for the request handler: keeps the headers and the body a route would send."""
    def __init__(self):
        import io
        self.headers, self.wfile = {}, io.BytesIO()
    def send_response(self, status):
        self.status = status
    def send_header(self, name, value):
        self.headers[name] = value
    def end_headers(self):
        pass


def test_a_report_page_is_installed_the_same_way_and_walled_off_the_same(tmp_path, monkeypatch):
    """An overnight run measured the whole studio on every sample drawing, and its page shows the
    children's paintings beside what was made from them, so it lives in the gitignored .studio/ like the
    worlds page and goes out in the same sandbox."""
    from studio.showcase_3d import serve
    night = tmp_path / 'night.html'
    monkeypatch.setitem(serve.INSTALLED, 'night.html', night)
    with pytest.raises(KeyError):
        resolve_file('night.html', tmp_path)
    night.write_text('<p>the night</p>')
    assert resolve_file('night.html', tmp_path) == (night, False)
    page = Recorder()
    serve.send_file(page, 'night.html')
    policy = page.headers['Content-Security-Policy']
    assert page.status == 200 and page.wfile.getvalue() == b'<p>the night</p>'
    assert policy.startswith('sandbox allow-scripts') and 'allow-same-origin' not in policy


def test_the_worlds_page_is_installed_outside_git_and_walled_off(tmp_path, monkeypatch):
    """The walkable worlds embed the sample paintings, so the page lives in the gitignored .studio/
    and is copied in by hand; a studio without it answers 404. The page is model-written, so it is sent
    in a sandbox: an opaque origin whose requests are refused, so it cannot call the classroom's routes."""
    from studio.showcase_3d import serve
    worlds = tmp_path / 'worlds.html'
    monkeypatch.setitem(serve.INSTALLED, 'worlds.html', worlds)
    with pytest.raises(KeyError):
        resolve_file('worlds.html', tmp_path)
    worlds.write_text('<p>worlds</p>')
    assert resolve_file('worlds.html', tmp_path) == (worlds, False)
    page = Recorder()
    serve.send_file(page, 'worlds.html')
    policy = page.headers['Content-Security-Policy']
    assert page.status == 200 and page.wfile.getvalue() == b'<p>worlds</p>'
    assert policy.startswith('sandbox allow-scripts') and 'allow-same-origin' not in policy
    assert "default-src 'none'" in policy and 'connect-src data: blob:' in policy
    ordinary = Recorder()
    serve.send_file(ordinary, 'figure.html')
    assert 'Content-Security-Policy' not in ordinary.headers


class Browser:
    """A browser asking for one viewer file: what it sends, and what comes back."""
    def __init__(self, **asked):
        import io
        self.headers, self.sent, self.wfile = dict(asked), {}, io.BytesIO()
    def send_response(self, status):
        self.status = status
    def send_header(self, name, value):
        self.sent[name] = value
    def end_headers(self):
        pass


def test_the_3d_viewers_code_is_sent_compressed_once_and_then_kept_by_the_browser():
    """Operator: a figure took so long to open that its window said it could not be shown.
    three.js alone is 2 MB, and it went out whole, uncompressed and untagged, every time."""
    import gzip
    from studio.showcase_3d import serve
    first = Browser(**{"Accept-Encoding": "gzip, br"})
    serve.send_file(first, "vendor/three.core.js")
    body = first.wfile.getvalue()
    assert first.status == 200 and first.sent["Content-Encoding"] == "gzip" and "ETag" in first.sent
    assert len(body) < 0.4 * (serve.ROOT / "vendor" / "three.core.js").stat().st_size
    assert gzip.decompress(body) == (serve.ROOT / "vendor" / "three.core.js").read_bytes()
    assert first.sent["X-Content-Type-Options"] == "nosniff"
    again = Browser(**{"Accept-Encoding": "gzip", "If-None-Match": first.sent["ETag"]})
    serve.send_file(again, "vendor/three.core.js")
    assert again.status == 304 and again.wfile.getvalue() == b"", "a browser that has it is told to keep it"
    plain = Browser(**{"If-None-Match": first.sent["ETag"]})
    serve.send_file(plain, "vendor/three.core.js")
    assert plain.status == 200 and "Content-Encoding" not in plain.sent, \
        "the gzipped copy's tag does not stand for the plain one (code review)"
    assert plain.wfile.getvalue() == (serve.ROOT / "vendor" / "three.core.js").read_bytes()
