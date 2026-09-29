# 开课入口插画

彩画和素描卡片中的两张图例由图像模型生成，无外部参考图、无真实儿童作品。
彩画采用暖纸色上的水粉／粉彩花园；素描采用同一纸色上的石膏几何体与梨的铅笔静物。
两张均为 3:2 构图，作为入口装饰；卡片标题与说明仍由页面提供。

| 用途 | 生成原图（1536 × 1024） | 网页版本（960 × 640） |
|---|---|---|
| 彩画 | [colour-painting.png](colour-painting.png) | [colour-painting.jpg](colour-painting.jpg) |
| 素描 | [sketch-study.png](sketch-study.png) | [sketch-study.jpg](sketch-study.jpg) |

网页版本仅缩小并转为 JPEG（质量 85），未修改画面内容。`src/10-app.html` 引用 JPEG；
`build.sh` 在构建时将其内嵌，正式服务和示例预览都不依赖额外图片路由。
修改素材后在 Spark 上重新生成页面：`sh deploy/spark/test-on-spark.sh sh studio/page/build.sh`。

验证：构建结构检查通过，两张内嵌图片与网页 JPEG 文件一致；在隔离副本中确认缺失引用会使构建失败。
本机示例页面已检查 1024 × 768 与 390 × 844 排布，图片完整加载，窄屏无横向溢出。

## 彩画生成提示词

```text
Use case: illustration-story.
Asset type: the colour-painting entrance illustration for a warm, elegant children's art classroom web app, a pair with a graphite still-life illustration. Generate one finished standalone image, landscape 3:2.
Primary request: a beautiful expressive hand-painted children's story scene: a small lavender bird with an orange beak in a garden of oversized coral and buttery-yellow flowers, a little coral-roofed house tucked behind foliage, a small warm sun. A handful of subjects with a clear central focal point and generous breathing room.
Style/medium: sophisticated children's picture-book illustration in gouache, wax pastel and coloured pencil on warm ivory paper, charming slightly irregular handmade contours, visible pigment grain, layered brush marks, tactile natural art materials. Designed by an excellent illustrator, playful and approachable.
Composition/framing: flat artwork viewed straight on, central scene occupies roughly 75 percent of image width and 75 percent of height, quiet edges and enough space around every subject to fit a UI card without cutting anything off. Artwork only; no photographed desk, no paper border, no frame.
Color palette: warm ivory background close to #fffdf9; lavender, dusty coral, soft sage green, butter yellow, a little muted teal. Cheerful yet restrained; fine paper texture and edges fade softly into the light paper.
Constraints: absolutely no text, lettering, logo, watermark, UI, buttons, labels, palette or drawing tools. No glossy 3D, no stock vector clipart, no geometric stick figures, no neon, no photorealism. Make the painting inviting and visibly handcrafted. This is an illustration for a selection card, not a complete interface screenshot.
```

## 素描生成提示词

```text
Use case: illustration-story.
Asset type: the sketch-study entrance illustration for a warm, elegant children's art classroom web app, a pair with a gouache/pastel garden illustration. Generate one finished standalone image, landscape 3:2.
Primary request: an exquisitely observed, approachable graphite pencil still-life study showing a matte plaster sphere to the left, a simple plaster cube set slightly behind to the right, and a ripe pear with a short stem at the front right, all grounded on the same surface. Only these three subjects.
Style/medium: authentic graphite drawing on warm ivory fine-grain drawing paper. Visible delicate construction marks, expressive layered pencil hatching following the volume, nuanced soft shading and occasional darker contour accents. A beautifully composed art-school sketch, human and tactile.
Composition/framing: straight-on view slightly above the objects, coherent perspective, compact central composition occupying about 70 percent of width and 65 percent of height, generous empty paper around it, shadows entirely in frame. Soft single light from upper left, clear light planes and rounded volumes, believable contact shadows cast gently lower-right.
Color palette: monochrome warm graphite gray, charcoal darks used sparingly; warm ivory paper background close to #fffdf9 to match its companion artwork. Fine paper texture and drawing fade naturally into quiet unmarked edges.
Constraints: artwork only, absolutely no text, labels, arrows, signature, watermark, logo, UI, border, frame, photographed sheet, desk, pencils or tools. No purple cartoon outline, no flat icon, no vector art, no digital gradient sphere, no photorealistic 3D render. This must unmistakably look like a beautiful hand-drawn pencil study, not a complete interface screenshot.
```
