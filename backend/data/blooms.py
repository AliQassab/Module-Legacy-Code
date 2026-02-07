import datetime

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data.connection import db_cursor
from data.users import User


@dataclass
class Bloom:
    id: int
    sender: str
    content: str
    sent_timestamp: datetime.datetime
    original_sender: Optional[str] = None
    rebloomer: Optional[str] = None
    rebloom_count: int = 0


def add_bloom(*, sender: User, content: str) -> Bloom:
    hashtags = [word[1:] for word in content.split(" ") if word.startswith("#")]

    now = datetime.datetime.now(tz=datetime.UTC)
    bloom_id = int(now.timestamp() * 1000000)
    timestamp = datetime.datetime.now(datetime.UTC)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO blooms (id, sender_id, content, send_timestamp) VALUES (%(bloom_id)s, %(sender_id)s, %(content)s, %(timestamp)s)",
            dict(
                bloom_id=bloom_id,
                sender_id=sender.id,
                content=content,
                timestamp=timestamp,
            ),
        )
        for hashtag in hashtags:
            cur.execute(
                "INSERT INTO hashtags (hashtag, bloom_id) VALUES (%(hashtag)s, %(bloom_id)s)",
                dict(hashtag=hashtag, bloom_id=bloom_id),
            )
    
    return Bloom(
        id=bloom_id,
        sender=sender.username,
        content=content,
        sent_timestamp=timestamp,
        rebloom_count=0,
    )


