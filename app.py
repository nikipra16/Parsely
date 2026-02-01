import os
import pickle
import datetime
import base64
import argparse
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import json
from email_parser import parse_email
from postgresDB import (
    upsert_order_with_items,
    upsert_raw_gmail,
    pipeline_start,
    pipeline_end,
    db_gmail_ids,
    fetch_raw_gmail_in_range,
)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class Parsely:
    def __init__(self, cred_file='priv_data/credentials.json', token_file='priv_data/token.pickle'):
        self.cred_file = cred_file
        self.token_file = token_file
        self.service = None

    def authenticate(self):
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    # Recover by deleting the token file and forcing a new OAuth consent flow.
                    print(f"Token refresh failed ({e}). Re-authenticating...")
                    try:
                        os.remove(self.token_file)
                    except OSError:
                        pass
                    # Fall back to interactive OAuth consent flow
                    flow = InstalledAppFlow.from_client_secrets_file(self.cred_file, SCOPES)
                    creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.cred_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Only persist if we actually obtained credentials
            if creds:
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)
        print('Authenticated!')

    @staticmethod
    def html_to_text(html_email: str) -> str:
        soup = BeautifulSoup(html_email, "html.parser")
        text = soup.get_text(separator="\n")
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())

    def get_email_body(self, email_data):
        body = ""
        payload = email_data.get('payload', {})
        parts = payload.get('parts', [])

        if not parts:
            data = payload.get('body', {}).get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                body = self.html_to_text(body)
            return body

        for part in parts:
            mimeType = part.get('mimeType')
            data = part.get('body', {}).get('data')
            if data:
                decoded = base64.urlsafe_b64decode(data).decode('utf-8')
                if mimeType == 'text/plain':
                    body += decoded
                elif mimeType == 'text/html' and not body:
                    body += self.html_to_text(decoded)
        return body

    def get_email_html(self, email_data):
        payload = email_data.get('payload', {})
        parts = payload.get('parts', [])

        if not parts:
            data = payload.get('body', {}).get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
            return ""

        for part in parts:
            mimeType = part.get('mimeType')
            data = part.get('body', {}).get('data')
            if data and mimeType == 'text/html':
                return base64.urlsafe_b64decode(data).decode('utf-8')
        return ""

    def is_food_order_email(self, subject, body, from_email):
        subject_lower = subject.lower()

        # currently works for doordash and instacart 
        food_keywords = ['order confirmation', 'your instacart order receipt']

        if any(keyword in subject_lower for keyword in food_keywords):
            return True
        return False


    def list_food_email_ids(self, *, start_date: str, end_date: str, stores: list[str], limit: int) -> list[str]:
        start_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)

        store_query = " OR ".join(stores)
        query = (
            f"after:{start_obj.strftime('%Y/%m/%d')} "
            f"before:{end_obj.strftime('%Y/%m/%d')} "
            f"from:({store_query})"
        )

        ids: list[str] = []
        seen: set[str] = set()
        page_token = None

        while True and len(ids) < limit:
            resp = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=min(100, limit - len(ids)),
                pageToken=page_token,
            ).execute()

            for msg in resp.get("messages", []) or []:
                mid = msg.get("id")
                if mid and mid not in seen:
                    seen.add(mid)
                    ids.append(mid)
                    if len(ids) >= limit:
                        break

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return ids


    def ensure_raw_gmail_cached(self, *, gmail_ids: list[str]) -> int:
        """
        Returns: number of *newly fetched* emails (get/full) inserted into raw_gmail
        """
        existing = db_gmail_ids(gmail_ids)
        missing = [mid for mid in gmail_ids if mid not in existing]

        newly_fetched = 0
        for mid in missing:
            email_data = self.service.users().messages().get(
                userId="me",
                id=mid,
                format="full",
            ).execute()

            from_email = ""
            subject = ""
            for header in email_data.get("payload", {}).get("headers", []) or []:
                nm = (header.get("name") or "").lower()
                if nm == "from":
                    from_email = header.get("value") or ""
                elif nm == "subject":
                    subject = header.get("value") or ""

            internal_date = email_data.get("internalDate")
            email_ts = None
            if internal_date:
                email_ts = datetime.datetime.fromtimestamp(int(internal_date) / 1000, tz=datetime.timezone.utc)

            upsert_raw_gmail(
                {
                    "gmail_id": mid,
                    "date_ts": email_ts,
                    "subject": subject,
                    "from_email": from_email,
                    "body": self.get_email_body(email_data),
                    "html_body": self.get_email_html(email_data),
                }
            )
            newly_fetched += 1

        return newly_fetched


    def fetch_food_emails_cached(self, *, start_date: str, end_date: str, stores: list[str], limit: int) -> list[dict]:
        gmail_ids = self.list_food_email_ids(
            start_date=start_date,
            end_date=end_date,
            stores=stores,
            limit=limit,
        )

        # only for missing: get(full) → upsert_raw_gmail
        self.ensure_raw_gmail_cached(gmail_ids=gmail_ids)

        # transforms from postgres
        return fetch_raw_gmail_in_range(
            start_date=start_date,
            end_date=end_date,
            stores=stores,
            limit=limit,
        )


    def save_orders_to_files(self, grocery_orders, dining_orders, unknown_orders):
        """Save orders to JSON files based on category (grocery or dining)"""
        
        # Save grocery orders
        if grocery_orders:
            with open('data/grocery_orders.json', 'w', encoding='utf-8') as f:
                json.dump(grocery_orders, f, indent=2)

        
        # Save dining orders
        if dining_orders:
            with open('data/dining_orders.json', 'w', encoding='utf-8') as f:
                json.dump(dining_orders, f, indent=2)

        
        # Save unknown orders (optional)
        if unknown_orders:
            with open('data/unknown_orders.json', 'w', encoding='utf-8') as f:
                json.dump(unknown_orders, f, indent=2)
    
    def parse_and_categorize_emails(self, max_results=400, start_date=None, end_date=None, save_json=False):
        if self.service is None:
            print("Please authenticate first!")
            return []

        emails = []
        pipeline_id = None

        grocery_orders = []
        dining_orders = []
        unknown_orders = []
        category_counts = {"Grocery": 0, "Dining": 0, "Unknown": 0}

        emails_loaded = 0
        grocery_orders_upserted = 0
        grocery_orders_with_total = 0

        status = "success"
        err = None

        try:
            # emails = self.fetch_food_emails(
            #     limit=max_results,
            #     save_to_file=False,
            #     start_date=start_date,
            #     end_date=end_date,
            # )
            emails = self.fetch_food_emails_cached(
                start_date=start_date,
                end_date=end_date,
                stores=[
                    "walmart.com",
                    "loblaws.ca",
                    "costco.ca",
                    "instacart.com",
                    "tntsupermarket.com",
                    "doordash.com",
                    "ubereats.com",
                    "skipthedishes.com",
                ],
                limit=max_results,
            )
            if not emails:
                print("No emails found to parse")
                return []

            pipeline_id = pipeline_start(
                start_date=start_date,
                end_date=end_date,
                limit_emails=max_results,
            )

            for email in emails:
                raw_date = email.get("date")
                email_ts = None
                if raw_date:
                    email_ts = datetime.datetime.fromtimestamp(int(raw_date) / 1000, tz=datetime.timezone.utc)

                upsert_raw_gmail(
                    {
                        "gmail_id": email.get("gmail_id"),
                        "date_ts": email_ts,
                        "subject": email.get("subject"),
                        "from_email": email.get("from", ""),
                        "body": email.get("body", ""),
                        "html_body": email.get("html_body", ""),
                    }
                )
                emails_loaded += 1

                try:
                    if not self.is_food_order_email(
                        email.get("subject", ""),
                        email.get("body", ""),
                        email.get("from", ""),
                    ):
                        continue

                    parsed_data = parse_email(
                        email["body"],
                        from_email=email.get("from", ""),
                        subject=email.get("subject", ""),
                        raw_html=email.get("html_body", ""),
                    )

                    if not parsed_data.get("items"):
                        print(f"  Skipped email with no items: {email.get('subject', '')[:50]}...")
                        continue

                    parsed_data["gmail_id"] = email.get("gmail_id")
                    parsed_data["date"] = email.get("date")
                    parsed_data["from"] = email.get("from", "")

                    gmail_id = parsed_data.get("gmail_id")
                    if not gmail_id:
                        print("  Skipped email with missing gmail_id")
                        continue

                    category = parsed_data.get("category", "Unknown")
                    category_counts[category] += 1

                    if category == "Grocery":
                        grocery_orders.append(parsed_data)

                        # `date` is stored as epoch-ms string (Gmail internalDate)
                        order_ts = None
                        raw_date = parsed_data.get("date")
                        if raw_date:
                            try:
                                order_ts = datetime.datetime.fromtimestamp(
                                    int(raw_date) / 1000,
                                    tz=datetime.timezone.utc,
                                )
                            except Exception:
                                order_ts = None

                        if order_ts:
                            total_val = (parsed_data.get("totals") or {}).get("total")
                            if total_val is not None:
                                grocery_orders_with_total += 1

                            # Atomic load: order + items in one transaction
                            upsert_order_with_items(
                                {
                                    "gmail_id": gmail_id,
                                    "order_ts": order_ts,
                                    "store_name": parsed_data.get("store_name"),
                                    "category": parsed_data.get("category"),
                                    "from_email": parsed_data.get("from", ""),
                                    "total": total_val,
                                },
                                parsed_data.get("items") or [],
                            )
                            grocery_orders_upserted += 1

                    elif category == "Dining":
                        dining_orders.append(parsed_data)
                    else:
                        unknown_orders.append(parsed_data)

                    print(f"Parsed email {email['gmail_id']}: {len(parsed_data['items'])} items - {category}")

                except Exception as e:
                    print(f"Error parsing email {email['gmail_id']}: {e}")
                    error_email = {
                        "items": [],
                        "totals": {},
                        "category": "Unknown",
                        "store_name": "",
                        "gmail_id": email["gmail_id"],
                        "date": email["date"],
                        "from": email.get("from", ""),
                        "error": str(e),
                    }
                    unknown_orders.append(error_email)
                    category_counts["Unknown"] += 1

            if grocery_orders_upserted:
                total_completeness_pct = (grocery_orders_with_total / grocery_orders_upserted) * 100
                print(
                    f"Total completeness: {grocery_orders_with_total}/{grocery_orders_upserted} "
                    f"({total_completeness_pct:.1f}%)"
                )

            if save_json:
                self.save_orders_to_files(grocery_orders, dining_orders, unknown_orders)

            print("\nParsing complete!")
            print(
                f"Category breakdown: {category_counts['Grocery']} Grocery, "
                f"{category_counts['Dining']} Dining, {category_counts['Unknown']} Unknown"
            )

            return {"grocery": grocery_orders, "dining": dining_orders, "unknown": unknown_orders}

        except Exception as e:
            status = "failed"
            err = str(e)
            raise

        finally:
            if pipeline_id is not None:
                grocery_orders_missing_total = grocery_orders_upserted - grocery_orders_with_total
                pipeline_end(
                    run_id=pipeline_id,
                    emails_loaded=emails_loaded,
                    emails_fetched=len(emails) if emails else 0,
                    orders_upserted=grocery_orders_upserted,
                    orders_with_total=grocery_orders_with_total,
                    orders_missing_total=grocery_orders_missing_total,
                    status=status,
                    error=err,
                )
        


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Parsely Gmail receipt ETL → PostgreSQL")
    p.add_argument("--start-date", dest="start_date", default="2025-12-05", help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end-date", dest="end_date", default="2025-12-23", help="YYYY-MM-DD (inclusive)")
    p.add_argument("--limit", dest="max_results", type=int, default=400, help="Max emails to fetch")
    p.add_argument("--save-json", action="store_true", help="Also write parsed outputs to data/*.json (optional)")
    args = p.parse_args()

    parsely = Parsely()
    parsely.authenticate()

    # results = parsely.parse_and_categorize_emails(
    #     max_results=400,
    #     start_date="2024-01-01",
    #     end_date="2025-04-05"
    # )
    results = parsely.parse_and_categorize_emails(
        max_results=args.max_results,
        start_date=args.start_date,
        end_date=args.end_date,
        save_json=args.save_json,
    )

    if results:
        grocery_orders = results.get('grocery', [])
        dining_orders = results.get('dining', [])
        unknown_orders = results.get('unknown', [])

        total_items = sum(len(email.get('items', [])) for email in grocery_orders + dining_orders + unknown_orders)
        total_spending = sum(email.get('totals', {}).get('total', 0) for email in grocery_orders + dining_orders + unknown_orders)
        
        # Find the earliest date processed
        all_orders = grocery_orders + dining_orders + unknown_orders
        
        print(f"\nProcessing Complete!")
        print(f"Total items parsed: {total_items}")
        print(f"Total spending: ${total_spending:.2f}")

        grocery_spending = sum(email.get('totals', {}).get('total', 0) for email in grocery_orders)
        dining_spending = sum(email.get('totals', {}).get('total', 0) for email in dining_orders)
        
        print(f"\n Spending Breakdown:")
        print(f" Grocery: ${grocery_spending:.2f}")
        print(f" Dining: ${dining_spending:.2f}")
    else:
        print("No emails were parsed successfully")
