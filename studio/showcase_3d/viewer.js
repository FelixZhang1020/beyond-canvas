import {scannedSurfaces} from './assets/materials/scanned.js';
import * as THREE from 'three';
let classroomEnglish = false, surfaceEnglish;
import {GLTFLoader} from './vendor/loaders/GLTFLoader.js';
import {boundedAsset, checkedBuffer} from './asset-guard.mjs';
import {solidScene, solidGroup} from './solid-scene.mjs';

const $ = (s, parent = document) => parent.querySelector(s);
const classroomMode = document.body.dataset.mode === 'classroom';
const studyMode = classroomMode || document.body.dataset.mode === 'exhibit';
const canvas = $('#scene-canvas');
const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, powerPreference: 'low-power'});
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.info.autoReset = false;
renderer.transmissionResolutionScale = 0.5;
const radians = THREE.MathUtils.degToRad;
const origin = new THREE.Vector3();
const grainStrength = {value: Number($('#wood-grain').value) / 100};
// Composite each isolated render into its card. Transmission never renders into the UI canvas.
const compositeScene = new THREE.Scene();
const compositeCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const compositeMaterial = new THREE.MeshBasicMaterial({depthTest: false, depthWrite: false});
compositeScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), compositeMaterial));
const materials = {
  matte: new THREE.MeshStandardMaterial({color: 0xa5a29c, roughness: 1, metalness: 0, side: THREE.DoubleSide}),
  plaster: new THREE.MeshStandardMaterial({color: 0xeeeae2, roughness: 0.94}),
  marble: new THREE.MeshPhysicalMaterial({color: 0xf4f2ee, roughness: 0.36, metalness: 0, clearcoat: 0}),
  wood: new THREE.MeshPhysicalMaterial({color: 0xa87543, roughness: 0.43, clearcoat: 0.12, clearcoatRoughness: 0.5}),
  metal: new THREE.MeshStandardMaterial({color: 0xdde1e3, metalness: 1, roughness: 0.28, envMapIntensity: 1}),
  glass: new THREE.MeshPhysicalMaterial({color: 0xffffff, roughness: 0.035, transmission: 1, thickness: 0.65, ior: 1.5, attenuationColor: new THREE.Color(0xf5faf7), attenuationDistance: 10}),
  denim: new THREE.MeshPhysicalMaterial({color:0x496787, roughness:0.95, sheen:0.35, sheenColor:0x8298ac, sheenRoughness:0.9}),
  rust: new THREE.MeshStandardMaterial({color:0x98502d, roughness:0.95, metalness:0}),
  chocolate: new THREE.MeshPhysicalMaterial({color: 0x482115, roughness: 0.34, clearcoat: 0.18, clearcoatRoughness: 0.3}),
  normal: studyMode ? new THREE.MeshStandardMaterial({color:0xffffff, roughness:0.8, side:THREE.DoubleSide}) : new THREE.MeshNormalMaterial({side: THREE.DoubleSide}),
  wire: new THREE.MeshBasicMaterial({color: 0x716679, wireframe: true})
};
if (studyMode) {
  // Normal colours remain diagnostic colours, but now participate in lighting and shadows.
  materials.normal.onBeforeCompile = shader => {
    shader.fragmentShader = shader.fragmentShader.replace('#include <normal_fragment_maps>',
      '#include <normal_fragment_maps>\ndiffuseColor.rgb = normal * 0.5 + 0.5;');
  };
  materials.normal.customProgramCacheKey=()=> 'lit-normal-colours-v1';
  Object.assign(materials.glass,{roughness:0.09,transmission:0.9,clearcoat:1,clearcoatRoughness:0.12});
}
// Object-space grain avoids UV seams and works on untextured provider meshes.
for (const kind of ['plaster', 'wood', 'marble']) {
  materials[kind].onBeforeCompile = shader => {
    shader.uniforms.grainStrength = grainStrength;
    shader.vertexShader = (kind === 'wood' ? '' : 'attribute vec3 surfacePosition;\n') + 'varying vec3 vGrain;\n' + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvGrain = ' + (kind === 'wood' ? 'position' : 'surfacePosition') + ';');
    shader.fragmentShader = 'varying vec3 vGrain;\nuniform float grainStrength;\n' + shader.fragmentShader;
    if (kind === 'marble' || kind === 'plaster') shader.fragmentShader = `
      float stoneHash(vec3 p) {
        p = fract(p * 0.1031);
        p += dot(p, p.yzx + 33.33);
        return fract((p.x + p.y) * p.z);
      }
      float stoneNoise(vec3 p) {
        vec3 i = floor(p), f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(mix(stoneHash(i), stoneHash(i + vec3(1,0,0)), f.x),
                       mix(stoneHash(i + vec3(0,1,0)), stoneHash(i + vec3(1,1,0)), f.x), f.y),
                   mix(mix(stoneHash(i + vec3(0,0,1)), stoneHash(i + vec3(1,0,1)), f.x),
                       mix(stoneHash(i + vec3(0,1,1)), stoneHash(i + vec3(1,1,1)), f.x), f.y), f.z);
      }
      float stoneCloud(vec3 p) {
        return 0.57 * stoneNoise(p) + 0.28 * stoneNoise(p * 2.07 + 11.3)
          + 0.15 * stoneNoise(p * 4.13 + 27.1);
      }
    ` + shader.fragmentShader;
    const pattern = kind === 'wood' ? `
      vec3 p = vGrain * 3.0;
      float warp = 0.06 * sin(p.y * 1.8 + sin(p.z * 2.0)) + 0.025 * sin(p.y * 5.0);
      float ringPhase = length(vec2(p.x + warp, p.z * 0.85)) * 90.0;
      float rings = 0.5 + 0.5 * sin(ringPhase + 1.2 * sin(ringPhase * 0.19));
      float fibers = 0.5 + 0.5 * sin((p.x + warp) * 260.0 + sin(p.z * 47.0));
      float variation = sin(p.x * 13.0 + p.z * 9.0 + sin(p.y * 0.8));
      float detail = 0.11 * variation - 0.30 * pow(rings, 9.0) - 0.10 * pow(fibers, 16.0);
      diffuseColor.rgb *= 1.0 + grainStrength * detail;
    ` : kind === 'marble' ? `
      // Low-contrast mineral clouds, without periodic contours or painted outlines.
      vec3 p = vGrain * 3.0;
      float cloud = stoneCloud(p * vec3(0.8, 1.3, 0.9));
      vec3 drift = vec3(cloud, stoneCloud(p + 7.4), stoneCloud(p + 19.2));
      float mineral = stoneCloud(p * vec3(1.2, 5.0, 1.6) + drift * 2.0);
      float haze = smoothstep(0.43, 0.76, mineral);
      // Stretched mineral deposits with soft edges, not periodic vein outlines.
      float deposit = stoneCloud(p * vec3(0.65, 7.0, 1.1) + drift * 2.7);
      float wisps = smoothstep(0.54, 0.72, deposit);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.57, 0.59, 0.60), wisps * 0.38);
      // Fade subpixel grains before they can shimmer when zoomed out.
      float grainVisibility = 1.0 - smoothstep(0.35, 1.1, length(fwidth(p * 24.0)));
      float crystal = stoneNoise(p * 24.0);
      float inclusions = smoothstep(0.66, 0.88, stoneNoise(p * vec3(3.0, 9.0, 4.0) + drift));
      float flecks = smoothstep(0.72, 0.9, crystal) * grainVisibility;
      diffuseColor.rgb *= 0.98 + 0.02 * cloud - 0.065 * haze
        + 0.045 * (crystal - 0.5) * grainVisibility;
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.52, 0.53, 0.52),
        inclusions * 0.19 + flecks * 0.045);
    ` : `
      vec3 powderPosition = vGrain * 72.0;
      float powderVisibility = 1.0 - smoothstep(0.4, 1.3, length(fwidth(powderPosition)));
      float powder = stoneNoise(powderPosition);
      float poreVisibility = 1.0 - smoothstep(0.4, 1.3, length(fwidth(vGrain * 65.0)));
      float pores = smoothstep(0.80, 0.95, stoneNoise(vGrain * 65.0 + 9.2));
      diffuseColor.rgb *= 0.985 + 0.035 * (powder - 0.5) * powderVisibility
        - 0.055 * pores * poreVisibility;
      float plasterHeight = 0.00014 * powder * powderVisibility - 0.00010 * pores * poreVisibility;
    `;
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\n' + pattern);
    if (kind === 'plaster') {
      shader.fragmentShader = shader.fragmentShader.replace('#include <roughnessmap_fragment>', `
        #include <roughnessmap_fragment>
        roughnessFactor = clamp(0.94 + (powder - 0.5) * 0.10 * powderVisibility, 0.89, 0.99);
      `);
      shader.fragmentShader = shader.fragmentShader.replace('#include <normal_fragment_maps>', `
        #include <normal_fragment_maps>
        // Powder and shallow pores change the lighting, not just the colour.
        vec3 plasterDx = dFdx(-vViewPosition), plasterDy = dFdy(-vViewPosition);
        vec3 plasterR1 = cross(plasterDy, normal), plasterR2 = cross(normal, plasterDx);
        float plasterDet = dot(plasterDx, plasterR1);
        vec3 plasterGradient = sign(plasterDet) * (dFdx(plasterHeight) * plasterR1 + dFdy(plasterHeight) * plasterR2);
        normal = normalize(abs(plasterDet) * normal - plasterGradient);
      `);
    }
    if (kind === 'marble') {
      // A normalized wrap diffuse lobe softens the terminator. This is a surface
      // approximation, not thickness-dependent transmission or volumetric SSS.
      // Shadowed directLight and the original specular response remain intact.
      const marbleLighting = THREE.ShaderChunk.lights_physical_pars_fragment.replace(
        'reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );',
        `float marbleCos = dot(geometryNormal, directLight.direction);
         float marbleWrap = max(marbleCos + 0.25, 0.0) / 1.5625;
         vec3 marbleIrradiance = mix(dotNL, marbleWrap, 0.35) * directLight.color;
         reflectedLight.directDiffuse += marbleIrradiance * BRDF_Lambert(material.diffuseColor);`
      );
      shader.fragmentShader = shader.fragmentShader.replace('#include <lights_physical_pars_fragment>', marbleLighting);
      shader.fragmentShader = shader.fragmentShader.replace('#include <roughnessmap_fragment>', `
        #include <roughnessmap_fragment>
        roughnessFactor = clamp(roughnessFactor + (stoneNoise(p * 24.0 + 41.7) - 0.5) * 0.16 * grainVisibility, 0.28, 0.58);
      `).replace('#include <normal_fragment_maps>', `
        #include <normal_fragment_maps>
        // Screen-space surface gradient adds fine relief without requiring UVs.
        vec3 stoneDx = dFdx(-vViewPosition), stoneDy = dFdy(-vViewPosition);
        vec3 stoneR1 = cross(stoneDy, normal), stoneR2 = cross(normal, stoneDx);
        float stoneDet = dot(stoneDx, stoneR1);
        float stoneHeight = crystal * 0.00012 * grainVisibility;
        vec3 stoneGradient = sign(stoneDet) * (dFdx(stoneHeight) * stoneR1 + dFdy(stoneHeight) * stoneR2);
        normal = normalize(abs(stoneDet) * normal - stoneGradient);
      `);
    }

  };
  materials[kind].customProgramCacheKey = () => 'surface-' + kind + (kind === 'wood' ? '-v3' : '-v7');
}
const scans = scannedSurfaces(THREE, materials, grainStrength, () => {cards.forEach(applySurface); requestRender();});
let metalEnvironment;
function neutralMetalEnvironment() {
  // A uniform surround keeps metal visible without fixed softboxes or dark cards.
  // All directional highlights then come from the user-controlled light.
  if (!metalEnvironment) {
    const room = new THREE.Scene(); room.background = new THREE.Color(0xb8b8b8);
    const generator = new THREE.PMREMGenerator(renderer);
    metalEnvironment = generator.fromScene(room, 0, 0.1, 10, {size: 16});
    generator.dispose();
  }
  return metalEnvironment.texture;
}
let steelEnvironment;
function stainlessEnvironment() {
  if (steelEnvironment) return steelEnvironment.texture;
  // Linear radiance: a light ceiling, darker floor and a broad, feathered light reflection.
  // A constant environment is a white-furnace test, which removes metallic shape cues.
  const room = new THREE.Scene();
  const shell = new THREE.Mesh(new THREE.SphereGeometry(5, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide,
    vertexShader: `varying vec3 direction;
      void main() { direction = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 direction;
      void main() {
        vec3 d = normalize(direction);
        float surround = mix(0.075, 0.85, smoothstep(-0.35, 0.5, d.y));
        vec2 spread = d.xy / vec2(0.32, 0.95);
        float softLight = 2.8 * exp(-dot(spread, spread)) * smoothstep(0.0, 0.45, d.z);
        gl_FragColor = vec4(vec3(surround + softLight), 1.0);
      }`
  }));
  room.add(shell);
  const generator = new THREE.PMREMGenerator(renderer);
  steelEnvironment = generator.fromScene(room, 0.04, 0.1, 10, {size:128});
  generator.dispose(); shell.geometry.dispose(); shell.material.dispose();
  return steelEnvironment.texture;
}
let studioEnvironment;
function environment() {
  if (studioEnvironment) return studioEnvironment.texture;
  const room = new THREE.Scene(); room.background = new THREE.Color(0xc6c8ca);
  const box = new THREE.Mesh(new THREE.BoxGeometry(20, 12, 20), new THREE.MeshBasicMaterial({color: 0xc6c4bf, side: THREE.BackSide}));
  room.add(box);
  const darkCard = new THREE.Mesh(new THREE.PlaneGeometry(2, 6), new THREE.MeshBasicMaterial({color: 0x454b52, side: THREE.DoubleSide}));
  darkCard.position.set(3, 0, 5); darkCard.lookAt(origin); room.add(darkCard);
  for (const [x,y,z,sx,sy,intensity] of [[-4,3,1,3,6,5],[4,2,-3,2,5,3],[0,5,0,5,2,4]]) {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(sx,sy), new THREE.MeshBasicMaterial({color: new THREE.Color().setScalar(intensity), side: THREE.DoubleSide}));
    panel.position.set(x,y,z); panel.lookAt(origin); room.add(panel);
  }
  const generator = new THREE.PMREMGenerator(renderer);
  studioEnvironment = generator.fromScene(room, 0.04, 0.1, 40, {size: 128});
  generator.dispose(); room.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
  return studioEnvironment.texture;
}
const surfaceNotes = {
  matte: '统一哑光用于比较几何形体。', plaster: '石膏：粉白、细密粉粒与浅小孔隙，干燥哑光表面。',
  marble: '白大理石：温润白色、淡淡矿物云纹与细腻柔光。',
  denim: '牛仔布：蓝色织纹与细密纤维，表面贴图不改变模型形状。',
  rust: '锈铁：红褐色氧化层与粗糙表面。',
  wood: '橡木：实物采集木纹与细微表面起伏，纹理强度可调。', metal: '浅色不锈钢：银灰反射与柔和亮带；移动光源观察反光和投影。',
  glass: studyMode ? '透明玻璃：移动光源观察高光、明暗与浅投影；透光阴影为近似，不模拟焦散。' : '透明玻璃：浅色条纹背板辅助观察折射，厚度为近似；不模拟焦散或准确透光阴影。',
  chocolate: '巧克力：深棕色与柔和表面光泽；未模拟次表面散射。',
  normal: studyMode ? '表面朝向：用颜色区分朝向，同时显示光源带来的明暗和投影。' : '表面朝向用于检查几何。', wire: '网格用于检查三角面分布。'
};
function applySurface(card) {
  const kind = $('#material').value;
  scans.ensure(kind);
  // Give stainless steel its own reflection exposure; keep classroom fill and floor unchanged.
  if (kind === 'metal') materials.metal.envMap = stainlessEnvironment();
  if (classroomMode) document.querySelectorAll('[data-classroom-material]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.classroomMaterial === kind)));
  card.scene.environment = studyMode ? neutralMetalEnvironment() : kind === 'metal' ? neutralMetalEnvironment() : ['glass','chocolate','wood','plaster','marble','denim','rust'].includes(kind) ? environment() : null;
  card.scene.environmentIntensity = studyMode ? 0.25 : kind === 'metal' ? 0.85 : 0.65;
  card.backdrop.visible = kind === 'glass';
  if (studyMode) {
    card.floor.visible = $('#ground').checked;
    $('#ground').disabled = false;
    // Uniform attenuation is a smooth real-time approximation of a transmitted shadow.
    card.light.shadow.intensity = kind === 'glass' ? 0.25 : 1;
  }
  card.model?.traverse(o => {if (o.isMesh) {o.material = materials[kind]; o.castShadow = studyMode || kind !== 'glass';}});
  card.sphere.material = materials[kind]; card.sphere.castShadow = studyMode || kind !== 'glass';
  $('#wood-control').hidden = kind !== 'wood';
  card.light.shadow.needsUpdate = true;
  $('#material-note').textContent = (classroomMode ? '' : '课堂现用 TRELLIS.2 · Pixal3D 已归档 ｜ ') + (classroomEnglish ? surfaceEnglish[kind] : surfaceNotes[kind]) + (scans.status(kind) === 'loading' ? (classroomEnglish ? ' Loading texture…' : ' 正在加载纹理…') : scans.status(kind) === 'error' ? (classroomEnglish ? ' Texture unavailable; showing base material.' : ' 纹理加载失败，显示基础材质。') : '') + (classroomMode ? '' : ' 导出仍为原始模型。');
}
let manifest, selected = 'portrait', cards = [], revision = 0, abort, frame = 0, auto = false, lastFrame = 0;
let studyInteraction = 'orbit';
function reportStudyState() {
  if (!classroomMode || !cards[0]?.ready) return;
  parent.postMessage({type:'study-state',state:{mode:studyInteraction,auto,material:$('#material').value,
    grayscale:$('#grayscale').checked,ground:$('#ground').checked,
    direction:Number($('#light-azimuth').value),elevation:Number($('#light-elevation').value),wireAvailable:true}},location.origin);
}
let loadingChain = Promise.resolve();
// Reuse four scene/camera identities: Three retains transmission targets per pair.
const renderSlots = [];

function disposeScene(root) {
  const geometries = new Set(), mats = new Set(), textures = new Set();
  root.traverse(o => {
    if (o.geometry) geometries.add(o.geometry);
    for (const m of [].concat(o.material || [])) if (!Object.values(materials).includes(m)) mats.add(m);
    if (o.shadow?.map) o.shadow.map.dispose();
  });
  for (const m of mats) {
    for (const value of Object.values(m)) if (value?.isTexture) textures.add(value);
    m.dispose();
  }
  for (const t of textures) {t.dispose(); t.source?.data?.close?.();}
  for (const g of geometries) g.dispose();
  root.clear();
}


function cameraQuaternion(yaw, polar) {
  const camera = new THREE.PerspectiveCamera();
  camera.position.setFromSphericalCoords(5, radians(polar), radians(yaw));
  camera.lookAt(origin); return camera.quaternion;
}

function calibratedBase(scene, catalog) {
  const valid = base => Array.isArray(base) && base.length === 2 && base.every(Number.isFinite)
    && base[0] >= -180 && base[0] <= 180 && base[1] > 0 && base[1] < 180;
  if (valid(scene.camera_base)) return scene.camera_base;
  const saved = catalog.samples?.flatMap(sample => sample.cases || []).find(item => item.sha256 === scene.sha256);
  const base = saved?.camera_base;
  return valid(base) ? base : scene.model === 'pixal' ? [180,75] : [45,75];
}

function fittedDistance(extent, aspect) {
  const inverse = cameraQuaternion(0,75).clone().invert();
  const tangent = Math.tan(radians(36)/2);
  let distance = 0;
  for (const x of [-1,1]) for (const y of [-1,1]) for (const z of [-1,1]) {
    const p = new THREE.Vector3(x*extent.x/2,y*extent.y/2,z*extent.z/2).applyQuaternion(inverse);
    distance = Math.max(distance, p.z + 1.35*Math.max(Math.abs(p.x)/(tangent*aspect), Math.abs(p.y)/tangent));
  }
  return Math.max(2.5,distance);
}

async function loadCard(card, token, signal) {
  if (card.item.status !== 'ready') {
    $('.loading', card.el).classList.add('pending');
    $('.loading-text', card.el).textContent = card.item.display_error || '显示版本尚未完成';
    $('.case-status', card.el).textContent = '待补齐'; return;
  }
  try {
    let raw;
    if (card.item.solids) raw = solidGroup(card.item.solids);
    else {
      const data = classroomMode && card.item.buffer ? await checkedBuffer(card.item.buffer, card.item) : await boundedAsset(card.item, signal);
      if (token !== revision) return;
      // The override prevents PBR image decoding; geometry remains the provider's actual GLB.
      const loader = new GLTFLoader();
      loader.register(() => ({name: 'ComparisonMatte', loadMaterial: () => Promise.resolve(materials[$('#material').value])}));
      const gltf = await loader.parseAsync(data, '');
      if (token !== revision) {disposeScene(gltf.scene); return;}
      raw = gltf.scene;
    }
    const old = new Set();
    raw.traverse(o => {
      if (!o.isMesh) return;
      for (const m of [].concat(o.material)) if (!Object.values(materials).includes(m)) old.add(m);
      o.material = materials[$('#material').value]; o.castShadow = o.receiveShadow = true;
    });
    old.forEach(m => m.dispose());
    const base = !classroomMode && card.item.comparison_camera_base || card.item.camera_base;
    // In the classroom the model stays upright and the camera takes the drawing's height instead: tilting the
    // model to match a steeper view lifted it off the floor.
    card.basePolar = classroomMode ? THREE.MathUtils.clamp(base[1], 20, 88) : 75;
    card.baseRotation = cameraQuaternion(0, 75).multiply(cameraQuaternion(base[0], classroomMode ? 75 : base[1]).invert());
    card.orbit.polar = card.basePolar;
    const sourceBounds = new THREE.Box3().setFromObject(raw);
    const aligned = new THREE.Group(); aligned.add(raw); aligned.quaternion.copy(card.baseRotation);
    const bounds = new THREE.Box3().setFromObject(aligned);
    if (!classroomMode && card.item.comparison_subject_bounds) {
      // Frame the subjects above the generated floor without altering the mesh.
      const subject = new THREE.Box3(), point = new THREE.Vector3(), sourcePoint = new THREE.Vector3();
      const unrotate = card.baseRotation.clone().invert();
      const floorCut = sourceBounds.min.y + (sourceBounds.max.y - sourceBounds.min.y) * 0.12;
      aligned.updateWorldMatrix(true, true);
      raw.traverse(mesh => {
        if (!mesh.isMesh) return;
        const positions = mesh.geometry.attributes.position;
        for (let i = 0; i < positions.count; i++) {
          point.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld);
          sourcePoint.copy(point).applyQuaternion(unrotate);
          if (sourcePoint.y > floorCut) subject.expandByPoint(point);
        }
      });
      if (!subject.isEmpty()) {
        bounds.copy(subject);
      }
    }
    const extent = bounds.getSize(new THREE.Vector3()), center = bounds.getCenter(new THREE.Vector3());
    const longest = Math.max(extent.x, extent.y, extent.z);
    if (!Number.isFinite(longest) || longest <= 0) {disposeScene(aligned); throw Error('模型边界无效');}
    const scale = 2.4 / longest;
    card.framingExtent = extent.clone().multiplyScalar(scale);
    aligned.scale.setScalar(scale); aligned.position.copy(center).multiplyScalar(-scale);
    card.pivot.add(aligned); card.model = raw;
    // Bake display-space coordinates once: grain stays attached during rotation,
    // with consistent density across provider units and transformed submeshes.
    aligned.updateWorldMatrix(true, true);
    raw.traverse(o => {
      if (!o.isMesh) return;
      const surfacePosition = o.geometry.attributes.position.clone();
      surfacePosition.applyMatrix4(o.matrixWorld);
      o.geometry.setAttribute('surfacePosition', surfacePosition);
    });
    applySurface(card);
    card.floorBase = -(extent.y * scale / 2) - 0.015;
    card.floor.position.y = card.floorBase;
    card.ready = true;
    $('.loading', card.el).hidden = true;
    $('.case-status', card.el).textContent = '可交互'; $('.case-status', card.el).classList.add('ready');
    card.el.dataset.loaded = 'true';
    requestRender();
  } catch (error) {
    if (token !== revision || error.name === 'AbortError') return;
    $('.loading', card.el).classList.add('error');
    $('.loading-text', card.el).textContent = error.message;
    $('.case-status', card.el).textContent = '读取失败';
    card.el.dataset.error = error.message;
  }
}

