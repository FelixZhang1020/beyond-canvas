// Classroom strings; the historical exhibit keeps its original Chinese labels.
export const surfaceEnglish = {
  matte:'Matte shading for observing the form.', plaster:'Plaster: chalk white with fine powder grains, shallow pores and a dry matte finish.',
  marble:'White marble: soft ivory stone with faint mineral clouds and a satin sheen.',
  wood:'Oak: scanned wood grain and fine surface relief; adjustable texture strength.',
  denim:'Denim: blue woven fabric; the texture does not change the model shape.',
  rust:'Rusted iron: reddish-brown oxide and a rough surface.',
  metal:'Light stainless steel: silver reflections and soft highlights; move the light to explore reflections and shadows.',
  glass:'Glass: move the light to explore highlights, shading and a faint shadow. Transmitted shadows are approximate; no caustics.',
  chocolate:'Chocolate: deep brown with a soft sheen; no subsurface scattering.',
  normal:'Surface directions: orientation colours with light shading and shadows.', wire:'Triangle mesh.'
};
export function localizeClassroom() {
  document.documentElement.lang='en';
  const labels={'查看原画':'Original drawing','重置视角':'Reset view','自动旋转':'Auto rotate','显示':'Material','材质':'Material','视角':'View',
    '调整光源':'Lighting','灰度观察':'Grayscale','灰度':'Grayscale','细木纹':'Wood grain','光源方向':'Light direction','光源高度':'Light height',
    '显示地面与投影':'Ground and shadows','哑光形体':'Matte','石膏':'Plaster','大理石':'Marble','木头':'Wood','牛仔布':'Denim','锈铁':'Rusted iron','金属':'Metal','玻璃':'Glass',
    '巧克力':'Chocolate','表面朝向':'Normals','三角网格':'Wireframe','关闭 ×':'Close ×'};
  const walker=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
  let node;while(node=walker.nextNode()){const word=node.textContent.trim();if(labels[word])node.textContent=labels[word];}
  document.querySelector('#close-original').textContent='Close ×';
  document.querySelector('#material-options').setAttribute('aria-label','Material');
  document.querySelector('#close-original').setAttribute('aria-label','Close original');
}
