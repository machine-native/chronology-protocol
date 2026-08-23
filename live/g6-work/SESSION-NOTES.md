# Epoch 4 optical session — what was captured and what was removed

## The session

    B0            height 320, 00000000e95f093d5d1b7d190684d7a0bb28839703d3611a6f8298ce74bb662f
    challenge     issued 2026-08-23T15:41:46Z
    seed          C315EEC56B91AFF8, 10-second slots
    frames        15:42:26Z to 15:47:54Z
    place         New Delhi, India
    camera        samsung Galaxy M56 5G

## What the frames are

    20260823_211226              the code page with the seed typed in, before
                                 Start was pressed. No code displayed.
    20260823_211232 .. _211534   the Moon with the rolling code in frame.
                                 29 frames, 19 distinct codes.
    20260823_211635 .. _211754   the Moon alone, including zoomed frames.
                                 No code page in shot.

Only the middle group carries a code, and only that group is counted toward the
series thresholds. The others are hashed and committed like every other frame,
but assert nothing about elapsed time -- see `rolling-expectation.json`, where
each carries `shows_code: false` rather than a code it cannot show.

## Frames removed before consolidation

Four frames were deleted by the operator after shooting and before `run_g6.py`
was run: accidental exposures taken while the camera was being moved, showing a
motion-blurred building and neither the sky target nor the code page. One of
them, `20260823_211546`, was inspected directly and confirmed to be exactly
that.

This is recorded because the retained series contains a 62-second gap between
15:45:35Z and 15:46:37Z, and an unexplained gap in an evidence record is an
invitation to a worse explanation than the true one. A reader who notices it
should be able to tell "accidental frames removed" from "inconvenient frames
removed" without having to ask.

**What that costs.** The photo manifest is a curated set, not everything the
camera produced. The claim it supports is unchanged -- these 41 frames existed,
hashed exactly as recorded, inside the causal window -- and none of it depends on
the set being exhaustive. But it is not exhaustive, and nothing elsewhere in the
evidence says so.

**Better practice for the next session:** keep every frame, including the duds.
Storage is free, `--code-frames` already handles frames that show no code, and a
complete set removes the question entirely.

## What this session does NOT establish

- Not where the camera was pointed. A signature attributes bytes to a key; it
  says nothing about the direction of a lens.
- Not a calibrated astrometric measurement. `CLAIMS.md` disclaims this
  explicitly, and the Moon here is an overexposed disc.
- Not a timestamp. The frames are bounded between B0 and whichever block later
  buries this checkpoint. That interval is the claim; its midpoint is not.