// The marker is the camera projection of the actual light, not a second angle-to-pixel mapping.
function projectLight(position, camera) {
  camera.updateMatrixWorld();
  const p=position.clone().project(camera);
  return {x:(p.x+1)/2,y:(1-p.y)/2,visible:p.z>=-1 && p.z<=1};
}
function dragLightPosition(x,y,camera,planePoint) {
  camera.updateMatrixWorld();
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(x*2-1,1-y*2),camera);
  const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()),planePoint);
  return ray.ray.intersectPlane(plane,new THREE.Vector3());
}
function updateLightMarker(card) {
  if (!card.lamp) return;
  const p=projectLight(card.light.position,card.camera);
  card.lamp.hidden=!p.visible;
  card.lamp.style.left=`${p.x*100}%`;card.lamp.style.top=`${p.y*100}%`;
  card.lamp.setAttribute('aria-label',classroomEnglish?'Drag light. Arrow keys adjust direction and height.':'移动光源，方向键调整光源方向和高度');
}
function setLight(card) {
  const az = radians(Number($('#light-azimuth').value)), el = radians(Number($('#light-elevation').value));
  const radius=card.lightRadius || 5;
  card.light.position.set(radius * Math.cos(el) * Math.sin(az), radius * Math.sin(el), radius * Math.cos(el) * Math.cos(az));
  materials.metal.envMapRotation.y = az;
  card.floor.visible = $('#ground').checked;
  card.light.castShadow = $('#ground').checked;
  if (!card.light.castShadow && card.light.shadow.map) {
    card.light.shadow.map.dispose(); card.light.shadow.map = null;
  }
  card.light.shadow.needsUpdate = true;
  updateLightMarker(card);
}

