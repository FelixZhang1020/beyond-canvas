// A continuous textured sheet: move the drawing locally without cutting holes
// or inventing a background. Shared mesh vertices keep neighbouring strokes
// joined. Rendering runs on the viewing device, not the studio model's GPU.
window.Studio = window.Studio || {};
Studio.motion = {
  MAX_EDGE: 1280, FPS: 30,
  active: null,
  ease: function (t) { return t * t * (3 - 2 * t); },
  progress: function (layer, t) {
    return this.ease(Math.max(0, Math.min(1,
      (t - layer.start_s) / Math.max(.001, layer.end_s - layer.start_s))));
  },
  // Every move settles back onto the original drawing, including old plans
  // whose enter/exit previously erased the artwork. No opacity animation.
  at: function (layer, t) {
    const p = this.progress(layer, t), d = layer.distance || [0, 0];
    const pulse = Math.pow(Math.sin(Math.PI * p), 2), cycle = Math.sin(2 * Math.PI * p);
    const limitX = Math.min(.018, layer.box[2] * .08);
    const limitY = Math.min(.018, layer.box[3] * .08);
    const clamp = function (v, limit) { return Math.max(-limit, Math.min(limit, v)); };
    let dx = 0, dy = 0, scale = 1;
    switch (layer.move) {
      case 'sway': dx = clamp(d[0] || .012, limitX) * cycle; break;
      case 'breathe': scale = 1 + .045 * pulse; dy = -limitY * .12 * pulse; break;
      case 'grow': scale = 1 + .08 * pulse; break;
      case 'rise': dx = clamp(d[0], limitX) * pulse; dy = -clamp(Math.abs(d[1] || .012), limitY) * pulse; break;
      default: dx = clamp(d[0] || (d[1] ? 0 : .012), limitX) * pulse;
        dy = clamp(d[1], limitY) * pulse;
    }
    return { dx: dx, dy: dy, scale: scale, alpha: 1 };
  },
  dimensions: function (w, h, edge) {
    const ratio = Math.min(1, edge / Math.max(w, h));
    return [Math.max(1, Math.round(w * ratio)), Math.max(1, Math.round(h * ratio))];
  },
  valid: function (plan) {
    if (!plan || !Number.isFinite(plan.duration_s) || plan.duration_s < 2 || plan.duration_s > 10
      || !Array.isArray(plan.layers) || !plan.layers.length || plan.layers.length > 3) return false;
    return plan.layers.every(function (l) {
      return l && Array.isArray(l.box) && l.box.length === 4 && l.box.every(Number.isFinite)
        && l.box[0] >= 0 && l.box[1] >= 0 && l.box[2] > 0 && l.box[3] > 0
        && l.box[0] + l.box[2] <= 1.001 && l.box[1] + l.box[3] <= 1.001
        && ['drift', 'sway', 'rise', 'grow', 'breathe', 'enter', 'exit'].includes(l.move)
        && Number.isFinite(l.start_s) && Number.isFinite(l.end_s)
        && l.start_s >= 0 && l.end_s > l.start_s && l.end_s <= plan.duration_s
        && (l.distance === undefined || (Array.isArray(l.distance) && l.distance.length === 2
          && l.distance.every(function (n) { return Number.isFinite(n) && Math.abs(n) <= 1; })));
    });
  },
  // Bake spatial influences once. A squared sine has zero slope at its boundary;
  // unlike moving a rectangle, it cannot expose a seam against its neighbour.
  mesh: function (w, h, layers, resolution) {
    const cols = Math.max(2, Math.round(resolution * w / Math.max(w, h)));
    const rows = Math.max(2, Math.round(resolution * h / Math.max(w, h)));
    const points = [], indices = [];
    for (let y = 0; y <= rows; y++) for (let x = 0; x <= cols; x++) {
      const u = x / cols, v = y / rows;
      const weights = layers.map(function (l) {
        const a = (u - l.box[0]) / l.box[2], b = (v - l.box[1]) / l.box[3];
        if (x === 0 || y === 0 || x === cols || y === rows || a <= 0 || a >= 1 || b <= 0 || b >= 1) return 0;
        return Math.pow(Math.sin(Math.PI * a) * Math.sin(Math.PI * b), 2);
      });
      points.push({ u: u, v: v, weights: weights });
    }
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const a = y * (cols + 1) + x, b = a + 1, c = a + cols + 1, d = c + 1;
      indices.push(a, b, c, b, d, c);
    }
    return { points: points, indices: new Uint16Array(indices), vertices: new Float32Array(points.length * 4) };
  },
  deform: function (mesh, layers, t) {
    const moves = layers.map(l => this.at(l, t));
    mesh.points.forEach(function (point, i) {
      let dx = 0, dy = 0, weight = 0;
      point.weights.forEach(function (a, j) {
        const m = moves[j], b = layers[j].box;
        dx += a * (m.dx + (point.u - b[0] - b[2] / 2) * (m.scale - 1));
        dy += a * (m.dy + (point.v - b[1] - b[3] / 2) * (m.scale - 1));
        weight += a;
      });
      const k = Math.max(1, weight);
      mesh.vertices.set([point.u + dx / k, point.v + dy / k, point.u, point.v], i * 4);
    });
    return mesh.vertices;
  },
  // One texture, one dynamic vertex buffer, one draw call. No full-frame CPU
  // readback, per-frame canvas allocation, server rendering or video model.
  gpu: function (canvas, img, plan) {
    const gl = canvas.getContext('webgl', { alpha: false, antialias: false, preserveDrawingBuffer: true });
    if (!gl) return null;
    const shaders = [], program = gl.createProgram();
    function shader(type, code) {
      const s = gl.createShader(type); shaders.push(s); gl.shaderSource(s, code); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('motion shader');
      gl.attachShader(program, s);
    }
    let buffer, index, texture;
    function dispose() {
      if (texture) gl.deleteTexture(texture);
      if (buffer) gl.deleteBuffer(buffer);
      if (index) gl.deleteBuffer(index);
      gl.deleteProgram(program); shaders.forEach(s => gl.deleteShader(s));
      const release = gl.getExtension('WEBGL_lose_context'); if (release) release.loseContext();
    }
    try {
      shader(gl.VERTEX_SHADER, 'attribute vec4 point; varying vec2 uv; void main(){uv=point.zw; gl_Position=vec4(point.x*2.0-1.0,1.0-point.y*2.0,0.0,1.0);}');
      shader(gl.FRAGMENT_SHADER, 'precision mediump float; varying vec2 uv; uniform sampler2D art; void main(){gl_FragColor=texture2D(art,uv);}');
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('motion program');
      gl.useProgram(program);
      const mesh = this.mesh(canvas.width, canvas.height, plan.layers, 48);
      buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, mesh.vertices.byteLength, gl.DYNAMIC_DRAW);
      const location = gl.getAttribLocation(program, 'point'); gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, 4, gl.FLOAT, false, 0, 0);
      index = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, index);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.indices, gl.STATIC_DRAW);
      texture = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      // Resize before uploading: a phone photo must not create a 48 MP texture.
      const source = document.createElement('canvas'); source.width = canvas.width; source.height = canvas.height;
      source.getContext('2d').drawImage(img, 0, 0, source.width, source.height);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
      source.width = source.height = 1;
      gl.viewport(0, 0, canvas.width, canvas.height);
      const self = this;
      return { fps: this.FPS, dispose: dispose, draw: function (t) {
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, self.deform(mesh, plan.layers, t));
        gl.drawElements(gl.TRIANGLES, mesh.indices.length, gl.UNSIGNED_SHORT, 0);
      } };
    } catch (error) { dispose(); return null; }
  },
  // Canvas 2D fallback uses the same joined mesh, at a smaller working size.
  cpu: function (canvas, img, plan) {
    const g = canvas.getContext('2d'), self = this;
    const mesh = this.mesh(canvas.width, canvas.height, plan.layers, 20);
    const W = canvas.width, H = canvas.height;
    const source = document.createElement('canvas'); source.width = W; source.height = H;
    source.getContext('2d').drawImage(img, 0, 0, W, H);
    return { fps: 15, dispose: function () { source.width = source.height = 1; }, draw: function (t) {
      const v = self.deform(mesh, plan.layers, t);
      // Underlay prevents subpixel antialiasing cracks between clipped triangles.
      g.drawImage(source, 0, 0);
      for (let i = 0; i < mesh.indices.length; i += 3) {
        const ids = [mesh.indices[i] * 4, mesh.indices[i + 1] * 4, mesh.indices[i + 2] * 4];
        const s = ids.map(j => [v[j + 2] * W, v[j + 3] * H]);
        const d = ids.map(j => [v[j] * W, v[j + 1] * H]);
        if (s.every((p, j) => Math.abs(p[0] - d[j][0]) + Math.abs(p[1] - d[j][1]) < .001)) continue;
        const sx1 = s[1][0] - s[0][0], sy1 = s[1][1] - s[0][1];
        const sx2 = s[2][0] - s[0][0], sy2 = s[2][1] - s[0][1], det = sx1 * sy2 - sx2 * sy1;
        const dx1 = d[1][0] - d[0][0], dy1 = d[1][1] - d[0][1];
        const dx2 = d[2][0] - d[0][0], dy2 = d[2][1] - d[0][1];
        const a = (dx1 * sy2 - dx2 * sy1) / det, c = (dx2 * sx1 - dx1 * sx2) / det;
        const b = (dy1 * sy2 - dy2 * sy1) / det, f = (dy2 * sx1 - dy1 * sx2) / det;
        g.save(); g.beginPath(); g.moveTo(d[0][0], d[0][1]); g.lineTo(d[1][0], d[1][1]); g.lineTo(d[2][0], d[2][1]); g.closePath(); g.clip();
        g.setTransform(a, b, c, f, d[0][0] - a * s[0][0] - c * s[0][1], d[0][1] - b * s[0][0] - f * s[0][1]);
        g.drawImage(source, 0, 0); g.restore();
      }
    } };
  },
  stop: function () {
    if (this.active) this.active.stop();
    this.active = null;
  },
  // A model's coordinates are a suggestion. A teacher can correct the region
  // on the original image and preview it immediately, with no further call.
  selection: function (from, to) {
    const clamp = v => Math.max(0, Math.min(1, v));
    const a = from.map(clamp), b = to.map(clamp);
    const box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1])];
    return box[2] >= .03 && box[3] >= .03 ? box : null;
  },
  open: function (host, plan, drawing) {
    const self = this, t = key => Studio.i18n.t(key);
    if (!this.valid(plan)) return this.play(host, plan, drawing);
    const stage = document.createElement('div'); stage.className = 'motion-stage';
    const controls = document.createElement('div'); controls.className = 'motion-controls';
    const edit = document.createElement('button'); edit.className = 'btn quiet'; edit.type = 'button';
    edit.textContent = t('motion.adjust'); edit.setAttribute('aria-pressed', 'false');
    const regions = document.createElement('select'); regions.setAttribute('aria-label', t('motion.region'));
    plan.layers.forEach(function (_, i) {
      const option = document.createElement('option'); option.value = i;
      option.textContent = t('motion.region') + ' ' + (i + 1); regions.appendChild(option);
    });
    const action = document.createElement('select'); action.setAttribute('aria-label', t('motion.action'));
    ['breathe', 'sway', 'drift', 'rise', 'grow'].forEach(function (move) {
      const option = document.createElement('option'); option.value = move;
      option.textContent = t('motion.' + move); action.appendChild(option);
    });
    const hint = document.createElement('p'); hint.className = 'motion-hint'; hint.textContent = t('motion.hint');
    const outline = document.createElement('div'); outline.className = 'motion-outline';
    let selected = 0, editing = false, from = null, player;
    function mark(box) {
      outline.style.left = box[0] * 100 + '%'; outline.style.top = box[1] * 100 + '%';
      outline.style.width = box[2] * 100 + '%'; outline.style.height = box[3] * 100 + '%';
    }
    function refresh() {
      regions.hidden = action.hidden = hint.hidden = outline.hidden = !editing;
      stage.classList.toggle('editing', editing); edit.textContent = t(editing ? 'motion.preview' : 'motion.adjust');
      edit.setAttribute('aria-pressed', String(editing));
      action.value = plan.layers[selected].move;
      mark(plan.layers[selected].box);
      if (player) player.paused = editing;
      const canvas = stage.querySelector('canvas'); if (editing && canvas && canvas.motionDraw) canvas.motionDraw(0);
    }
    function restart() {
      self.stop(); stage.replaceChildren(); player = self.play(stage, plan, drawing);
      stage.appendChild(outline); refresh();
    }
    function position(e) { const b = stage.getBoundingClientRect(); return [(e.clientX - b.left) / b.width, (e.clientY - b.top) / b.height]; }
    edit.onclick = function () { editing = !editing; refresh(); };
    regions.onchange = function () { selected = Number(regions.value); refresh(); };
    action.onchange = function () { plan.layers[selected].move = action.value; restart(); };
    stage.onpointerdown = function (e) {
      if (!editing || e.button !== 0) return;
      from = position(e); stage.setPointerCapture(e.pointerId); e.preventDefault();
    };
    stage.onpointermove = function (e) {
      if (!from) return; const box = self.selection(from, position(e)); if (box) mark(box);
    };
    stage.onpointerup = function (e) {
      if (!from) return;
      const box = self.selection(from, position(e)); from = null;
      if (box) { plan.layers[selected].box = box; restart(); } else refresh();
    };
    stage.onpointercancel = function () { from = null; refresh(); };
    controls.append(edit, regions, action); host.append(stage, controls, hint); restart();
  },
  play: function (host, plan, drawing) {
    this.stop();
    const self = this, img = new Image();
    let canvas = document.createElement('canvas'), renderer, raf = null, stopped = false;
    const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const handle = { stop: function () {
      stopped = true; if (raf !== null) cancelAnimationFrame(raf);
      img.onload = img.onerror = null;
      img.src = '';
      if (renderer) renderer.dispose();
      if (canvas) { delete canvas.motionDraw; canvas.width = canvas.height = 1; }
    } };
    this.active = handle; host.appendChild(canvas);
    function failed() {
      if (stopped) return;
      handle.stop();
      const note = document.createElement('p'); note.textContent = Studio.i18n.t('motion.failed'); host.appendChild(note);
    }
    if (!this.valid(plan) || !drawing || !drawing.url) { failed(); return handle; }
    img.onerror = failed;
    img.onload = function () {
      if (stopped) return;
      try {
        const size = self.dimensions(img.naturalWidth || img.width, img.naturalHeight || img.height, self.MAX_EDGE);
        canvas.width = size[0]; canvas.height = size[1];
        renderer = self.gpu(canvas, img, plan);
        if (!renderer) {
          // A canvas whose WebGL context was acquired cannot switch to 2D.
          const fallback = document.createElement('canvas'); host.replaceChild(fallback, canvas); canvas = fallback;
          const small = self.dimensions(size[0], size[1], 640); canvas.width = small[0]; canvas.height = small[1];
          renderer = self.cpu(canvas, img, plan);
        }
        canvas.motionDuration = plan.duration_s;
        canvas.motionReduced = !!reduced;
        canvas.motionDraw = renderer.draw;
        renderer.draw(0);
        canvas.addEventListener('webglcontextlost', function (event) { event.preventDefault(); failed(); }, { once: true });
        if (reduced) return;
        let elapsed = 0, last = performance.now(), painted = -Infinity;
        function frame(now) {
          if (stopped) return;
          if (!document.hidden && !handle.paused) {
            elapsed += Math.min(100, now - last);
            if (now - painted >= 1000 / renderer.fps - 1) {
              renderer.draw((elapsed / 1000) % plan.duration_s); painted = now;
            }
          }
          last = now; raf = requestAnimationFrame(frame);
        }
        raf = requestAnimationFrame(frame);
      } catch (error) { failed(); }
    };
    img.src = drawing.url;
    return handle;
  }
};
