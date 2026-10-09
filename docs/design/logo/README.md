# The Beyond Canvas logo

Splat beside the hand lettering, chosen by the operator from six crayon options
(option A). Both are cut straight out of the video's first and last frames,
[opening.png](../video-cards/opening.png) and [closing.png](../video-cards/closing.png), so the logo
is the same drawing the videos show. `python3 docs/design/logo/make_logo.py` remakes every file into
[studio/page/assets/brand/](../../../studio/page/assets/brand/), beside the page that shows them,
and the class server sends them from there.

| File | Use |
|---|---|
| `lockup.png` | The full logo: Splat beside 画里画外 / Beyond Canvas, for the top of a page, a slide or a poster |
| `lockup-header.png` | The same at the class home screen's 56 px, in 256 colours (12 KB) for a classroom on a slow link |
| `lockup-on-dark.png` | The same with paper-coloured letters, for a dark page; the project README shows it in GitHub's dark theme |
| `lockup-line.png` | The same on one line, for a narrow header or a footer |
| `splat.png` | Splat on its own, with its three excitement marks |
| `splat-plain.png` | Splat on its own, without them; the source of every icon |
| `splat-header.png` | The class page's header mark, drawn at twice its 44 px so it stays sharp |
| `tab-icon.png` | The class page's browser-tab icon, 48 px in 256 colours; `studio/page/build.sh` writes it into the page, because Chrome on an iPhone or iPad fetches a tab icon apart from the page, refuses the class's own certificate there, and never showed it as a file |
| `favicon.ico` | A browser-tab icon at 16, 32 and 48 px, for any other site |
| `apple-touch-icon.png` | The class page's iPhone and iPad home-screen icon, 180 px on paper (iOS fills a see-through icon with black), 256 colours; `build.sh` writes it into the page too, because "Add to Home Screen" fetches it without the class password and the door refuses it |
| `icon-192.png` | An Android home-screen icon |
| `icon-512.png` | The largest icon, for an avatar or an installed web app |

Every file has a see-through background, and every one but `lockup-on-dark.png` has dark lettering, so
it needs a light ground. The frames are
1920×1080, which caps the cut-out Splat at about 300 px wide: `icon-512.png` is enlarged from it, and
anything printed larger than a page header needs Splat redrawn at a higher resolution. The big Splat
on the class page's home screen is still drawn by the page itself, because its eyes follow the pointer
and it blinks and winks; a crayon one would have to be redrawn to move.