function changeOrbit(card, yaw, polar, zoom) {
  const targets = $('#sync').checked ? cards : [card];
  for (const c of targets) {
    c.orbit.yaw += yaw; c.orbit.polar = THREE.MathUtils.clamp(c.orbit.polar + polar, 12, 168);
    c.orbit.zoom = THREE.MathUtils.clamp(c.orbit.zoom * zoom, 0.45, 2.5);
  }
  requestRender();
}

function focusCard(card) {
  const focused = card && !card.el.classList.contains('focused-card');
  $('#cards').classList.toggle('focused', Boolean(focused));
  cards.forEach(c => c.el.classList.toggle('focused-card', focused && c === card));
  $('#exit-focus').hidden = !focused; requestRender();
}

function createCard(item, i) {
  const el = $('#model-card').content.firstElementChild.cloneNode(true);
  const slot = renderSlots[i] ||= {scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(36, 1, 0.05, 80), target: new THREE.WebGLRenderTarget(1, 1, {type: THREE.HalfFloatType})};
  const {scene, camera} = slot; scene.environment = null;
  const pivot = new THREE.Group();
  const light = studyMode ? new THREE.PointLight(0xfff9ef,8,0,2) : new THREE.DirectionalLight(0xfff9ef, 2.7);
  light.shadow.mapSize.set(1024, 1024); light.shadow.camera.left = light.shadow.camera.bottom = -3;
  light.shadow.camera.right = light.shadow.camera.top = 3; light.shadow.camera.near = 0.1; light.shadow.camera.far = 12;
  light.shadow.normalBias = 0.02; light.shadow.bias = -0.00015;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.MeshStandardMaterial({color: 0xe4dfd6, roughness: 1}));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true;
  scene.add(pivot, light, new THREE.HemisphereLight(0xffffff, 0x8c8174, studyMode?0.45:1.2), floor);
  const backdrop = new THREE.Group();
  for (let n=0; n<16; n++) {
    const stripe = new THREE.Mesh(new THREE.PlaneGeometry(0.5,6), new THREE.MeshBasicMaterial({color: n % 2 ? 0xf5f1e8 : 0xcbd4d7}));
    stripe.position.set(n*0.5-3.75,0,-2.2); backdrop.add(stripe);
  }
  backdrop.visible = false; scene.add(backdrop);
  const sphere = new THREE.Mesh(new THREE.SphereGeometry(1.1, 64, 40), materials[$('#material').value]);
  sphere.geometry.setAttribute('surfacePosition', sphere.geometry.attributes.position.clone());
  sphere.visible = false; sphere.castShadow = sphere.receiveShadow = true; scene.add(sphere);
  const initialZoom = classroomMode ? 0.8 : 1;
  const card = {item, el, scene, pivot, camera, light, floor, backdrop, sphere, target: slot.target, viewport: $('.viewport', el), initialZoom, orbit: {yaw: 0, polar: 75, zoom: initialZoom}, ready: false};
  if (studyMode) {
    card.lightRadius=1.5;
    const lamp=document.createElement('button'); lamp.type='button'; lamp.className='study-lamp';
    lamp.innerHTML='<span></span>';
    $('span',lamp).textContent=classroomEnglish?'Drag light':'拖动光源';
    card.lamp=lamp; card.viewport.append(lamp);
    let pointer=null, dragPlanePoint=null;
    const move=e=>{
      const rect=card.viewport.getBoundingClientRect();
      const position=dragLightPosition((e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height,card.camera,dragPlanePoint);
      if(!position)return;
      position.y=Math.max(.15,position.y);card.lightRadius=Math.max(.3,position.length());
      $('#light-azimuth').value=THREE.MathUtils.radToDeg(Math.atan2(position.x,position.z));
      $('#light-elevation').value=THREE.MathUtils.radToDeg(Math.asin(position.y/card.lightRadius));
      for (const id of ['light-azimuth','light-elevation']) $(`#${id}`).oninput();
    };
    lamp.onpointerdown=e=>{if(e.button!==0)return;e.stopPropagation();pointer=e.pointerId;dragPlanePoint=card.light.position.clone();lamp.classList.add('is-dragging');lamp.setPointerCapture(pointer);auto=false;$('#auto').setAttribute('aria-pressed','false');};
    lamp.onpointermove=e=>{if(pointer===e.pointerId){e.stopPropagation();move(e);}};
    lamp.onpointerup=lamp.onpointercancel=lamp.onlostpointercapture=()=>{pointer=null;lamp.classList.remove('is-dragging');};
    lamp.onkeydown=e=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
      e.preventDefault();e.stopPropagation();
      const id=['ArrowLeft','ArrowRight'].includes(e.key)?'light-azimuth':'light-elevation';
      const input=$(`#${id}`); input.value=Number(input.value)+(['ArrowRight','ArrowUp'].includes(e.key)?5:-5); input.oninput();
    };
  }
  el.dataset.model = item.model;
  $('h2', el).textContent = item.name; $('.model-number', el).textContent = `MODEL / 0${i + 1}` + (item.model === 'trellis2' ? ' · 课堂现用' : item.model === 'pixal' ? ' · 已归档' : '');
  card.viewport.setAttribute('aria-label', `${item.name} 三维视图，拖动或方向键旋转，滚轮缩放`);
  $('.finding', el).textContent = item.note;
  $('.time', el).textContent = item.generation_seconds == null ? '—' : `${item.generation_seconds.toFixed(1)} 秒`;
  $('.time', el).title = `生成处理时间；本次等待 ${item.wait_seconds?.toFixed(1) ?? '未知'} 秒${item.remesh_seconds ? `，另减面 ${item.remesh_seconds.toFixed(1)} 秒` : ''}`;
  $('.weight', el).textContent = item.bytes ? `${(item.bytes / 1e6).toFixed(2)} MB` : '—';
  $('.faces', el).textContent = item.triangles ? `${(item.triangles / 1e4).toFixed(1)} 万` : '—';
  $('.processing', el).textContent = item.processing.replace('仅显示时改为哑光', '实时材质预览') + (item.reused ? ' · 同图记录复用' : ' · 本轮生成');
  const display = $('.download-display', el), original = $('.download-original', el);
  if (item.asset) display.href = item.asset; else display.hidden = true;
  if (item.original_download) {
    original.href = item.original_download;
    original.title = `原始文件 ${(item.original_file_bytes / 1e6).toFixed(1)} MB`;
  } else original.hidden = true;
  $('.focus-button', el).onclick = () => focusCard(card);
  card.viewport.ondblclick = e => {if (e.target === card.viewport) focusCard(card);};
  let drag;
  card.viewport.onpointerdown = e => {
    if (e.target.closest('button') || e.button !== 0) return;
    drag = [e.clientX, e.clientY]; card.viewport.setPointerCapture(e.pointerId); card.viewport.focus({preventScroll: true});
  };
  card.viewport.onpointermove = e => {
    if (!drag) return;
    if (classroomMode && studyInteraction === 'light') {
      $('#light-azimuth').value=Number($('#light-azimuth').value)+(e.clientX-drag[0])*.5;
      $('#light-elevation').value=Number($('#light-elevation').value)-(e.clientY-drag[1])*.3;
      $('#light-azimuth').oninput();$('#light-elevation').oninput();
    } else changeOrbit(card, -(e.clientX - drag[0]) * 0.4, -(e.clientY - drag[1]) * 0.3, 1);
    drag = [e.clientX, e.clientY];
  };
  card.viewport.onpointerup = card.viewport.onpointercancel = card.viewport.onlostpointercapture = () => {drag = null;};
  card.viewport.addEventListener('wheel', e => {e.preventDefault(); changeOrbit(card, 0, 0, Math.exp(THREE.MathUtils.clamp(e.deltaY, -150, 150) * 0.002));}, {passive: false});
  card.viewport.onkeydown = e => {
    const keys = {ArrowLeft: [-8, 0], ArrowRight: [8, 0], ArrowUp: [0, -6], ArrowDown: [0, 6]};
    if (keys[e.key]) {e.preventDefault(); changeOrbit(card, ...keys[e.key], 1);}
    if (e.key === 'Home') {e.preventDefault(); reset();}
  };
  $('.align-button', el).onclick = () => {$('.align-panel', el).hidden = !$('.align-panel', el).hidden; requestRender();};
  const align = () => {pivot.rotation.set(radians(Number($('.align-pitch', el).value)), radians(Number($('.align-yaw', el).value)), 0, 'YXZ'); light.shadow.needsUpdate = true; requestRender();};
  $('.align-yaw', el).oninput = $('.align-pitch', el).oninput = align;
  $('.align-reset', el).onclick = () => {$('.align-yaw', el).value = $('.align-pitch', el).value = '0'; align();};
  setLight(card); $('#cards').append(el); return card;
}

