#!/bin/sh
# Is the class making something right now? Runs ON the node: exits 0 while it is, 1 when it is not.
#
# Busy means what restart.sh's guard means, by the same two looks: a media job folder younger than three
# hours (a crash leaves older ones behind, and start.sh removes those), or the class studio holding an
# accepted request it has not finished saving (studio_idle.py, which answers busy too when it cannot tell).
# test-on-spark.sh waits on it before a full run, because a run shares the class's chip: once one
# slowed a storybook's pages from about 5 s each to 6-7 s while a teacher waited.
jobs=$(find "$HOME/spark-media/media-extra/jobs" -mindepth 1 -maxdepth 1 -mmin -180 2>/dev/null | wc -l)
[ "$jobs" -eq 0 ] || exit 0
python3 "$HOME/beyond-canvas/deploy/spark/studio_idle.py" > /dev/null 2>&1 || exit 0
exit 1
