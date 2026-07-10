#!/bin/bash
# Self-restarting daemon for the fully-pauper coevolution run (pauper_optimize.py).
# Relaunches the optimizer through any harness reap until PAUPER_DONE appears; resume skips
# already-recorded deck-rounds. Launch detached:
#   python3 -c "import subprocess; subprocess.Popen(['bash','.../run_pauper.sh'], start_new_session=True, ...)"
SIM="/Users/jeffbrower/Documents/jeffbrower.com/docs/pokemon/sim"
LOG="$SIM/pauper_opt.log"
DLOG="$SIM/pauper_daemon.log"
cd "$SIM" || exit 1

fastfails=0
for i in $(seq 1 500); do
  if [ -f "$SIM/PAUPER_DONE" ]; then
    echo "[daemon $(date '+%m-%d %H:%M:%S')] PAUPER_DONE present — all rounds complete (after $i checks)" >> "$DLOG"
    break
  fi
  if pgrep -f 'pauper_optimize.py' >/dev/null; then
    sleep 20; continue
  fi
  echo "[daemon $(date '+%m-%d %H:%M:%S')] launch #$i" >> "$DLOG"
  start=$(date +%s)
  python3 "$SIM/pauper_optimize.py" --games 5 --rounds 10 --cap 200 --workers 9 >> "$LOG" 2>&1
  rc=$?; dur=$(( $(date +%s) - start ))
  echo "[daemon $(date '+%m-%d %H:%M:%S')] optimizer exited rc=$rc after ${dur}s" >> "$DLOG"
  if [ "$dur" -lt 60 ] && [ "$rc" -ne 0 ]; then
    fastfails=$((fastfails + 1))
    [ "$fastfails" -ge 5 ] && { echo "[daemon $(date '+%m-%d %H:%M:%S')] 5 fast failures — aborting" >> "$DLOG"; break; }
  else
    fastfails=0
  fi
  sleep 5
done