function reset() {
  auto = false; $('#auto').setAttribute('aria-pressed', 'false');
  for (const c of cards) {
    c.orbit = {yaw: 0, polar: c.basePolar || 75, zoom: c.initialZoom || 1};
    c.pivot.rotation.set(0, 0, 0);
    $('.align-yaw', c.el).value = $('.align-pitch', c.el).value = '0';
  }
  requestRender();
}

async function selectSample(id) {
  const token = ++revision;
  abort?.abort(); abort = new AbortController(); const signal = abort.signal;
  cards.forEach(c => disposeScene(c.scene)); cards = []; renderer.renderLists.dispose();
  $('#cards').replaceChildren(); $('#cards').classList.remove('focused'); $('#exit-focus').hidden = true;
  selected = id; reset();
  const sample = manifest.samples.find(s => s.id === id);
  $('#original-image').src = sample.image;
  for (const button of $('#sample-tabs').children) {button.setAttribute('aria-selected', String(button.dataset.sample === id)); button.tabIndex = button.dataset.sample === id ? 0 : -1;}
  cards = sample.cases.map(createCard); const batch = cards.slice();
  requestRender();
  // Serialize parsing even across rapid tab switches, avoiding overlapping mesh allocations.
  loadingChain = loadingChain.catch(() => {}).then(async () => {
    for (const c of batch) {if (token !== revision) return; await loadCard(c, token, signal);}
  });
  await loadingChain;
}

