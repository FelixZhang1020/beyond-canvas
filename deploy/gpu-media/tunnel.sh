#!/usr/bin/env bash
#
# The classroom Mac's private line to the 4090. Six loopback ports, forwarded
# over one SSH connection; weights and inference never leave the 4090.
#
# 7290 is hearing, and it is the one that carries a child's recorded voice off
# this machine. That was a deliberate reversal — see the note in
# studio/voice/transcribe.py — and it is why this line matters more than it used to.
#
#   sh deploy/gpu-media/tunnel.sh              dial, and keep redialling
#   BEYOND_CANVAS_GPU_HOST=mybox sh …/tunnel.sh   someone else's card
#   pkill -f "autossh.*7240"                   hang up for good
#
# The host is an SSH alias, taken from BEYOND_CANVAS_GPU_HOST or the first
# argument, and defaulting to the maintainer's `gpu4090`. It is a variable
# because this repository is shared: a collaborator with their own NVIDIA card
# runs the same workers on the same loopback ports, so pointing this at their
# own machine is the only change the whole studio needs from them. Editing a
# checked-in script to run it was the last thing in the deploy guide that asked
# a reader to modify code.
#
# Why autossh rather than plain ssh: once the connection died leaving
# no log, and took voice, image, video and 3D with it. Nothing restarted it and
# nothing said it was gone, so the classroom read as four broken models when in
# fact all five workers on the 4090 were healthy and simply unreachable. autossh
# watches the connection and redials; ssh alone only ever notices its own death.
#
# What this does NOT promise: it does not start at login, and it does not tell
# anyone it dropped. A reconnect takes roughly the ServerAlive window below, so
# a request in flight when the line dies still fails — it is the next one that
# succeeds.
#
# -M 0 turns off autossh's own monitoring port, which needs a second forwarded
# port and cannot see a connection that is up but not passing traffic. The ssh
# keepalives below do that job: three missed 15-second probes and ssh exits,
# which is the signal autossh acts on. AUTOSSH_GATETIME=0 means a connection
# that dies in its first seconds — the 4090 rebooting, the network not up yet —
# is still retried rather than treated as a configuration error and abandoned.
#
# Measured with this file's config, recovery timed from the Mac:
#   ssh killed outright (a crash)          restarted in ~2s
#   4090 closed the session (a reboot)     restarted in ~2s, new child pid
#   silent network blackhole               NOT TESTED; detection is bounded by
#                                          the keepalives above, so under ~45s
# One case deliberately does not recover: SIGTERM to the ssh child makes it exit
# with status 0, and autossh reads a clean exit as "you meant to stop" and exits
# too. That is why hanging up means killing autossh, not ssh — see above.

set -Eeuo pipefail

host="${1:-${BEYOND_CANVAS_GPU_HOST:-gpu4090}}"

export AUTOSSH_GATETIME=0
export AUTOSSH_POLL=30

exec autossh -M 0 -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -o ConnectTimeout=10 \
  -L 127.0.0.1:7240:127.0.0.1:7240 \
  -L 127.0.0.1:7250:127.0.0.1:7250 \
  -L 127.0.0.1:7260:127.0.0.1:7260 \
  -L 127.0.0.1:7270:127.0.0.1:7270 \
  -L 127.0.0.1:7280:127.0.0.1:7280 \
  -L 127.0.0.1:7290:127.0.0.1:7290 "$host"
