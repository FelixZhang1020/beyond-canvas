# Skill card: painting-to-animation

| Field | Value |
|---|---|
| Description | One short Wan 2.2 video preview of a child's drawing, made from the original and screened before the teacher sees it. |
| Owner | spark-art-studio team |
| License | Apache-2.0 |
| Use case | A teacher turns the child's confirmed words about what should move into a short clip and compares it with the original. |
| Deployment geography | Chinese and English classroom UI; the clip is made on the hosted DGX Spark. |
| Requirements | video.animation, Python 3.13, Pillow, ffmpeg, httpx and a browser. |
| Known risks | May move the wrong subject or redraw marks. A person's hands, a person or an art tool painted into the clip is checked for and held back (caught 2 of 2, one false alarm in 34 good clips); other additions such as extra figures are not checked, and the check is a model's reading of five frames. A 5-second clip takes about 18 minutes on the Spark. |
| References | ../../docs/measured/animation-model-bakeoff.md; ../../docs/deployment-versions.md |
| Skill output | Embedded H.264 MP4, at most 10 seconds; no still picture (retired) and no choreography. |
| Skill version | 0.6 |
| Ethical considerations | Original retained for comparison; generated output explicitly labelled. Input and output safety gates remain. Class end drops drawings, cached outputs and response streams. |
