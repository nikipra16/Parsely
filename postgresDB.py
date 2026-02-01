import os
from dotenv import load_dotenv
import psycopg
from typing import Iterable

load_dotenv()

def connect_pg():
    return psycopg.connect(
        host = os.getenv("POSTGRES_HOST"),
        port = os.getenv("POSTGRES_PORT"),
        dbname = os.getenv("POSTGRES_DB"),
        user = os.getenv("POSTGRES_USER"),
        password = os.getenv("POSTGRES_PASSWORD"),
    )

# def upsert_order(order):
#     # NOTE: %(gmail_id)s, %(order_ts)s, etc are filled from the Python dict passed to cur.execute(sql, order)

#     sql = """
#     insert into orders (gmail_id, order_ts, store_name, category, from_email, total)
#     values (%(gmail_id)s, %(order_ts)s, %(store_name)s, %(category)s, %(from_email)s, %(total)s)
#     on conflict (gmail_id) do update set
#       order_ts = excluded.order_ts,
#       store_name = excluded.store_name,
#       category = excluded.category,
#       from_email = excluded.from_email,
#       total = excluded.total
#     returning id;
#     """
#     with connect_pg() as conn:
#         with conn.cursor() as cur:
#             cur.execute(sql, order)
#             return cur.fetchone()[0]

# def replace_order_items(order_id:int, items:list[dict]) -> None:
#     with connect_pg() as conn:
#         with conn.cursor() as cur:

#             cur.execute("delete from order_items where order_id = %s", (order_id,))

#             for it in items:
#                 cur.execute(
#                     """
#                     insert into order_items (order_id, brand, item_name, quantity, item_price)
#                     values (%s, %s, %s, %s, %s)
#                     """,
#                     (
#                         order_id,
#                         it.get("brand"),
#                         it.get("name") or it.get("item_name"),
#                         it.get("qty") or it.get("quantity"),
#                         it.get("price") or it.get("item_price"),
#                     ),
#                 )

def upsert_order_with_items(order: dict, items: list[dict]) -> int:
    """
    Atomically:
      1) upsert into `orders` (by gmail_id) and get order_id
      2) replace all `order_items` rows for that order_id

    If anything fails, the whole transaction rolls back.
    """
    sql_upsert_order = """
    insert into orders (gmail_id, order_ts, store_name, category, from_email, total)
    values (%(gmail_id)s, %(order_ts)s, %(store_name)s, %(category)s, %(from_email)s, %(total)s)
    on conflict (gmail_id) do update set
      order_ts = excluded.order_ts,
      store_name = excluded.store_name,
      category = excluded.category,
      from_email = excluded.from_email,
      total = excluded.total
    returning id;
    """

    with connect_pg() as conn:
        with conn.cursor() as cur:
            # upsert order
            cur.execute(sql_upsert_order, order)
            order_id = cur.fetchone()[0]

            # replace items
            cur.execute("delete from order_items where order_id = %s", (order_id,))

            for it in items or []:
                cur.execute(
                    """
                    insert into order_items (order_id, brand, item_name, quantity, item_price)
                    values (%s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        it.get("brand"),
                        it.get("name") or it.get("item_name"),
                        it.get("qty") or it.get("quantity"),
                        it.get("price") or it.get("item_price"),
                    ),
                )

            return order_id

def upsert_raw_gmail(data):
    
    sql = """ 
    insert into raw_gmail(gmail_id, date_ts, subject, from_email, body, html_body)
    values (%(gmail_id)s, %(date_ts)s, %(subject)s, %(from_email)s, %(body)s, %(html_body)s)
    on conflict (gmail_id) do update set
      date_ts = excluded.date_ts,
      subject = excluded.subject,
      from_email = excluded.from_email,
      body = excluded.body,
      html_body = excluded.html_body;
    """
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, data)
            
# * makes the arguments after it keyword-only
def pipeline_start(*,start_date:None, end_date:None, limit_emails:None) -> int:
    sql = """
    insert into pipeline_run(start_date, end_date, limit_emails)
    values (%(start_date)s, %(end_date)s, %(limit_emails)s)
    returning id;
    """
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "start_date": start_date,
                "end_date": end_date,
                "limit_emails": limit_emails
            })
            return cur.fetchone()[0]


def pipeline_end(
    *,
    run_id: int,
    emails_loaded: int | None = None,
    emails_fetched: int | None = None,
    orders_upserted: int | None = None,
    orders_with_total: int | None = None,
    orders_missing_total: int | None = None,
    status: str | None = None,
    error: str | None = None,
) -> None:
    sql = """
    update pipeline_run
    set status = %(status)s, error = %(error)s, ended_at = now(), 
    emails_fetched = %(emails_fetched)s,
    emails_loaded = %(emails_loaded)s,
    orders_upserted = %(orders_upserted)s,
    orders_with_total = %(orders_with_total)s,
    orders_missing_total = %(orders_missing_total)s
    where id = %(run_id)s;
    """
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "run_id": run_id,
                "status": status,
                "error": error,
                "emails_fetched": emails_fetched,
                "emails_loaded": emails_loaded,
                "orders_upserted": orders_upserted,
                "orders_with_total": orders_with_total,
                "orders_missing_total": orders_missing_total,
            })


def db_gmail_ids(gmail_ids: list[str]) -> set[str]:
    if not gmail_ids:
        return set()

    sql = "select gmail_id from raw_gmail where gmail_id = any(%s::text[])"
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (gmail_ids,))
            return {row[0] for row in cur.fetchall()}


def fetch_raw_gmail(
    *,
    start_date: str,  
    end_date: str,   
    stores: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    
    sql = """
    select gmail_id, date_ts, subject, from_email, body, html_body
    from raw_gmail
    where date_ts >= (%s::date at time zone 'utc')
      and date_ts < ((%s::date + interval '1 day') at time zone 'utc')
    """
    params: list[object] = [start_date, end_date]

    if stores:
        ors = " or ".join(["from_email ilike %s"] * len(stores))
        sql += f"\n  and ({ors})"
        params.extend([f"%{s}%" for s in stores])

    sql += "\norder by date_ts asc, gmail_id asc"

    if limit is not None:
        sql += "\nlimit %s"
        params.append(limit)

    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    out: list[dict] = []
    for gmail_id, date_ts, subject, from_email, body, html_body in rows:
        epoch_ms = int(date_ts.timestamp() * 1000) if date_ts else None
        out.append(
            {
                "gmail_id": gmail_id,
                "date": str(epoch_ms) if epoch_ms is not None else None,
                "subject": subject or "",
                "from": from_email or "",
                "body": body or "",
                "html_body": html_body or "",
            }
        )
    return out


def fetch_raw_gmail_in_range(
    *,
    start_date: str,
    end_date: str,
    stores: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:

    return fetch_raw_gmail(
        start_date=start_date,
        end_date=end_date,
        stores=stores,
        limit=limit,
    )