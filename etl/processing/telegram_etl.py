import json
from datetime import datetime, timezone
from llama_index.core.schema import TextNode
from etl.models import GenericDocument, TelegramMetadata, TelegramNodeMetadata
from etl.security import mask_pii


def transform_telegram_docs_to_nodes(
    docs: list[GenericDocument], context_window_size: int = 3
) -> list[TextNode]:
    """
    Transforms raw Telegram documents into LlamaIndex Nodes with Context Windowing.

    Args:
        docs: List of GenericDocument objects.
        context_window_size: Number of previous messages to prepend as context.

    Returns:
        List of TextNode objects ready for indexing.
    """

    # 1. Sort by source_id then timestamp to ensure correct order
    sorted_docs = sorted(docs, key=lambda x: (x.source_id, x.timestamp))

    nodes = []

    # Dictionary to keep track of recent messages per chat (source_id)
    # Key: source_id, Value: List of (content, sender_name)
    context_buffers = {}

    for doc in sorted_docs:
        chat_id = doc.source_id
        if chat_id not in context_buffers:
            context_buffers[chat_id] = []

        # 2. Parse Metadata
        meta = TelegramMetadata(**doc.metadata)

        # 3. Build Context String
        context_str = ""
        buffer = context_buffers[chat_id]

        if buffer:
            context_str = (
                "--- PREVIOUS MESSAGES IN THIS CHAT ---\n"
                + "\n".join(buffer)
                + "\n---\n"
            )

        # 4. Create Node with Enriched Text
        safe_content = mask_pii(doc.content)
        # Ensure the current message is clearly distinct
        enriched_text = context_str + "CURRENT MESSAGE:\n" + safe_content

        node_meta_obj = TelegramNodeMetadata(
            source_id=doc.source_id,
            chat_id=meta.chat_id,  # int from TelegramMetadata — authoritative
            doc_id=doc.doc_id,  # mirrors TextNode id_ — canonical key for SQLite lookup
            ts_unix_ms=int(doc.timestamp.timestamp() * 1000),
            ts_iso=doc.timestamp.isoformat(),
            author=meta.sender_name,
            recipient=meta.recipient_name,
            forwarded_from=meta.forward_from_name,
            is_from_me=meta.is_from_me,
            original_text=doc.content,
            content_norm=safe_content.lower().strip(),
            char_count=len(safe_content),
            approx_token_count=len(safe_content) // 4,
            reply_to_message_id=meta.reply_to_msg_id,
            ingested_at_unix_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
        )

        if meta.media:
            node_meta_obj.media = json.dumps(meta.media.model_dump())
            if meta.media.tags:
                node_meta_obj.tags = meta.media.tags
            if meta.media.url:
                node_meta_obj.media_url = meta.media.url

        node = TextNode(
            text=enriched_text,
            id_=doc.doc_id,
            metadata=node_meta_obj.model_dump(),
            excluded_llm_metadata_keys=["source_id", "original_text"],
        )

        nodes.append(node)

        # 5. Update Buffer
        # Append masked content
        buffer.append(mask_pii(doc.content))
        # Keep only last K
        if len(buffer) > context_window_size:
            buffer.pop(0)

    return nodes
