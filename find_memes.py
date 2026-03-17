import sqlite3
import json
import os

DB_PATH = os.getenv("DB_PATH", "summagram.db")


def get_telegram_link(chat_id, message_id, chat_title=None, username=None):
    # Heuristic to determine link format
    # If we had username, it would be t.me/username/message_id
    # Since we often only have chat_id, we use the private link format for -100 ids

    cid = str(chat_id)
    if cid.startswith("-100"):
        # Private channel/supergroup id
        clean_id = cid[4:]
        return f"https://t.me/c/{clean_id}/{message_id}"
    elif cid.startswith("-"):
        # Group chat, usually no direct link unless it's a supergroup
        # specific logic might be needed, but let's try the same
        clean_id = cid[1:]
        # For normal groups, links are tricky without username or invite link
        return f"https://t.me/c/{clean_id}/{message_id}"
    else:
        # User ID or positive ID - likely a private chat with a user
        # You can't really link to a specific message in a private 1-on-1 chat easily
        # without the context of the user opening it.
        # But maybe the user wants to see it in their "Saved Messages" if they forwarded it?
        return f"tg://openmessage?user_id={cid}&message_id={message_id}"


def find_memes():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT source_id, doc_id, metadata, content 
    FROM raw_documents 
    WHERE source_id LIKE 'telegram_%'
    """

    cursor.execute(query)

    memes = []

    idx = 0
    for row in cursor:
        try:
            meta = json.loads(row["metadata"])
            media = meta.get("media")

            if not media:
                continue

            is_meme = media.get("is_meme", False)
            description = media.get("description", "").lower()
            tags = media.get("tags", "")
            if tags:
                tags = str(tags).lower()

            # Check identifying features
            # 1. Explicit flag
            if is_meme:
                reason = "is_meme flag"
            # 2. Keywords in description/tags
            elif (
                "meme" in description
                or "funny" in description
                or (tags and ("meme" in tags or "funny" in tags))
            ):
                reason = "keywords"
                is_meme = True  # Treat as meme for our list
            else:
                continue

            chat_id = meta.get("chat_id")
            msg_id = row["doc_id"]
            chat_title = meta.get("chat_title")

            # Construct link
            link = get_telegram_link(chat_id, msg_id, chat_title)

            local_path = media.get("path")

            memes.append(
                {
                    "id": idx,
                    "chat_id": chat_id,
                    "msg_id": msg_id,
                    "chat_title": chat_title,
                    "description": media.get("description"),
                    "local_path": local_path,
                    "link": link,
                    "reason": reason,
                    "tags": tags,
                }
            )
            idx += 1

        except Exception:
            # print(f"Error processing row: {e}")
            pass

    conn.close()
    return memes


if __name__ == "__main__":
    found_memes = find_memes()
    print(f"Found {len(found_memes)} memes.")

    # Sort specifically to find 'funniest'.
    # Since we can't judge funny, let's look for 'funny' keyword explicitly first,
    # then just return the last few (most recent).

    # Prioritize those with "funny" in description
    funniest = [
        m
        for m in found_memes
        if m["description"] and "funny" in m["description"].lower()
    ]
    others = [m for m in found_memes if m not in funniest]

    all_sorted = funniest + others

    # Show last 5
    for m in all_sorted[-5:]:
        print("---")
        print(f"Description: {m['description']}")
        print(f"Tags: {m['tags']}")
        print(f"Path: {m['local_path']}")
        print(f"Link: {m['link']}")
        print(f"Source: {m['chat_title']}")
