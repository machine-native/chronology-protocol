#!/usr/bin/env bash
# Race loop for the live-anchor gate: rebuild against the current tip, mine, submit,
# and check whether our block became the tip. Repeats until it does (or MAX_ROUNDS).
# The laboratory VM mines the same chain at ~64 min/block average; each of our rounds
# takes ~1-7 min, so odds favor us in any given round.
set -u
cd "$(dirname "$0")/.."
export PATH=/c/msys64/mingw64/bin:$PATH
MAX_ROUNDS=8
CORES=8
SPAN=536870912   # 2^32 / 8

for round in $(seq 1 $MAX_ROUNDS); do
  echo "=== ROUND $round $(date -u +%H:%M:%SZ) ==="
  python live/fetch_tip_context.py > /dev/null || { echo "fetch failed"; sleep 10; continue; }
  PREV=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_hash'])")
  MTP=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['median_time_past'])")
  BITS=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['next_bits'])")
  HEIGHT=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_height'])")
  NTIME=$(python -c "import time;print(int(time.time()))")
  echo "tip $PREV height $HEIGHT mtp $MTP bits $BITS ntime $NTIME"
  python scripts/build_sandwich_template.py "$PREV" "$MTP" "$BITS" "$NTIME" > /dev/null || { echo "template failed"; continue; }
  H=$(python -c "import json;print(json.load(open('reports/live-template.json'))['header_nonce0'])")

  rm -f live/mine/range*.out
  mkdir -p live/mine
  pids=""
  for i in $(seq 0 $((CORES-1))); do
    start=$((i * SPAN))
    ( ./native/mine_sha256d.exe "$H" $start $SPAN > live/mine/range$i.out 2>&1 ) &
    pids="$pids $!"
  done

  FOUNDHDR=""
  while true; do
    sleep 5
    f=$(grep -h "^header=" live/mine/range*.out 2>/dev/null | head -1)
    if [ -n "$f" ]; then FOUNDHDR="${f#header=}"; break; fi
    alive=0
    for p in $pids; do kill -0 $p 2>/dev/null && alive=1; done
    [ $alive -eq 0 ] && break
  done
  for p in $pids; do kill $p 2>/dev/null; done
  wait 2>/dev/null

  if [ -z "$FOUNDHDR" ]; then
    echo "nonce space exhausted, rebuilding with fresh nTime"
    continue
  fi
  grep -h "FOUND" live/mine/range*.out | head -1
  python scripts/finalize_mined_block.py "$FOUNDHDR" > live/mine/finalize.json || { echo "finalize refused"; continue; }
  OURHASH=$(python -c "import json;print(json.load(open('live/mine/finalize.json'))['block_hash'])")
  python scripts/submit_block_v01.py bitcoin.bitcoin-lab.org 18026 > live/mine/submit.json && echo "submitted $OURHASH"
  sleep 8
  python live/fetch_tip_context.py > /dev/null || true
  NEWTIP=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_hash'])")
  NEWH=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_height'])")
  if [ "$NEWTIP" = "$OURHASH" ]; then
    echo "=== SUCCESS: our block $OURHASH is the active tip at height $NEWH ==="
    exit 0
  fi
  echo "tip after submit: $NEWTIP (height $NEWH) — not ours, racing again"
done
echo "=== gave up after $MAX_ROUNDS rounds ==="
exit 1
