"""Read-only readiness checks. Never submits inference or exposes upstream errors."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import httpx
from studio.core.slots import load_profile, SlotConfig
from studio.providers import is_disabled_stepfun_image_model, key_for


def check_slot(config):
    provider, model, opts = config.provider, config.model, config.options
    from studio.core.deployments import component_identity
    result = {'slot': config.slot, 'model': model, 'status': 'unknown', **component_identity(config)}
    if is_disabled_stepfun_image_model(model):
        return dict(result, status='unavailable', reason='retired')
    key = key_for(provider)
    if provider == 'cloudmesh' and model == 'pixal':
        if not (os.environ.get('FALAI_API_KEY') or os.environ.get('FAL_KEY')):
            return dict(result, status='unavailable', reason='credentials')
        return dict(result, reason='unsupported')
    if key and not os.environ.get(key):
        return dict(result, status='unavailable', reason='credentials')
    headers = {'Authorization': 'Bearer ' + os.environ[key]} if key else {}
    catalog = False
    if provider == 'stepfun':
        from studio.providers.stepfun import API_URL
        url = opts.get('base_url', API_URL).rstrip('/') + '/models'
        catalog = True
    elif provider == 'openrouter':
        url = 'https://openrouter.ai/api/v1/models/user'
        catalog = True
    elif provider in ('replicate', 'cloudmesh'):
        model_path = 'fishwowater/trellis2' if provider == 'cloudmesh' else model
        url = 'https://api.replicate.com/v1/models/' + model_path
        from studio.providers.cloudmesh import TRELLIS_VERSION
        version = TRELLIS_VERSION if provider == 'cloudmesh' else None if opts.get('official') is True else opts.get('version')
        if version:
            url += '/versions/' + version
    elif provider in ('localimage', 'remotevoice', 'localmesh', 'localvideo'):
        try:
            with httpx.Client(timeout=6, trust_env=False) as client:
                response = client.get(opts['base_url'].rstrip('/') + '/v1/models')
                response.raise_for_status()
                body = response.json()
                found = next((item for item in body.get('data', []) if isinstance(item, dict) and item.get('id') == model), None)
                if found is None:
                    return dict(result, reason='model_unlisted')
                state = found.get('status', found.get('state', 'unknown'))
                # Legacy TRELLIS/Wan directories expose only IDs once their service is up.
                if state == 'unknown' and provider in ('localvideo', 'localmesh') and model != 'pixal':
                    return dict(result, status='ready', reason='busy' if body.get('busy') else 'health')
                if found.get('ready') is False:
                    return dict(result, status='unavailable', reason='connection')
                if state in ('ready', 'standby', 'loaded', 'busy', 'running'):
                    return dict(result, status='ready', reason='busy' if body.get('busy') or state in ('busy','running') else 'standby' if state == 'standby' else 'health')
                return dict(result, status='unavailable' if state in ('unavailable','missing','failed') else 'unknown', reason='connection')
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return dict(result, status='unavailable', reason='connection')
    elif provider == 'whispercpp' and opts.get('base_url'):
        # Probed on '/' rather than through modelusage.probe, which tries
        # /v1/models and /health: whisper.cpp v1.7.4 — the build on the 4090 —
        # serves neither, only /inference and /load, so a working server read as
        # unavailable. Both builds answer on '/', and both bind the port only
        # once the model is loaded, so answering at all is the readiness signal.
        try:
            with httpx.Client(timeout=5, trust_env=False) as client:
                up = client.get(opts['base_url'].rstrip('/') + '/').status_code == 200
        except httpx.HTTPError:
            up = False
        return dict(result, status='ready' if up else 'unavailable', reason='health' if up else 'connection')
    elif provider in ('llamacpp', 'localvideo', 'localmesh', 'hybridmesh', 'safetyreader') and opts.get('base_url'):
        from studio.ops.modelusage import probe
        up = probe(opts['base_url'], timeout=5)
        return dict(result, status='ready' if up else 'unavailable', reason='health' if up else 'connection')
    else:
        return dict(result, reason='unsupported')
    try:
        with httpx.Client(timeout=6, follow_redirects=False, trust_env=False) as client:
            response = client.get(url, headers=headers)
            if response.status_code != 200:
                return dict(result, status='unavailable', reason='credentials' if response.status_code in (401, 403) else 'connection')
            body = response.json()
            if catalog and model not in [item.get('id') for item in body.get('data', []) if isinstance(item, dict)]:
                return dict(result, status='unknown', reason='model_unlisted')
            if provider == 'replicate' and opts.get('official') is True:
                if f"{body.get('owner')}/{body.get('name')}" != model:
                    return dict(result, reason='model_unlisted')
            if not catalog and version and body.get('id') != version:
                return dict(result, reason='model_unlisted')
            if not catalog and not (body.get('name') or body.get('id')):
                return dict(result, reason='unsupported')
            return dict(result, status='ready', reason='catalog')
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return dict(result, status='unavailable', reason='connection')


def check_deployment(classroom, name):
    if name == 'stepfun':  # the only deployment
        # speech.in comes from the profile like every other slot,
        # so check_profile already carries it. This used to append a second one
        # built from the running classroom's ears and labelled whisper.cpp on the
        # Mac — which described the deployment being checked only by accident, and
        # once hearing could be bought it marked every deployment unavailable by
        # probing StepFun's HTTPS endpoint as though it were a local whisper. That
        # refused all three switches while all three services were healthy (there
        # used to be three deployments).
        report = check_profile(name)
        with classroom.lock:
            if not hasattr(classroom, '_component_checks'):
                classroom._component_checks = {}
            classroom._component_checks[name] = (time.monotonic(), report)
        return report
    if name != 'current':
        raise ValueError('Unknown deployment')
    with classroom.lock:
        runtime = classroom._runtime() if name == classroom.deployment else classroom._deployments.get(name)
        profile = runtime.profile if runtime else 'stepfun' if name == 'stepfun' else None
    if profile is None:
        raise ValueError('Deployment is not configured')
    slots = load_profile(profile)
    # Check the classroom routes, not unused experiment slots in inherited profiles.
    names = ('vlm.studio', 'vlm.director', 'video.animation', 'mesh.portrait', 'tts.studio')
    configs = [slots[n] for n in names if n in slots and (n != 'tts.studio' or name == 'stepfun' or
               (runtime and runtime.voice is not None and not getattr(runtime.voice, 'local', False)))]
    if runtime:
        configs.extend(slots[n] for n in runtime.clients if n in slots and n not in names)
    # Hearing is a profile slot, so check the one this deployment
    # declares rather than the client the running classroom happens to hold —
    # they differ whenever a teacher checks an option they have not selected.
    if 'speech.in' in slots:
        configs.append(slots['speech.in'])
    elif getattr(classroom.ears, 'base_url', None):
        configs.append(SlotConfig('speech.in', 'whispercpp', 'Whisper', {'base_url': classroom.ears.base_url}))
    with ThreadPoolExecutor(max_workers=6) as pool:
        components = list(pool.map(check_slot, configs))
    # Profiles do not describe runtime voice overrides. Never claim these were checked.
    if runtime and runtime.voice is not None and getattr(runtime.voice, 'local', False):
        components = [c for c in components if c['slot'] != 'tts.studio']
        components.append({'slot': 'tts.studio', 'model': str(getattr(runtime.voice, 'model', 'local')), 'status': 'ready' if getattr(getattr(runtime.voice, 'runtime', None), 'model', None) is not None else 'unknown', 'reason': 'loaded'})
    return {'target': name, 'ready': bool(components) and all(c['status'] == 'ready' for c in components), 'components': components}


def check_profile(name):
    from studio.core.deployments import DEPLOYMENTS, ROLE_SLOTS
    if name not in DEPLOYMENTS: raise ValueError('Unknown deployment')
    slots = load_profile(name)
    # No image.edit: the still picture was retired, so its model is not checked.
    required = ROLE_SLOTS + ('video.animation', 'mesh.portrait', 'tts.studio', 'speech.in')
    # What the class gained since the still picture was retired, each of which it runs without: shown on the
    # board, never a reason not to start. Pixal3D's mesh.alternative was the one optional slot until it was archived.
    optional = ('vlm.front', 'safety.reader', 'vlm.figure', 'vlm.figure.look', 'image.book', 'tts.child', 'video.online')
    names = tuple(n for n in required if n in slots) + tuple(n for n in optional if n in slots)
    configs = [slots[n] for n in names]
    missing = [n for n in required if n not in slots]
    with ThreadPoolExecutor(max_workers=6) as pool:
        components = list(pool.map(check_slot, configs))
    for c, config in zip(components, configs):
        c['optional'] = config.slot in optional
        if config.slot.startswith('mesh.'):
            c['slot'] = 'mesh.portrait.' + config.model
    components.extend({'slot': n, 'model': '', 'status': 'unavailable', 'reason': 'configuration',
                       'optional': False} for n in missing)
    return {'target': name, 'ready': bool(components) and all(c['status'] == 'ready' for c in components if not c['optional']), 'components': components}
