"""Bounded image editing on the project's GPU machine: the DGX Spark for StepFun First, the 4090 for the older development profiles.

Two shapes: one picture and one instruction (/v1/image, the retired still pose and the older profiles), or
several pictures in one job (/v1/pictures, a storybook's picture-book pages), which the
Spark's picture service draws with one load of the model.
"""
import base64
import json
import time
from studio.providers.gpu_job import stream_job
import httpx
from studio.providers.localvideo import LocalVideoClient
from studio.providers.media import MediaResult
from studio.core.errors import ModelRefused, ModelUnavailable


MOST_PICTURES = 8   # page 1 in four styles, or up to seven pages in one (media_server.MOST_PICTURES)


class LocalImageClient(LocalVideoClient):
    def make(self, inputs):
        if 'pictures' in inputs:
            return self._pictures(inputs['pictures'])
        image, instruction = inputs.get('image'), inputs.get('instruction')
        if not isinstance(image, str) or not image.startswith('data:image/') or len(image) > 12 * 1024 * 1024:
            raise ModelRefused('Image worker requires a bounded embedded image')
        if not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 4000:
            raise ModelRefused('Image worker requires a bounded instruction')
        started = time.monotonic()
        try:
            with stream_job(self._client, self.base_url, '/v1/image',
                    body={'model': self.model, 'image': image, 'instruction': instruction},
                    timeout=min(900, max(1, float(self.options.get('timeout_s', 600))))) as response:
                if response.status_code in (408,409,429,500,502,503,504):
                    raise ModelUnavailable('The picture worker is busy or unavailable')
                if response.status_code != 200 or response.headers.get('content-type','').split(';')[0] not in ('image/png','image/jpeg','image/webp'):
                    raise ModelRefused('The picture worker rejected the request')
                content=bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(content)+len(chunk)>12*1024*1024:
                        raise ModelRefused('Image response exceeds byte limit')
                    content.extend(chunk)
        except httpx.RequestError:
            raise ModelUnavailable('The picture worker did not answer') from None
        if not content: raise ModelRefused('Empty image response')
        return MediaResult([],content=bytes(content),provider='localimage',model=self.model,latency_s=time.monotonic()-started)

    def _pictures(self, pictures):
        if not isinstance(pictures, list) or not 1 <= len(pictures) <= MOST_PICTURES or any(
                not isinstance(one, dict) or not str(one.get('image', '')).startswith('data:image/')
                or not 1 <= len(str(one.get('instruction', '')).strip()) <= 4000 for one in pictures):
            raise ModelRefused('Picture worker requires one to eight bounded pictures with instructions')
        started = time.monotonic()
        try:
            with stream_job(self._client, self.base_url, '/v1/pictures', body={'model': self.model, 'pictures': pictures},
                            timeout=min(900, max(1, float(self.options.get('timeout_s', 600))))) as response:
                if response.status_code in (408, 409, 429, 500, 502, 503, 504):
                    raise ModelUnavailable('The picture worker is busy or unavailable')
                if response.status_code != 200 or response.headers.get('content-type', '').split(';')[0] != 'application/json':
                    raise ModelRefused('The picture worker rejected the request')
                content = bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(content) + len(chunk) > 16 * 1024 * 1024:
                        raise ModelRefused('Picture response exceeds byte limit')
                    content.extend(chunk)
        except httpx.RequestError:
            raise ModelUnavailable('The picture worker did not answer') from None
        try:
            drawn = json.loads(bytes(content))['pictures']
            if len(drawn) != len(pictures) or any(not base64.b64decode(p, validate=True).startswith(b'\xff\xd8\xff') for p in drawn):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ModelRefused('The picture worker returned unreadable pictures') from None
        return MediaResult([], payload={'pictures': ['data:image/jpeg;base64,' + p for p in drawn]},
                           provider='localimage', model=self.model, latency_s=time.monotonic() - started)