def get_blooms_for_user(
    username: str, *, before: Optional[int] = None, limit: Optional[int] = None
) -> List[Bloom]:
    with db_cursor() as cur:
        kwargs = {
            "sender_username": username,
        }
        if before is not None:
            before_clause = "AND send_timestamp < %(before_limit)s"
            kwargs["before_limit"] = before
        else:
            before_clause = ""

        limit_clause = make_limit_clause(limit, kwargs)

        cur.execute(
            f"""SELECT
              blooms.id, users.username, content, send_timestamp,
              (SELECT COUNT(*) FROM reblooms WHERE reblooms.original_bloom_id = blooms.id) as rebloom_count
            FROM
              blooms INNER JOIN users ON users.id = blooms.sender_id
            WHERE
              username = %(sender_username)s
              {before_clause}
            ORDER BY send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms_list = []
        for row in rows:
            bloom_id, sender_username, content, timestamp, rebloom_count = row
            blooms_list.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                    rebloom_count=rebloom_count or 0,
                )
            )
    return blooms_list


def get_bloom(bloom_id: int) -> Optional[Bloom]:
    with db_cursor() as cur:
        cur.execute(
            """SELECT blooms.id, users.username, content, send_timestamp,
               (SELECT COUNT(*) FROM reblooms WHERE reblooms.original_bloom_id = blooms.id) as rebloom_count
               FROM blooms INNER JOIN users ON users.id = blooms.sender_id WHERE blooms.id = %s""",
            (bloom_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        bloom_id, sender_username, content, timestamp, rebloom_count = row
        return Bloom(
            id=bloom_id,
            sender=sender_username,
            content=content,
            sent_timestamp=timestamp,
            rebloom_count=rebloom_count or 0,
        )


def get_blooms_with_hashtag(
    hashtag_without_leading_hash: str, *, limit: int = None
) -> List[Bloom]:
    kwargs = {
        "hashtag_without_leading_hash": hashtag_without_leading_hash,
    }
    limit_clause = make_limit_clause(limit, kwargs)
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT
              blooms.id, users.username, content, send_timestamp,
              (SELECT COUNT(*) FROM reblooms WHERE reblooms.original_bloom_id = blooms.id) as rebloom_count
            FROM
              blooms INNER JOIN hashtags ON blooms.id = hashtags.bloom_id INNER JOIN users ON blooms.sender_id = users.id
            WHERE
              hashtag = %(hashtag_without_leading_hash)s
            ORDER BY send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms_list = []
        for row in rows:
            bloom_id, sender_username, content, timestamp, rebloom_count = row
            blooms_list.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                    rebloom_count=rebloom_count or 0,
                )
            )
    return blooms_list


def make_limit_clause(limit: Optional[int], kwargs: Dict[Any, Any]) -> str:
    if limit is not None:
        limit_clause = "LIMIT %(limit)s"
        kwargs["limit"] = limit
    else:
        limit_clause = ""
    return limit_clause


def add_rebloom(*, rebloomer: User, original_bloom_id: int) -> Bloom:
    with db_cursor() as cur:
        cur.execute(
            "SELECT blooms.id, blooms.sender_id, blooms.content, blooms.send_timestamp FROM blooms WHERE blooms.id = %s",
            (original_bloom_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Bloom {original_bloom_id} does not exist")
        
        bloom_id, original_sender_id, content, _ = row
        
        cur.execute(
            "SELECT id FROM reblooms WHERE rebloomer_id = %s AND original_bloom_id = %s",
            (rebloomer.id, original_bloom_id),
        )
        if cur.fetchone() is not None:
            raise ValueError("You have already rebloomed this bloom")
        
        # Add rebloom record
        rebloom_timestamp = datetime.datetime.now(datetime.UTC)
        cur.execute(
            "INSERT INTO reblooms (rebloomer_id, original_bloom_id, rebloom_timestamp) VALUES (%s, %s, %s)",
            (rebloomer.id, original_bloom_id, rebloom_timestamp),
        )
        
        cur.execute("SELECT username FROM users WHERE id = %s", (original_sender_id,))
        original_sender_row = cur.fetchone()
        if original_sender_row is None:
            raise ValueError(f"Original sender user {original_sender_id} not found")
        original_sender_username = original_sender_row[0]
        
        cur.execute(
            "SELECT COUNT(*) FROM reblooms WHERE original_bloom_id = %s",
            (bloom_id,),
        )
        rebloom_count_row = cur.fetchone()
        rebloom_count = rebloom_count_row[0] if rebloom_count_row else 0
        
        return Bloom(
            id=bloom_id,
            sender=rebloomer.username,
            content=content,
            sent_timestamp=rebloom_timestamp,
            original_sender=original_sender_username,
            rebloomer=rebloomer.username,
            rebloom_count=rebloom_count,
        )


def get_rebloom_count(bloom_id: int) -> int:
    with db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM reblooms WHERE original_bloom_id = %s",
            (bloom_id,),
        )
        row = cur.fetchone()
        return row[0] if row else 0


def get_reblooms_for_user(username: str, *, limit: Optional[int] = None) -> List[Bloom]:
    """Get all reblooms made by a user (for their feed)"""
    with db_cursor() as cur:
        kwargs = {"username": username}
        limit_clause = make_limit_clause(limit, kwargs)
        
        cur.execute(
            f"""SELECT
              blooms.id,
              rebloomer_user.username as rebloomer_username,
              original_sender_user.username as original_sender_username,
              blooms.content,
              reblooms.rebloom_timestamp,
              (SELECT COUNT(*) FROM reblooms r2 WHERE r2.original_bloom_id = blooms.id) as rebloom_count
            FROM reblooms
            INNER JOIN blooms ON reblooms.original_bloom_id = blooms.id
            INNER JOIN users rebloomer_user ON reblooms.rebloomer_id = rebloomer_user.id
            INNER JOIN users original_sender_user ON blooms.sender_id = original_sender_user.id
            WHERE rebloomer_user.username = %(username)s
            ORDER BY reblooms.rebloom_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        reblooms_list = []
        for row in rows:
            bloom_id, rebloomer_username, original_sender_username, content, rebloom_timestamp, rebloom_count = row
            reblooms_list.append(
                Bloom(
                    id=bloom_id,
                    sender=rebloomer_username,
                    content=content,
                    sent_timestamp=rebloom_timestamp,
                    original_sender=original_sender_username,
                    rebloomer=rebloomer_username,
                    rebloom_count=rebloom_count or 0,
                )
            )
    return reblooms_list
