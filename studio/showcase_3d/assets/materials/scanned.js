// Poly Haven CC0 surfaces. Height-gradient projection avoids tangent-UV seams.
export function scannedSurfaces(THREE, materials, grainStrength, refresh) {
  const specs = {wood:['oak_veneer_01',0.6,0.00045], denim:['denim_fabric',1.8,0.00002], rust:['rust_coarse_01',0.8,0.0008]};
  const states = new Map(), textures = new Set();
  let disposed = false;
  function ensure(kind) {
    if (!specs[kind] || states.has(kind) || disposed) return;
    states.set(kind, 'loading');
    const [asset, scale, relief] = specs[kind];
    const loader = new THREE.TextureLoader();
    Promise.all(['diff','rough','disp'].map(async channel => {
      const texture = await loader.loadAsync(new URL(`${asset}_${channel}_1k.png`, import.meta.url).href);
      if (disposed) {texture.dispose(); throw Error('disposed');}
      textures.add(texture);
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.colorSpace = channel === 'diff' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      texture.needsUpdate = true;
      return texture;
    })).then(([color, rough, height]) => {
      if (disposed) return;
      const material = materials[kind];
      material.color.set(0xffffff); material.roughness = 1;
      material.clearcoat = 0;
      material.onBeforeCompile = shader => {
        Object.assign(shader.uniforms, {scanColor:{value:color},scanRough:{value:rough},scanHeight:{value:height},scanStrength:kind==='wood'?grainStrength:{value:1}});
        shader.vertexShader = 'attribute vec3 surfacePosition; varying vec3 scanPosition;\n' + shader.vertexShader;
        shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nscanPosition = surfacePosition;');
        shader.fragmentShader = `varying vec3 scanPosition;
          uniform sampler2D scanColor, scanRough, scanHeight;
          uniform float scanStrength;
          vec2 scanUV(vec2 uv) {
            ${kind === 'denim' ? `
              // Sample only the inspected seam-free central cloth region.
              // Mirrored tiles keep the cropped borders continuous.
              uv = 1.0 - abs(mod(uv, 2.0) - 1.0);
              return vec2(0.50, 0.10) + uv * vec2(0.35, 0.35);
            ` : 'return uv;'}
          }
          ${kind === 'denim' ? `
          // Individual warp/weft crossings: three indigo floats, one pale weft.
          // No continuous raised diagonal ridges; subpixel crossings fade out.
          vec2 denimYarn(vec2 uv) {
            vec2 yarn = uv * 82.0;
            vec2 cell = floor(yarn), f = fract(yarn);
            float visibility = 1.0 - smoothstep(0.30, 0.85, max(fwidth(yarn.x), fwidth(yarn.y)));
            float warp = step(0.5, mod(cell.x + cell.y, 4.0));
            float across = mix(f.y, f.x, warp);
            float strand = pow(max(sin(across * 3.14159265), 0.0), 0.6);
            float yarnTone = mix(0.38, -0.08, warp) + 0.12 * (strand - 0.70);
            return vec2(yarnTone, strand - 0.70) * visibility;
          }` : ''}
          vec4 projectScan(sampler2D tex, vec3 p, vec3 w) {
            return texture2D(tex,scanUV(p.zy))*w.x + texture2D(tex,scanUV(p.xz))*w.y + texture2D(tex,scanUV(p.xy))*w.z;
          }\n` + shader.fragmentShader;
        shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', `
          #include <color_fragment>
          vec3 scanP = scanPosition * ${scale.toFixed(2)};
          vec3 scanN = normalize(cross(dFdx(scanPosition),dFdy(scanPosition)));
          vec3 scanW = pow(abs(scanN),vec3(${kind==='denim'?'8.0':'4.0'})); scanW /= max(dot(scanW,vec3(1.0)),0.00001);
          diffuseColor.rgb *= mix(${kind==='wood'?'vec3(0.52,0.30,0.13)':'vec3(1.0)'},projectScan(scanColor,scanP,scanW).rgb,scanStrength);
          float scanH = projectScan(scanHeight,scanP,scanW).r * ${relief.toFixed(5)} * scanStrength;
          ${kind === 'denim' ? `
          vec2 yarnDetail = denimYarn(scanPosition.zy) * scanW.x
            + denimYarn(scanPosition.xz) * scanW.y + denimYarn(scanPosition.xy) * scanW.z;
          // Indigo warp / lighter weft, with shallow thread relief rather than pits.
          diffuseColor.rgb *= 0.98 + 0.30 * yarnDetail.x;
          scanH += 0.000025 * yarnDetail.y;
          ` : ''}
        `).replace('#include <roughnessmap_fragment>', `
          #include <roughnessmap_fragment>
          roughnessFactor = clamp(mix(0.43,projectScan(scanRough,scanP,scanW).r,scanStrength),${kind==='denim'?'0.88':'0.22'},1.0);
        `).replace('#include <normal_fragment_maps>', `
          #include <normal_fragment_maps>
          vec3 dx = dFdx(-vViewPosition), dy = dFdy(-vViewPosition);
          vec3 r1 = cross(dy,normal), r2 = cross(normal,dx);
          float det = dot(dx,r1);
          normal = normalize(abs(det)*normal-sign(det)*(dFdx(scanH)*r1+dFdy(scanH)*r2));
        `);
      };
      material.customProgramCacheKey = () => `scan-${kind}-v4`;
      material.needsUpdate = true;
      states.set(kind,'ready'); refresh();
    }).catch(() => {if (!disposed) {states.set(kind,'error'); refresh();}});
  }
  return {ensure, status:kind=>states.get(kind), dispose() {disposed=true; textures.forEach(t=>t.dispose()); textures.clear();}};
}
