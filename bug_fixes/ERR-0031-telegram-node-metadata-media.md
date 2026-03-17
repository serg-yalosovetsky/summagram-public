# ERR-0031: TelegramNodeMetadata Schema Missing Field

## Symptoms
The `etl` container logged an error during the indexing job:
```
Job df7a1cf0-24de-4dee-94dd-8bc02c7eaf62 failed: "TelegramNodeMetadata" object has no field "media"
```

## Investigation Notes 
In `etl/models.py`, `TelegramNodeMetadata` has `has_media`, `media_json`, and `media_url`, but it lacks a direct `media: Optional[TelegramMediaMetadata]` field. The `transform_telegram_docs_to_nodes` function in `etl/processing/telegram_etl.py` must be trying to assign or access a `.media` attribute on `TelegramNodeMetadata` or during its instantiation.

## Hypotheses
The `TelegramNodeMetadata` model needs an explicit `media: Optional[TelegramMediaMetadata] = None` attribute to support parsing and storing the nested media metadata object before/during ingestion. 

## Experiments
Add `media: Optional[TelegramMediaMetadata] = None` to `TelegramNodeMetadata` in `etl/models.py`. 

## Final Fix
Added the `media` field back to the `TelegramNodeMetadata` object.

## Verification 
Run `pytest etl/tests/test_audio_processing.py` or monitor the ETL pipeline starting to ensure documents successfully index without the schema validation error.

## Status
Resolved.