function requestRender() {if (!frame && !document.hidden) frame = requestAnimationFrame(render);}
function render(now) {
  frame = 0;
  if (document.hidden) return;
  if (auto && now - lastFrame < 33) {requestRender(); return;}
  const dt = Math.min((now - lastFrame) / 1000, 0.05); lastFrame = now;
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const dpr = Math.min(devicePixelRatio, 1.25, Math.sqrt(3000000 / (width * height)));
  if (renderer.getPixelRatio() !== dpr) renderer.setPixelRatio(dpr);
  const size = renderer.getSize(new THREE.Vector2());
  if (size.x !== width || size.y !== height) renderer.setSize(width, height, false);
  renderer.setScissorTest(false); renderer.clear(); renderer.setScissorTest(true); renderer.info.reset();
  renderer.shadowMap.enabled = $('#ground').checked;
  for (const c of cards) {
    const rect = c.viewport.getBoundingClientRect();
    if (auto) c.orbit.yaw += dt * 12;
    if (!c.ready || rect.width === 0 || rect.bottom < 0 || rect.top > height) continue;
    const w = rect.width, h = rect.height;
    const standard = $('#sphere-test').checked;
    c.pivot.visible = !standard; c.sphere.visible = standard;
    c.floor.position.y = standard ? -1.115 : c.floorBase;
    $('.view-caption', c.el).textContent = standard ? '标准球体 · 非 AI 输出' : classroomEnglish ? 'Drag to rotate' : '拖动旋转';
    c.camera.aspect = w / h; c.camera.updateProjectionMatrix();
    const distance = (classroomMode && c.framingExtent ? fittedDistance(c.framingExtent,c.camera.aspect) : Math.max(4.8, 4.2 / c.camera.aspect)) * c.orbit.zoom;
    c.camera.position.setFromSphericalCoords(distance, radians(c.orbit.polar), radians(c.orbit.yaw)); c.camera.lookAt(origin);
    updateLightMarker(c);
    const tw = Math.max(1, Math.round(w * dpr)), th = Math.max(1, Math.round(h * dpr));
    if (c.target.width !== tw || c.target.height !== th) c.target.setSize(tw, th);
    renderer.setRenderTarget(c.target);
    renderer.setScissorTest(false);
    renderer.setClearColor(0xf2efe9, 1); renderer.clear();
    renderer.render(c.scene, c.camera);
    renderer.setRenderTarget(null);
    renderer.setViewport(rect.left, height - rect.bottom, w, h);
    renderer.setScissorTest(true);
    renderer.setScissor(Math.max(0, rect.left), Math.max(0, height - rect.bottom), Math.min(w, width - rect.left), Math.min(h, height - Math.max(0, rect.top)));
    compositeMaterial.map = c.target.texture;
    renderer.render(compositeScene, compositeCamera);
    c.viewport.dataset.orbit = [c.orbit.yaw, c.orbit.polar, c.orbit.zoom].map(n => n.toFixed(2)).join(',');
  }
  renderer.setClearColor(0x000000, 0);
  // Read-only DOM counters for repeatable browser QA, without retaining scene objects globally.
  canvas.dataset.geometries = renderer.info.memory.geometries;
  canvas.dataset.textures = renderer.info.memory.textures;
  canvas.dataset.triangles = renderer.info.render.triangles;
  canvas.dataset.loaded = cards.filter(c => c.ready).length;
  canvas.dataset.sample = selected;
  if (auto) requestRender();
}

