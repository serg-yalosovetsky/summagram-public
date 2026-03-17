# ERR-0033: WSL GPU VRAM Parsing Error and UI Scroll Bug

## Symptoms
1. In the Analytics frontend, all containers show `0 MiB` for VRAM usage.
2. The user cannot scroll down the Container list to see containers that overflowed the viewport.
3. The backend logs throw repeated warnings: `Command failed: nvidia-smi --query-graphics-apps...`

## Investigation Notes
- On WSL, `nvidia-smi` does not support `--query-graphics-apps` and returns an error.
- Even for `--query-compute-apps`, the `used_memory` column returns `[N/A]` instead of a number, which causes a `ValueError` in `float("[N/A]")` in `backend/system_stats.py`, preventing any GPU mapping.
- In the frontend `v0/components/app-shell/main-content.tsx`, the `<main>` tag uses `flex flex-1 overflow-hidden`, but without `min-h-0`, flex children (like `AnalyticsView`) that have `overflow-auto` expand infinitely instead of contracting to allow scrolling.

## Hypotheses / Experiments
- **Backend**: If we check for `[N/A]` and default it to `0` MiB, and simultaneously mute the stderr of the `graphics-apps` search, the parser won't crash and the logs won't be spammed.
- **Frontend**: Adding `min-h-0` to the flex container guarantees it respects the viewport height, effectively enabling vertical scrolling in the child container list.

## Final Fix
1. Updated `backend/system_stats.py` to add a `quiet` flag to `_run_cmd`, allowing us to silence the `graphics-apps` query errors.
2. Handled `[N/A]` natively in `_nvidia_procs` by defaulting it to `0` instead of letting `float()` fail.
3. Updated `v0/components/app-shell/main-content.tsx` from `<main className="flex flex-1 flex-col overflow-hidden">` to `<main className="flex flex-1 min-h-0 flex-col overflow-hidden">`.

## Verification
- Running backend shows no more `graphics-apps` log spam.
- Opening the UI allows the Container area to scroll correctly.
- VRAM mappings no longer crash due to `[N/A]`.

## Status
Resolved.
