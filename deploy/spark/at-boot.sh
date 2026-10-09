#!/bin/sh
# Bring the class back after the Spark restarts: wait for Docker, then run start.sh, which starts
# every session that is down (door, studio, media services, recorder). Run by our own user's
# crontab (`@reboot`), installed with:
#     (crontab -l 2>/dev/null | grep -v at-boot.sh; echo "@reboot sh $HOME/beyond-canvas/deploy/spark/at-boot.sh") | crontab -
#
# Why: the organisers power-cycled the node once and every tmux session was lost; the
# class address then stays down until someone logs in. A per-user crontab is not among the
# manual's forbidden system changes (8.1 item 4: passwords, SSH, firewall, network, users), and
# nothing here needs root. Log: ~/logs/at-boot.log
LOG=$HOME/logs/at-boot.log
mkdir -p "$HOME/logs"
echo "=== $(date '+%F %T') the node started" >> "$LOG"
tries=0
until docker info > /dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -ge 60 ] && { echo "Docker did not answer in 5 minutes; start.sh not run" >> "$LOG"; exit 1; }
    sleep 5
done
PATH=/usr/local/bin:/usr/bin:/bin sh "$HOME/beyond-canvas/deploy/spark/start.sh" >> "$LOG" 2>&1
echo "=== $(date '+%F %T') start.sh finished" >> "$LOG"
