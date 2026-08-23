#!/usr/bin/env bash
# Race loop for the live-anchor gate: rebuild against the current tip, mine, submit,
# and check whether our block became the tip. Repeats until it does (or MAX_ROUNDS).
# The laboratory VM mines the same chain at ~64 min/block average; each of our rounds
# takes ~1-7 min, so odds favor us in any given round.
set -u
cd "$(dirname "$0")/.."

# Which epoch this race is anchoring. Required and explicit: the previous default
# read reports/verification.json, the sealed v0.1.0 baseline, which carries epoch
# 0 -- so a run started today would have mined a duplicate of an epoch already on
# the chain, and nothing in the loop would have said so.
#   PAYLOAD_HEX=$(cat live/g6-work/payload.hex) ./live/race.sh
: "${PAYLOAD_HEX:?set PAYLOAD_HEX to the 96-byte anchor payload, e.g. PAYLOAD_HEX=\$(cat live/g6-work/payload.hex)}"
echo "anchoring payload epoch $(python -c "import sys;print(int(sys.argv[1][16:32],16))" "$PAYLOAD_HEX")"
export PATH=/c/msys64/mingw64/bin:$PATH
MAX_ROUNDS=${MAX_ROUNDS:-8}
# CORES defaults to 8 because that is what the earlier anchors were mined with.
# SPAN is derived rather than hardcoded: the two must partition the 2^32 nonce
# space exactly, and a mismatched pair silently leaves a gap that is never
# searched -- a round that reports "nonce space exhausted" while having skipped
# part of it.
CORES=${CORES:-8}
SPAN=$(( 4294967296 / CORES ))
echo "mining with $CORES workers, span $SPAN each"

for round in $(seq 1 $MAX_ROUNDS); do
  echo "=== ROUND $round $(date -u +%H:%M:%SZ) ==="
  python live/fetch_tip_context.py > /dev/null || { echo "fetch failed"; sleep 10; continue; }
  PREV=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_hash'])")
  MTP=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['median_time_past'])")
  BITS=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['next_bits'])")
  HEIGHT=$(python -c "import json;c=json.load(open('live/tip-context.json'));print(c['tip_height'])")
  NTIME=$(python -c "import time;print(int(time.time()))")
  echo "tip $PREV height $HEIGHT mtp $MTP bits $BITS ntime $NTIME"
  python scripts/build_live_template.py "$PREV" "$MTP" "$BITS" "$NTIME" "$PAYLOAD_HEX" > /dev/null || { echo "template failed"; continue; }
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
