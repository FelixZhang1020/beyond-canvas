"""Check maintained text documentation and HTML reports, including new files."""
from collections import Counter
from pathlib import Path
import re
import subprocess

import pytest

from studio.server.ports import off_convention

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {'.md', '.mdx', '.rst', '.txt', '.adoc', '.org'}
# Match port syntax, not years, token budgets, UUIDs, or arbitrary model numbers.
PORT_REFERENCE = re.compile(
    r'(?:https?|wss?)://(?:\[[^\]]+\]|[\w.-]+):(?P<url>\d+)'
    r'|--(?:server-)?port(?:\s+|=)[\"\x27]?(?P<flag>\d+)'
    r'|\bhttp\.server\s+(?P<http>\d+)'
    r'|\b(?:[A-Z_]*_)?PORT\s*=\s*[\"\x27]?(?P<env>\d+)'
    r'|\bport\s*(?:[=:（(]\s*)?(?P<prose>\d{2,5})\b'
    r'|端口\s*(?:为|是|[=:：])?\s*[`（(]?(?P<chinese>\d{2,5})\b'
    r'|\b(?P<suffix>\d{2,5})\s*端口'
)

# Exact existing occurrences only. These are not permitted startup examples.
# Each is a historical record of its day, not a way to start anything.
RETAINED = {
    ('docs/measured/model-deployment-readiness.md', 1234): 1,
    ('docs/measured/four-model-comparison.md', 7135): 1,
    ('studio/showcase_3d/records/3d-model-selection.md', 7135): 1,
    ('studio/showcase_3d/records/measured/four-model-comparison.md', 7135): 1,
}


def document_paths():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, capture_output=True, check=True)
    paths = {Path(name.decode('utf-8')) for name in result.stdout.split(b'\0') if name}
    return sorted(path for path in paths if 'vendor' not in path.parts and (
        path.suffix.lower() in TEXT_SUFFIXES or
        (path.suffix.lower() in {'.html', '.htm'} and path.parts[0] in {'docs', 'design'})
    ))


def violations(text):
    return [int(match.group(match.lastgroup)) for match in PORT_REFERENCE.finditer(text)
            if off_convention(int(match.group(match.lastgroup))) is not None]


def test_all_document_port_references_are_valid_or_explicitly_retained():
    # The published copy leaves some working documents out; an exception for a file that is not
    # here is not stale, only absent.
    retained = Counter({key: count for key, count in RETAINED.items() if (ROOT / key[0]).is_file()})
    found = Counter()
    for path in document_paths():
        found.update((path.as_posix(), port) for port in violations(
            (ROOT / path).read_text(encoding='utf-8')))
    assert found == retained, (
        f'New or undocumented noncompliant port references: {dict(found - retained)}; '
        f'stale exceptions to remove: {dict(retained - found)}'
    )


@pytest.mark.parametrize('text', [
    'http://127.0.0.1:7137/showcase/3d/',
    '<a href="http://localhost:7137/">Preview</a>',
    'python -m studio.serve --port 7137',
    'python -m studio.serve --port=7137',
    'python -m http.server 7137',
    'PORT=7137 npm run dev',
    'APP_PORT="7137" npm run dev',
    'Listen on port 7137',
    '端口为 7137',
    '默认监听端口为 7137',
    '7137 端口',
])
def test_detects_bad_examples_and_accepts_good_controls(text):
    assert violations(text) == [7137]
    assert violations(text.replace('7137', '7070')) == []


def test_checks_range_and_preserves_test_ephemeral_exception():
    assert violations('--port 7800') == [7800]
    assert violations('--port 0') == []
    assert violations('2026-09-07; 8192 tokens; model 1024') == []


def test_inventory_includes_previously_missed_documentation():
    paths = document_paths()
    for path in ('README.md', 'docs/specs/3d-model-selection.md', 'studio/showcase_3d/README.md',
                 'docs/specs/studio-page-contract.md',
                 'docs/guides/where-models-sit.html'):
        assert Path(path) in paths
