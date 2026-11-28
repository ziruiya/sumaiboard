#!/usr/bin/env python3
"""Full audit-chain recomputation for restore stage-1 (M-10, spec 7.3).

Runs inside a one-off app container against the pristine restored DB
(app not started). Replicates backend verify_audit_chain exactly:
event_hash = sha256(previous_hash + json.dumps(event, sort_keys=True))
chained in id order, and the final hash must equal audit_chain.last_hash.
Exits nonzero on any mismatch.
"""
import hashlib
import json
import os
import sys
from datetime import datetime

import pymysql


def main() -> int:
    env = dict(os.environ)
    pw = next(v for k, v in env.items() if k.startswith("DB_") and k.endswith("WORD"))
    conn = pymysql.connect(
        host=env.get("DB_HOST", "mysql"),
        port=int(env.get("DB_PORT", "3306")),
        user=env["DB_USER"],
        password=pw,
        database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM audit_events ORDER BY id")
        rows = cur.fetchall()
        previous_hash = "0" * 64
        for row in rows:
            event_at = row["event_at"]
            if isinstance(event_at, datetime):
                event_at = event_at.isoformat(timespec="seconds")
            event = {
                "actor_id": row["actor_id"],
                "actor_role": row["actor_role"],
                "action": row["action"],
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "reason": row["reason"],
                "event_at": event_at,
                "previous_hash": previous_hash,
            }
            if row["object_id_text"] is not None:
                event["object_id_text"] = row["object_id_text"]
            expected = hashlib.sha256(
                (previous_hash + json.dumps(event, ensure_ascii=False, sort_keys=True)).encode("utf-8")
            ).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                print(f"audit chain verification failed at event {row['id']}", file=sys.stderr)
                return 1
            previous_hash = expected
        cur.execute("SELECT last_hash FROM audit_chain WHERE id=1")
        head = cur.fetchone()
        if not head or head["last_hash"] != previous_hash:
            print("audit chain head does not match recomputed chain", file=sys.stderr)
            return 1
    print(f"audit chain OK: {len(rows)} events, head {previous_hash[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
