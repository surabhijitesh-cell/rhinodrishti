"""
migrate_atlas_to_local.py
─────────────────────────
Copies every collection from MongoDB Atlas (source) to a local
MongoDB Community installation (target).

Usage (called by setup-wizard.ps1):
    python migrate_atlas_to_local.py --source <atlas-uri> --target <local-uri>

Can also be run standalone to re-sync or top-up the local DB.
"""

import argparse
import sys
import time
from datetime import datetime, timezone


def _bar(done: int, total: int, width: int = 30) -> str:
    if total == 0:
        return f"[{'─' * width}]"
    filled = int(width * done / total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def _fmt(n: int) -> str:
    return f"{n:,}"


def migrate(source_uri: str, target_uri: str, dry_run: bool = False):
    try:
        from pymongo import MongoClient
        from pymongo.errors import BulkWriteError
    except ImportError:
        print("✘  pymongo not installed. Run: pip install 'pymongo[srv]'")
        sys.exit(1)

    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║          Rhino Drishti — Atlas → Local Migration        ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    # ── Connect ──────────────────────────────────────────────────────────────
    print("  ▶  Connecting to Atlas ...")
    try:
        src_client = MongoClient(source_uri, serverSelectionTimeoutMS=15000)
        src_client.admin.command("ping")
        print("  ✔  Atlas connected")
    except Exception as e:
        print(f"  ✘  Cannot connect to Atlas: {e}")
        sys.exit(1)

    print("  ▶  Connecting to local MongoDB ...")
    try:
        dst_client = MongoClient(target_uri, serverSelectionTimeoutMS=10000)
        dst_client.admin.command("ping")
        print("  ✔  Local MongoDB connected")
    except Exception as e:
        print(f"  ✘  Cannot connect to local MongoDB: {e}")
        sys.exit(1)

    # Parse DB name from URI
    db_name = "rhino_drishti"
    for part in target_uri.split("/"):
        if part and "?" in part:
            db_name = part.split("?")[0]
            break
        if part and part not in ("", "mongodb:", "") and ":" not in part and "@" not in part:
            db_name = part

    src_db = src_client[db_name]
    dst_db = dst_client[db_name]

    collections = src_db.list_collection_names()
    print(f"\n  ℹ  Database      : {db_name}")
    print(f"  ℹ  Collections   : {len(collections)}")
    if dry_run:
        print("  ⚠  DRY RUN — no data will be written\n")

    total_docs   = 0
    total_copied = 0
    start        = time.time()

    for col_name in sorted(collections):
        src_col = src_db[col_name]
        dst_col = dst_db[col_name]

        count = src_col.count_documents({})
        if count == 0:
            print(f"  ─  {col_name:<35}  (empty — skipped)")
            continue

        print(f"\n  ▶  {col_name:<35}  {_fmt(count)} documents")

        if dry_run:
            total_docs += count
            continue

        # Stream in batches of 500
        batch_size = 500
        inserted   = 0
        skipped    = 0
        cursor     = src_col.find({}, {"_id": 1}).batch_size(batch_size)
        src_ids    = {doc["_id"] for doc in cursor}

        # Find IDs not yet in local
        existing   = {doc["_id"] for doc in dst_col.find({}, {"_id": 1})}
        to_copy    = src_ids - existing

        if not to_copy:
            print(f"       {_bar(count, count)}  already up-to-date ({_fmt(count)} existing)")
            total_docs   += count
            total_copied += count
            continue

        # Copy in batches
        batch     = []
        done      = 0
        to_copy_l = list(to_copy)

        for _id in to_copy_l:
            doc = src_col.find_one({"_id": _id})
            if doc:
                batch.append(doc)
            if len(batch) >= batch_size:
                try:
                    if not dry_run:
                        dst_col.insert_many(batch, ordered=False)
                    inserted += len(batch)
                except BulkWriteError as bwe:
                    inserted += bwe.details.get("nInserted", 0)
                    skipped  += len(batch) - bwe.details.get("nInserted", 0)
                batch = []
            done += 1
            if done % 100 == 0 or done == len(to_copy_l):
                pct = int(done / len(to_copy_l) * 100)
                print(f"       {_bar(done, len(to_copy_l))}  {pct}%  ({_fmt(inserted)} new, {_fmt(skipped)} dup)   ", end="\r")

        if batch:
            try:
                dst_col.insert_many(batch, ordered=False)
                inserted += len(batch)
            except BulkWriteError as bwe:
                inserted += bwe.details.get("nInserted", 0)

        print(f"       {_bar(count, count)}  100%  {_fmt(inserted)} copied, {_fmt(skipped)} already existed     ")
        total_docs   += count
        total_copied += inserted

    elapsed = time.time() - start
    print()
    print("  ╔═══════════════════════════════════════════╗")
    print(f"  ║  Migration complete in {elapsed:5.1f}s              ║")
    print(f"  ║  Collections processed : {len(collections):<17} ║")
    print(f"  ║  Total source documents: {_fmt(total_docs):<17} ║")
    print(f"  ║  New docs copied       : {_fmt(total_copied):<17} ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()

    if not dry_run:
        # Write migration log
        log_entry = {
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "source":      source_uri[:40] + "..." if len(source_uri) > 40 else source_uri,
            "collections": len(collections),
            "docs_copied": total_copied,
            "duration_s":  round(elapsed, 1),
        }
        dst_db["_migration_log"].insert_one(log_entry)
        print("  ✔  Migration log entry written to local DB")

    src_client.close()
    dst_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Rhino Drishti from Atlas to local MongoDB")
    parser.add_argument("--source",    required=True,         help="MongoDB Atlas connection URI")
    parser.add_argument("--target",    required=True,         help="Local MongoDB connection URI")
    parser.add_argument("--dry-run",   action="store_true",   help="Count documents only, don't copy")
    args = parser.parse_args()

    migrate(args.source, args.target, dry_run=args.dry_run)
