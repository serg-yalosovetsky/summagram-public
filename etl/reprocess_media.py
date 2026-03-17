import asyncio
import sqlite3
import json
import os
import sys
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Add current directory to path so imports work
sys.path.append(os.getcwd())

from models import GenericDocument
from shared.config import Config
from loguru import logger
from etl.processing.indexer import update_index

# Configuration
DB_PATH = Config.DB_PATH
BACKEND_URL = f"{Config.LLM_API_BASE.replace('/v1', '')}/analyze-image"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def analyze_image(path):
    async with httpx.AsyncClient(timeout=60.0) as client:
        # prompt matches telegram.py
        resp = await client.post(BACKEND_URL, json={"image_path": path})
        resp.raise_for_status()
        return resp.json().get("description", "")


async def main():
    logger.info("Starting media reprocessing...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch candidates
    # We look for photo type and missing description
    logger.info("Scanning for documents with missing descriptions...")
    cursor.execute(
        "SELECT id, source_id, doc_id, content, timestamp, metadata FROM raw_documents"
    )
    rows = cursor.fetchall()

    docs_to_update = []

    for row in rows:
        try:
            metadata = json.loads(row["metadata"])
        except Exception:
            continue

        if not metadata:
            continue

        media = metadata.get("media")
        if not media:
            continue

        if media.get("type") == "photo" and not media.get("description"):
            # Candidate found
            path = media.get("path")
            if not path:
                logger.warning(f"Doc {row['doc_id']} has photo type but no path.")
                continue

            if not os.path.exists(path):
                logger.warning(f"Image not found at {path} for doc {row['doc_id']}")
                continue

            docs_to_update.append((row, metadata, path))

    logger.info(f"Found {len(docs_to_update)} documents to process.")

    updated_docs = []

    for row, metadata, path in docs_to_update:
        logger.info(f"Processing {row['doc_id']} ({path})...")
        try:
            description = await analyze_image(path)
            if description:
                # Update Metadata
                metadata["media"]["description"] = description
                if "is_meme: true" in description.lower():
                    metadata["media"]["is_meme"] = True
                if "is_portrait: true" in description.lower():
                    metadata["media"]["is_portrait"] = True

                # Update DB
                new_meta_json = json.dumps(metadata)
                cursor.execute(
                    "UPDATE raw_documents SET metadata = ? WHERE id = ?",
                    (new_meta_json, row["id"]),
                )

                # Reconstruct GenericDocument
                # Need to handle timestamp format
                # Row timestamp is string ISO
                ts = datetime.fromisoformat(row["timestamp"])

                doc = GenericDocument(
                    source_id=row["source_id"],
                    doc_id=row["doc_id"],
                    content=row["content"],
                    timestamp=ts,
                    metadata=metadata,
                )
                updated_docs.append(doc)
                logger.info(f"Updated {row['doc_id']}.")
            else:
                logger.warning(f"No description returned for {row['doc_id']}.")
        except Exception as e:
            logger.error(f"Failed to process {row['doc_id']}: {e}")

    conn.commit()
    conn.close()

    # Update Index
    if updated_docs:
        logger.info(f"Re-indexing {len(updated_docs)} documents...")
        # update_index is sync
        try:
            update_index(updated_docs)
            logger.info("Index update complete.")
        except Exception as e:
            logger.error(f"Failed to update index: {e}")

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
