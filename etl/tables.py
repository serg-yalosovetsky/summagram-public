from piccolo.table import Table
from piccolo.columns import Text, Integer, JSONB, Float, Boolean, Serial, BigInt


class UnifiedEvent(Table, tablename="unified_events"):
    id = Serial(primary_key=True)
    event_type = Text(null=False)
    start_time = Text(null=False)
    end_time = Text(null=False)
    title = Text(null=False)
    payload = JSONB(null=True)
    evidence_msg_id = Text(null=True)
    source_id = Text(null=True)
    calendar_sync_status = Integer(default=0)
    created_at = Text(null=True)


class SyncState(Table, tablename="sync_states"):
    source_id = Text(primary_key=True)
    last_synced_at = Text(null=True)
    last_msg_id = Integer(null=True)
    meta = JSONB(null=True)


class RawDocument(Table, tablename="raw_documents"):
    id = Serial(primary_key=True)
    source_id = Text(null=True)
    doc_id = Text(null=True)
    content = Text(null=True)
    timestamp = Text(null=True)
    metadata_ = JSONB(null=True, db_column_name="metadata")


class DownloadRange(Table, tablename="download_ranges"):
    id = Serial(primary_key=True)
    chat_id = Text(null=False)
    start_date = Text(null=False)
    end_date = Text(null=False)
    created_at = Text(null=True)


class IndexedDocument(Table, tablename="indexed_documents"):
    source_id = Text(null=True)
    doc_id = Text(null=True)
    indexed_at = Text(null=True)


class Chat(Table, tablename="chats"):
    id = Serial(primary_key=True)
    source_id = BigInt(null=False, unique=True)
    title = Text(null=True)
    description = Text(null=True)
    tags = Text(null=True)
    image_path = Text(null=True)
    image_description = Text(null=True)
    message_count_total = Integer(default=0)
    message_count_me = Integer(default=0)
    importance_score = Float(default=0.0)
    is_private = Boolean(default=False)
    last_analyzed_at = Text(null=True)
    created_at = Text(null=True)


class Contact(Table, tablename="contacts"):
    id = Serial(primary_key=True)
    source_id = BigInt(null=False, unique=True)
    name = Text(null=True)
    username = Text(null=True)
    phone = Text(null=True)
    description = Text(null=True)
    interests = Text(null=True)
    tags = Text(null=True)
    image_path = Text(null=True)
    image_description = Text(null=True)
    address = Text(null=True)
    last_analyzed_at = Text(null=True)
    created_at = Text(null=True)


class ChatMember(Table, tablename="chat_members"):
    chat_id = BigInt(null=False)
    user_id = BigInt(null=False)


class SocialGraphCache(Table, tablename="social_graph_cache"):
    id = Serial(primary_key=True)
    graph_json = Text(null=False)
    node_count = Integer(default=0)
    edge_count = Integer(default=0)
    created_at = Text(null=True)


class SessionTable(Table, tablename="sessions"):
    id = Text(primary_key=True)
    title = Text(null=True)
    context_chat_id = BigInt(null=True)
    meta = JSONB(null=True)
    created_at = Text(null=True)
    updated_at = Text(null=True)


class ChatSegment(Table, tablename="chat_segments"):
    id = Serial(primary_key=True)
    chat_id = BigInt(null=False)
    segment_no = Integer(null=False)
    start_message_doc_id = Text(null=False)
    end_message_doc_id = Text(null=False)
    start_ts = Text(null=False)
    end_ts = Text(null=False)
    message_count = Integer(null=False)
    token_count_estimate = Integer(null=False)
    strategy = Text(null=False)
    text_for_llm = Text(null=False)
    created_at = Text(null=True)

    class Meta():
        unique_together = (("chat_id", "segment_no"),)


class ChatSegmentAnalysis(Table, tablename="chat_segment_analysis"):
    id = Serial(primary_key=True)
    segment_id = BigInt(null=False, unique=True)
    model_name = Text(null=False)
    model_version = Text(null=True)
    summary = Text(null=False)
    topics = JSONB(null=False)
    people = JSONB(null=False)
    events = JSONB(null=False)
    interests = JSONB(null=False)
    places = JSONB(null=False)
    relationship_signals = JSONB(null=False)
    tone = JSONB(null=False)
    importance_score = Float(null=True)
    confidence = Float(null=True)
    raw_json = JSONB(null=False)
    created_at = Text(null=True)
