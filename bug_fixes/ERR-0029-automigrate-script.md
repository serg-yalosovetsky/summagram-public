# ERR-0029: Separate Script for Auto Migrations

## Symptoms
Following the fixes in `ERR-0027` and `ERR-0028`, the automatic database migrations via Piccolo ORM were stripped out of the application’s auto-startup sequence (`init_db()` in `etl/db/core.py`). This left developers without a quick way to apply schema changes without manually remembering the exact `uv run piccolo` command and environment setup.

## Investigation Notes
- The command requires specific environment variables (`PICCOLO_CONF`) and must be run from the directory containing `piccolo_conf.py` (which is the `etl/` folder).
- Running migrations inside Docker via the application code was problematic, so an explicit, external script is the safest approach.

## Final Fix
Created `automigrate.sh` in the project root:
```bash
#!/bin/bash
# automigrate.sh

echo "Running Piccolo migrations..."
cd "$(dirname "$0")/etl" || exit 1
export PICCOLO_CONF="piccolo_conf"
uv run piccolo migrations forwards all
echo "Migrations completed successfully."
```

## Verification
- Running `./automigrate.sh` locally with the `POSTGRES_DSN` configured successfully executes the Piccolo migration check against the `summagram_new-postgres-1` container.
- Script changes into the correct directory and exits cleanly.

## Status
Resolved
