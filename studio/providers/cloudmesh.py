"""Selected cloud image-to-3D providers; one explicit choice, no paid fallback."""
from dataclasses import replace
from urllib.parse import urlsplit
import os

import httpx

from studio.making import glb
from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.replicate import ReplicateClient
from studio.providers.fal import FalClient

TRELLIS_VERSION = '52e1ad6852599ea10ce8e257635a3c11485cba51c181ea5173e34d9b2955b226'


class CloudMeshClient:
    def __init__(self, model, options=None, client=None):
        self.model, self.options = model, dict(options or {})
        self._client = client or httpx.Client(trust_env=False, timeout=120, follow_redirects=False)

    def make(self, inputs):
        choice = inputs.get('model_choice', 'trellis2')
        image = inputs.get('image')
        if choice not in ('trellis2', 'pixal') or not isinstance(image, str) or not image.startswith('data:image/') or len(image) > 8 * 1024 * 1024:
            raise ModelRefused('Invalid image or model choice')
        try:
            if choice == 'trellis2':
                provider = ReplicateClient('fishwowater/trellis2', {'version': TRELLIS_VERSION, 'timeout_s': 600}, client=self._client)
                result = provider.make(dict(image=image, seed=42, randomize_seed=False, preprocess_image=True,
                                            return_no_background=False, generate_model=True, generate_video=False,
                                            pipeline_type='1024_cascade', texture_size=1024, decimation_target=100000))
                url = (result.payload.get('output') or {}).get('model_file')
            else:
                provider = FalClient('fal-ai/pixal3d', {'timeout_s': 600, 'price_usd': 0.30},
                                     api_key=os.environ.get('FALAI_API_KEY') or os.environ.get('FAL_KEY', ''), client=self._client)
                result = provider.make(dict(image_url=image, seed=42, resolution=1024, texture_size=1024, decimation_target=100000))
                url = (result.payload.get('model_glb') or {}).get('url')
            content = self._download(url)
            glb.validate(content)
        except ModelUnavailable:
            raise ModelUnavailable('Cloud 3D is busy or timed out; the remote job may still finish. No backup was submitted.') from None
        except (ModelRefused, ValueError, TypeError, AttributeError):
            raise ModelRefused('Cloud 3D could not provide a displayable model. Check configuration or choose the backup explicitly.') from None
        return replace(result, content=content, urls=[], payload={}, model=choice)

    def _download(self, url):
        for _ in range(4):
            parsed = urlsplit(url or '')
            host = parsed.hostname or ''
            if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not any(host == domain or host.endswith('.' + domain) for domain in ('replicate.delivery', 'fal.media')):
                raise ModelRefused('Untrusted model download')
            try:
                with self._client.stream('GET', url, timeout=120) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = response.headers.get('location'); continue
                    if response.status_code != 200:
                        raise ModelUnavailable('Model download unavailable')
                    if int(response.headers.get('content-length', 0)) > glb.MAX_BYTES:
                        raise ModelRefused('Model exceeds display budget')
                    content = bytearray()
                    for chunk in response.iter_bytes(65536):
                        if len(content) + len(chunk) > glb.MAX_BYTES:
                            raise ModelRefused('Model exceeds display budget')
                        content.extend(chunk)
                    return bytes(content)
            except httpx.RequestError:
                raise ModelUnavailable('Model download interrupted') from None
        raise ModelRefused('Too many model redirects')
