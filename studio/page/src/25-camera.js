// Photos in: from the camera or from a file, downscaled and oriented, then handed to the session.
window.Studio = window.Studio || {};
Studio.photos = {
  MAX: 1600,
  // Bind decoding, the light check and upload to the class that chose the image.
  // Prepared URLs belong here until addDrawing takes responsibility for them.
  importDrawing: async function (blob, sessionId) {
    const id = sessionId === undefined ? Studio.state.session : sessionId;
    let prepared = null, handedOff = false;
    try {
      if (!Studio.session.isCurrent(id)) return null;
      prepared = await this.prepare(blob);
      if (!Studio.session.isCurrent(id)) return null;
      const stats = await this.stats(prepared.url);
      if (!Studio.session.isCurrent(id)) return null;
      if (stats && Studio.isDark(stats)) {
        const error = new Error('dark image'); error.code = 'dark_image'; throw error;
      }
      handedOff = true;
      return await Studio.session.addDrawing(prepared.blob, prepared.url, id);
    } catch (error) {
      if (!Studio.session.isCurrent(id)) return null;
      throw error;
    } finally {
      if (prepared && !handedOff) Studio.session.releaseUrl(prepared.url);
    }
  },
  prepare: function (blob) {
    const self = this;
    const decode = ('createImageBitmap' in window) ? createImageBitmap(blob, { imageOrientation: 'from-image' })
      : Promise.reject(new Error('no bitmap'));
    return decode.catch(function () {
      return new Promise(function (resolve, reject) {
        const img = new Image(); img.onload = function () { resolve(img); }; img.onerror = reject; img.src = URL.createObjectURL(blob);
      });
    }).then(function (src) {
      const w = src.width, h = src.height, k = Math.min(1, self.MAX / Math.max(w, h));
      const c = document.createElement('canvas'); c.width = Math.round(w * k); c.height = Math.round(h * k);
      c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
      return new Promise(function (resolve) { c.toBlob(function (out) { resolve({ blob: out, url: URL.createObjectURL(out) }); }, 'image/jpeg', .9); });
    });
  },
  // Pixel statistics of an image url, for the dark-frame check at upload and for the mock harness.
  stats: function (url) {
    return new Promise(function (resolve) {
      const img = new Image();
      img.onload = function () {
        const c = document.createElement('canvas'), s = 96; c.width = s; c.height = s;
        const g = c.getContext('2d'); g.drawImage(img, 0, 0, s, s);
        resolve(Studio.imageStats(g.getImageData(0, 0, s, s).data));
      };
      img.onerror = function () { resolve(null); };
      img.src = url;
    });
  },
  // Pick an existing artwork from the local classroom sample library.
  sample: function () { return Studio.samples.choose(); },
  camera: {
    stream: null,
    open: function () {
      const overlay = document.getElementById('camera-overlay'), video = document.getElementById('cam');
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return Promise.reject(new Error('no camera'));
      return navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } }, audio: false })
        .then(function (stream) { Studio.photos.camera.stream = stream; video.srcObject = stream; overlay.hidden = false; });
    },
    shoot: function () {
      const video = document.getElementById('cam'), c = document.createElement('canvas');
      c.width = video.videoWidth || 1280; c.height = video.videoHeight || 960;
      c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
      return new Promise(function (resolve) { c.toBlob(resolve, 'image/jpeg', .92); });
    },
    close: function () {
      const overlay = document.getElementById('camera-overlay'), video = document.getElementById('cam');
      if (this.stream) { this.stream.getTracks().forEach(function (t) { t.stop(); }); this.stream = null; }
      video.srcObject = null; overlay.hidden = true;
    }
  }
};
