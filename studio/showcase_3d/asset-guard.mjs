const maxBytes = 16 * 1024 * 1024;
export async function boundedAsset(item, signal) {
  if (!/^assets\/(portrait|geometry|fruit)\/(trellis2|pixal|hunyuan21|triposg)\.glb$/.test(item.asset) || item.bytes > maxBytes) throw Error('模型超出显示预算');
  const response = await fetch(item.asset, {signal});
  if (!response.ok) throw Error('模型文件读取失败');
  if (Number(response.headers.get('content-length')) > maxBytes) throw Error('模型文件过大');
  const reader = response.body.getReader(), chunks = []; let length = 0;
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      length += value.byteLength;
      if (length > maxBytes) throw Error('模型文件过大');
      chunks.push(value);
    }
  } finally {await reader.cancel().catch(() => {});}
  if (length !== item.bytes) throw Error('文件大小与记录不符');
  const data = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) {data.set(chunk, offset); offset += chunk.length;}
  return checkedBuffer(data.buffer, item);
}

export async function checkedBuffer(buffer, item = {}) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength > maxBytes) throw Error('模型超出显示预算');
  const data = new Uint8Array(buffer), length = data.length;
  const h = new DataView(data.buffer);
  if (length < 20 || h.getUint32(0, true) !== 0x46546c67 || h.getUint32(4, true) !== 2 || h.getUint32(8, true) !== length) throw Error('GLB 格式无效');
  const jsonSize = h.getUint32(12, true);
  if (jsonSize > 2 * 1024 * 1024 || 20 + jsonSize > length || h.getUint32(16, true) !== 0x4e4f534a) throw Error('GLB 描述无效');
  const header = JSON.parse(new TextDecoder().decode(data.subarray(20, 20 + jsonSize)));
  if ((header.buffers || []).some(b => b.uri) || (header.images || []).some(i => i.uri)) throw Error('仅支持自包含的显示文件');
  const faces = (header.meshes || []).flatMap(m => m.primitives).reduce((sum, p) => {
    if (p.mode !== undefined && p.mode !== 4) throw Error('仅支持三角面模型');
    return sum + (header.accessors[p.indices ?? p.attributes.POSITION]?.count || 0) / 3;
  }, 0);
  if (faces > 350000 || !faces) throw Error('模型三角面超出显示预算');
  if (crypto.subtle && item.sha256) {
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', data))].map(b => b.toString(16).padStart(2, '0')).join('');
    if (hash !== item.sha256) throw Error('模型校验不一致');
  }
  return data.buffer;
}