async function refresh() {
  const response = await fetch('manifest.json', {cache: 'no-store'}); if (!response.ok) throw Error('无法读取比较记录');
  manifest = await response.json();
  $('#progress').textContent = `${manifest.raw_ready} 份已生成 · ${manifest.ready} 份可交互`;
  $('#sample-tabs').replaceChildren();
  manifest.samples.forEach((sample, i) => {
    const button = document.createElement('button'); button.type = 'button'; button.role = 'tab'; button.dataset.sample = sample.id;
    const image = document.createElement('img'); image.src = sample.image; image.alt = '';
    const labels = document.createElement('span'), number = document.createElement('span'), label = document.createElement('span');
    number.className = 'sample-number'; number.textContent = `SKETCH / 0${i + 1}`; label.textContent = sample.label;
    labels.append(number, label); button.append(image, labels);
    button.onclick = () => selectSample(sample.id);
    button.onkeydown = e => {
      if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault(); const next = (i + (e.key === 'ArrowRight' ? 1 : 2)) % 3;
        selectSample(manifest.samples[next].id); $('#sample-tabs').children[next].focus();
      }
    };
    $('#sample-tabs').append(button);
  });
  await selectSample(selected);
}

$('#reset').onclick = reset;
$('#exit-focus').onclick = () => focusCard(null);
$('#auto').onclick = () => {auto = !auto; $('#auto').setAttribute('aria-pressed', String(auto)); requestRender();reportStudyState();};
$('#sync').onchange = () => {if ($('#sync').checked && cards[0]) cards.forEach(c => c.orbit = {...cards[0].orbit}); requestRender();};
$('#material').onchange = () => {
  document.querySelectorAll('[data-exhibit-material]').forEach(button =>
    button.setAttribute('aria-pressed', String(button.dataset.exhibitMaterial === $('#material').value)));
  cards.forEach(applySurface); requestRender();reportStudyState();
};
const exhibitChoices = $('#exhibit-materials');
if (exhibitChoices) for (const option of $('#material').options) {
  const button = document.createElement('button'); button.type = 'button';
  button.dataset.exhibitMaterial = option.value; button.textContent = option.textContent;
  button.setAttribute('aria-pressed', String(option.value === $('#material').value));
  button.onclick = () => {$('#material').value = option.value; $('#material').onchange();};
  exhibitChoices.append(button);
}
$('#sphere-test').onchange = () => {cards.forEach(c => c.light.shadow.needsUpdate = true); requestRender();};
$('#grayscale').onchange = () => {canvas.classList.toggle('grayscale', $('#grayscale').checked);reportStudyState();};
$('#wood-grain').oninput = () => {grainStrength.value = Number($('#wood-grain').value) / 100; $('#wood-value').textContent = grainStrength.value ? `${$('#wood-grain').value}%` : classroomEnglish ? 'Off' : '关闭'; requestRender();};
$('#lighting-toggle').onclick = () => {$('#lighting').hidden = !$('#lighting').hidden; $('#lighting-toggle').setAttribute('aria-expanded', String(!$('#lighting').hidden)); requestRender();};
for (const id of ['light-azimuth', 'light-elevation', 'ground']) {
  $(`#${id}`).oninput = () => {
    if (id !== 'ground') $(`#${id}-value`).textContent = $(`#${id}`).value + '°';
    cards.forEach(setLight); requestRender();reportStudyState();
  };
}
$('#view-original').onclick = () => $('#original-dialog').showModal();
$('#close-original').onclick = () => $('#original-dialog').close();
$('#refresh').onclick = () => refresh().catch(e => {$('#progress').textContent = e.message;});
document.addEventListener('keydown', e => {if (e.key === 'Escape') focusCard(null);});
document.addEventListener('visibilitychange', () => {if (document.hidden) {cancelAnimationFrame(frame); frame = 0;} else requestRender();});
window.addEventListener('resize', requestRender);
window.addEventListener('scroll', requestRender, {passive: true});
canvas.addEventListener('webglcontextlost', e => {e.preventDefault(); auto = false; $('#progress').textContent = '图形资源已释放，请刷新页面重新加载';});
new ResizeObserver(requestRender).observe($('#cards'));
if (classroomMode) {
  let received = false;
  window.addEventListener('message', async event => {
    if (event.source !== parent || event.origin !== location.origin) return;
    if (event.data?.type === 'study-control') {
      if (!received || !cards[0]?.ready) return;
      const {action,value}=event.data;
      if (action==='mode' && ['orbit','light'].includes(value)) {
        studyInteraction=value;
        if(value==='light' && auto) $('#auto').click();
      }
      else if (action==='reset') reset();
      else if (action==='auto') $('#auto').click();
      else if (action==='zoom' && Number.isFinite(value)) {cards[0].orbit.zoom=THREE.MathUtils.clamp(cards[0].orbit.zoom*(value>0?.9:1.1),.4,2.5);requestRender();}
      else if (action==='material' && Object.hasOwn(materials,value)) {$('#material').value=value;$('#material').onchange();}
      else if (action==='grayscale' && typeof value==='boolean') {$('#grayscale').checked=value;$('#grayscale').onchange();}
      else if (action==='ground' && typeof value==='boolean') {$('#ground').checked=value;$('#ground').oninput();}
      else if (action==='direction' && Number.isFinite(value)) {$('#light-azimuth').value=THREE.MathUtils.clamp(value,-180,180);$('#light-azimuth').oninput();}
      else if (action==='elevation' && Number.isFinite(value)) {$('#light-elevation').value=THREE.MathUtils.clamp(value,10,85);$('#light-elevation').oninput();}
      reportStudyState();return;
    }
    if (event.data?.type === 'snapshot') {
      render(performance.now());
      const rect = cards[0]?.viewport.getBoundingClientRect();
      if (!rect) return;
      const shot = document.createElement('canvas'), scale = renderer.getPixelRatio();
      shot.width = Math.round(rect.width * scale); shot.height = Math.round(rect.height * scale);
      shot.getContext('2d').drawImage(canvas, rect.left * scale, rect.top * scale, shot.width, shot.height, 0, 0, shot.width, shot.height);
      shot.toBlob(blob => parent.postMessage({type:'snapshot', blob}, location.origin), 'image/png');
      return;
    }
    if (event.data?.type !== 'classroom-scene' || received) return;
    received = true;
    document.body.classList.add('studio-embedded');
    try {
      classroomEnglish = event.data.language === 'en';
      if (classroomEnglish) {
        const ui = await import('./classroom-ui.js'); surfaceEnglish = ui.surfaceEnglish; ui.localizeClassroom();
      }
      const scene = event.data.scene;
      const choices = $('#material-options');
      for (const option of $('#material').options) {
        const button = document.createElement('button'); button.type='button';
        button.dataset.classroomMaterial=option.value; button.textContent=option.textContent;
        button.setAttribute('aria-pressed', String(option.value === 'plaster'));
        button.onclick=()=>{$('#material').value=option.value; $('#material').onchange();};
        choices.append(button);
      }
      let item;
      if (scene.method !== 'cloud-glb') {
        if (!solidScene(scene)) throw Error('模型数据无效');
        // Open from the angle the drawing was read at, as [yaw, polar]; the model stays upright (loadCard).
        item = {model:'solids', name:'立体作品', status:'ready', solids:scene,
          camera_base:[scene.camera.azimuth, 90 - scene.camera.elevation], note:'', processing:'', reused:false};
      } else {
      if (!['trellis2','pixal'].includes(scene.model) || typeof scene.glb !== 'string' || scene.glb.length > 24 * 1024 * 1024) throw Error('模型数据无效');
      const bytes = Uint8Array.from(atob(scene.glb), c => c.charCodeAt(0));
      const buffer = await checkedBuffer(bytes.buffer, scene);
      // Reuse the exact asset's curated orientation; a provider does not have one universal front.
      let catalog = {};
      try {
        const response = await fetch('manifest.json', {cache:'no-store'});
        if (response.ok) catalog = await response.json();
      } catch (_) { /* New classroom assets still use the provider fallback. */ }
      item = {model:scene.model, name:scene.model === 'pixal'?'Pixal3D':'TRELLIS.2', status:'ready', buffer,
        bytes:scene.bytes, sha256:scene.sha256, triangles:scene.triangles, camera_base:calibratedBase(scene,catalog),
        note:'', processing:'', reused:false};
      }
      $('#reset').textContent=scene.camera_calibration?.status==='teacher'?'返回保存角度':'返回初始角度';
      const original = event.data.image;
      if (typeof original !== 'string' || !(original.startsWith('data:image/') || original.startsWith('blob:') || original.startsWith(location.origin + '/'))) throw Error('原图地址无效');
      manifest = {samples:[{id:'portrait', image:original, cases:[item]}]};
      $('#material').value='plaster'; $('#ground').checked=true; $('#lighting').hidden=false;
      $('#lighting-toggle').setAttribute('aria-expanded','true');
      await selectSample('portrait');
      if (!cards[0]?.ready) throw Error('模型加载失败');
      $('#progress').textContent = item.name;
      parent.postMessage({type:'scene-ready'}, location.origin);
      reportStudyState();
    } catch (error) {$('#progress').textContent='模型无法显示，请关闭后重试'; parent.postMessage({type:'scene-error'}, location.origin);}
  });
} else refresh().catch(e => {$('#progress').textContent = e.message;});
window.addEventListener('pagehide', event => {
  if (event.persisted) return;
  abort?.abort(); cancelAnimationFrame(frame);
  cards.forEach(card => disposeScene(card.scene));
  renderSlots.forEach(slot => slot.target.dispose());
  scans.dispose();
  Object.values(materials).forEach(material => material.dispose());
  studioEnvironment?.dispose(); metalEnvironment?.dispose(); steelEnvironment?.dispose();
  renderer.dispose(); renderer.forceContextLoss();
});
