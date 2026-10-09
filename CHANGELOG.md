# Changelog

Notable changes to Beyond Canvas. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## 0.1.0

The first public release, entered in the third NVIDIA DGX Spark Hackathon (Agent Skills).

### Added

- **The classroom.** A teacher-operated page with the course Portfolio as its home screen; a sketch
  entrance and a colour entrance; warm, specific feedback on each drawing and one question for the
  teacher to put to the child; a plain chat about the drawing, every reply checked before it is shown.
- **Things made from a drawing:** a short animated clip (Wan 2.2 I2V A14B on the DGX Spark, or a hosted
  Wan clip when the teacher chooses it), a 3D study with movable light (TRELLIS.2), a small 3D toy figure
  of a colour painting, and a storybook of the child's originals or of pages redrawn in one of seven
  picture-book styles, read aloud page by page.
- **Six classroom Agent Skills:** `studio-safety`, `art-feedback`, `painting-to-animation`,
  `painting-to-figure`, `sketch-to-3d`, `drawings-to-storybook`.
- **Agentic 3D:** seven Agent Skills (`model-anatomy`, `shot-judge`, `joint-reveal`, `structure-tour`,
  `raise-the-hall`, `load-path`, `hall-carpenter`) with which a model rebuilds the East Hall of Foguang
  Temple from an empty file in Blender, accepted only after a seven-check hand-over gate.
- **The harness:** a fixed route in class — safety, Skill, quality gate, ledger — with one retry, then
  repair, then stop; slots and profiles so that no Skill names a vendor.
- **Evaluation:** fourteen teaching rules, model-assisted judging, Skill-versus-bare-model benchmarks,
  packaging checks against NVIDIA's release format, and OpenSSF Model Signing for every Skill folder.
- **Deployment on the DGX Spark:** the studio, its models and NVIDIA Nemotron 3.5 Content Safety run on
  the box behind one class password; the evidence for every measured claim is in `docs/measured/`.
