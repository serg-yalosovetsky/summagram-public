# Error 14: Jaeger Invalid Configuration for Exporter

## Symptoms
The `jaeger-1` container fails to start and enters a restart loop with the error `invalid configuration: service::pipelines::metrics: references exporter "debug" which is not configured`.

## Investigation Details
- Inspected `./jaeger-config.yaml`.
- The `metrics` pipeline referenced `debug` under `exporters`.
- The `exporters` block at the bottom only defined `jaeger_storage_exporter`. OpenTelemetry collector crashes if a pipeline references an undefined component.

## Final Fix
Added the `debug` exporter in `jaeger-config.yaml` underneath `exporters:` with `verbosity: basic`.

## Verification
Docker logs should show a healthy startup of `jaeger-1` after configuration is re-loaded.

## Status
Resolved
