# ERR-0040: Pydantic populate_by_name omitted from RelationshipSignalPayload

### Symptoms:
Type checker and runtime errors indicate that `RelationshipSignalPayload` is instantiated with keyword arguments `from_person`, `to_person`, `relation_type` but Pydantic expects `from`, `to`, `type` according to its validation aliases.

### Investigation Notes:
- `etl/chat_analysis/prompts.py` instantiates `RelationshipSignalPayload(from_person=..., to_person=..., relation_type=..., signal=...)`
- `RelationshipSignalPayload` fields are defined as `from_person: str = Field(alias="from")`, etc.
- Pydantic V2 strictly requires instantiation by alias unless `populate_by_name=True` is provided in the model config.
- We cannot use `from` as a Python argument identifier in the constructor because it is a reserved language keyword.

### Hypotheses Considered:
1. Redefine aliases? No, the LLM expected JSON schema must contain the concise keys `"from"`, `"to"`, `"type"`.
2. Add `model_config = ConfigDict(populate_by_name=True)`. This allows both initialization by internal field name (`from_person`) and serialization to the desired schema alias (`from`).

### Final Fix:
Instead of using `Field(alias="...")`, the model was refactored to use an `alias_generator` in `model_config`. Pyright relies on PEP 681 (`@dataclass_transform`) and uses `Field(alias=...)` to overwrite the expected `__init__` parameter name, throwing errors when passed the actual python property name. An `alias_generator` correctly formats the JSON schema for LLM output, while keeping the `__init__` signature identical to the model properties for static type checking.

### Status:
resolved
