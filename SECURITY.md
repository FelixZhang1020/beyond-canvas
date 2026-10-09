# Security policy

Beyond Canvas handles children's drawings and recorded voices, so a problem that could expose them is
treated as a security problem, even when no code is broken.

## Supported versions

Only the `main` branch is maintained.

## Reporting a problem

Please do not open a public issue. Report it privately through GitHub: open this repository's
**Security** tab and choose **Report a vulnerability**. Say what you found, how to reproduce it, and what
it would expose. We will reply as soon as we can and keep you informed until it is fixed.

## What we most want to hear about

- Anything that could expose a child's drawing, voice or words beyond where
  [the deployment guide](docs/guides/deployment-versions.md) says they go.
- A path that lets a drawing reach a model before `studio-safety` has looked at it, or lets a picture or
  clip reach a teacher without being screened.
- A way past the class password in front of the studio.
- A key, password or personal data committed to the repository.
- A Skill folder that no longer matches its signature (`uv run python -m evalkit.signing verify skills`).

## Keys

Keys live only in `.env`, which is never committed; `.env.example` lists their names and never their values.
If you find a working key anywhere in this repository, report it as above.
