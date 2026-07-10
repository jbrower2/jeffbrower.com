#!/bin/bash
# Self-restarting daemon for the coevolutionary deck optimizer.
#
# The harness reaps long background jobs unpredictably (observed kills at 23 min and
# 55 min). optimize.py checkpoints after every accepted change and skips already-done
# deck-rounds on restart, so relaunching simply continues. This wrapper relaunches it
# until the OPT_DONE sentinel appears. Fully detach it so it outlives the spawning
# shell:  setsid nohup bash run_optimizer.sh >> daemon.log 2>&1 < /dev/null &
#
# Idempotent: a pgrep guard prevents two optimizers running at once, so it is safe to
# start this wrapper more than once (e.g. from a watchdog).
SIM="/Users/jeffbrower/Documents/jeffbrower.com/docs/pokemon/sim"
LOG="$SIM/opt.log"
DLOG="$SIM/daemon.log"
cd "$SIM" || exit 1

fastfails=0
for i in $(seq 1 500); do
  if [ -f "$SIM/OPT_DONE" ]; then
    echo "[daemon $(date '+%m-%d %H:%M:%S')] OPT_DONE present — all 8 rounds complete (after $i checks)" >> "$DLOG"
    break
  fi
  if pgrep -f 'optimize.py --games 3' >/dev/null; then
    sleep 20; continue                       # another optimizer instance is already running
  fi
  echo "[daemon $(date '+%m-%d %H:%M:%S')] launch #$i" >> "$DLOG"
  start=$(date +%s)
  python3 "$SIM/optimize.py" --games 3 --cap 250 --rounds 5 --workers 9 >> "$LOG" 2>&1
  rc=$?; dur=$(( $(date +%s) - start ))
  echo "[daemon $(date '+%m-%d %H:%M:%S')] optimizer exited rc=$rc after ${dur}s" >> "$DLOG"
  if [ "$dur" -lt 60 ] && [ "$rc" -ne 0 ]; then
    fastfails=$((fastfails + 1))             # tight error loop (e.g. bad code) — bail out
    if [ "$fastfails" -ge 5 ]; then
      echo "[daemon $(date '+%m-%d %H:%M:%S')] 5 fast failures in a row — aborting" >> "$DLOG"
      break
    fi
  else
    fastfails=0                              # a long run that got reaped: keep going
  fi
  sleep 5
done
