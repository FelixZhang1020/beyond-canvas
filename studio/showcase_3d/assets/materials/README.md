# Scanned surfaces

Official Poly Haven CC0 assets, downloaded as unmodified 1K PNGs. Exact URLs,
byte counts and SHA-256 checksums are in sources.json.

- Oak Veneer 01 — Jenelle van Heerden: https://polyhaven.com/a/oak_veneer_01
- Denim Fabric — Rob Tuytel: https://polyhaven.com/a/denim_fabric
- Rust Coarse 01: https://polyhaven.com/a/rust_coarse_01
- Asset license: https://polyhaven.com/license

Runtime uses diffuse, roughness and displacement-as-bump (not geometric
 displacement). Color is sRGB; roughness and height are non-color data.
No preview renders are redistributed. Nine original files total about 23 MiB.
Only a selected material loads its three files; textures are shared by cards
and released on viewer disposal. Loading failure retains the base material
and displays an explicit status. Reload the viewer to retry.

Three-axis projection uses the existing fixed display-space surface coordinates;
no mesh UVs are required. Projection transitions blend instead of creating hard
UV seams, but directional wood/fabric patterns can cross-fade unnaturally.
Scale is tuned for classroom display, not measured object size. Denim samples
a seam-free crop (x 0.50–0.85, y 0.10–0.45) with mirrored repetition; source PNGs
remain unchanged. No cloth deformation, internal scattering or original GLB
export changes are included. Height gradients replace tangent-space normal maps to
avoid incorrectly oriented normals across projection axes.

Browser check: saved classroom geometric solids displayed all three scanned
materials. Unit controls cover one-time loading, color/data distinction,
cleanup, failed loading fallback, and existing coordinate scale behavior.
Follow-up browser check on the saved TRELLIS.2 portrait: the denim seam grid
is no longer conspicuous; marble has soft mineral streaks, and reduced plaster
bump removes the sandy appearance. Fine plaster grain remains subtle at normal
viewing distance. This is visual inspection, not a photorealism or long-running
memory certification; directional projection and repeating crops remain limits.

Denim follow-up: square crop preserves source aspect ratio. Continuous procedural
diagonal yarn detail supplements the 1K scan in color and shallow bump, with
screen-derivative filtering at distance. Three-axis blending can still alter
weave direction on curved surfaces; this does not simulate garment construction.
Browser portrait close-up shows diagonal weave on forehead, cheek and base.

The initial continuous diagonal relief was rejected in a user close-up as
embossed rather than woven. It is superseded by fine 3-over/1-under yarn
crossings with much lower relief and weak cloth sheen. Geometry browser check
confirms coarse ridges are gone; scanned color mottling remains visible.
