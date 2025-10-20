import os
import pickle
import datetime
import base64
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import json
from email_parser import parse_email

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class Parsely:
    def __init__(self, cred_file='priv_data/credentials.json', token_file='priv_data/token.pickle'):
        self.cred_file = cred_file
        self.token_file = token_file
        self.service = None
        self.store_names = [
            'walmart', 'save-on-foods', 'freshco', 'loblaws', 'costco', 
            'tnt', 'superstore', 'no frills', 'metro', 'sobeys', 'pc express'
        ]

    def authenticate(self):
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.cred_file, SCOPES)
                creds = flow.run_local_server(port=0)
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

        promo_keywords = [
            'newsletter', 'unsubscribe', 'marketing', 'advertisement', 'ad',
            'verification code', 'password reset', 'account', 'login',
            'welcome', 'thank you for signing up', 'confirm your email',
            'update your preferences', 'manage your account',
            'rate your experience', 'feedback', 'survey',
            'coming soon', 'announcement', 'new menu launch',
            'dashpass membership', 'membership paused', 'membership cancelled',
            'a world of food awaits', 'explore new restaurants',"discount",
            'no-contact delivery'
        ]

        if any(keyword in subject_lower for keyword in promo_keywords):
            return False
        return True


    def fetch_food_emails(self, months=24, stores=None, limit=100, save_to_file=False, start_date=None, end_date=None):
        """Fetch Gmail emails in batches of 100, going through multiple months.
        
        Args:
            months: Number of months to go back
            stores: List of stores to filter by
            limit: Maximum number of emails to fetch
            save_to_file: Whether to save raw emails to file
            start_date: Start date in format 'YYYY-MM-DD' (optional)
            end_date: End date in format 'YYYY-MM-DD' (optional)
        """
        if self.service is None:
            raise Exception('Authenticate first!')

        if stores is None:
            #OPTIMIZE
            stores = [
                'walmart.com', 'loblaws.ca', 'costco.ca',
                'instacart.com', 'tntsupermarket.com', 'doordash.com',
                'ubereats.com', 'skipthedishes.com', 'grubhub.com',
                'mcdonalds.com', 'kfc.com', 'burgerking.com', 'subway.com',
                'pizzahut.com', 'dominos.com', 'wendys.com', 'tacobell.com'
            ]

        all_food_emails = []
        batch_size = 100
        total_processed = 0

        for month_offset in range(months):
            if start_date and end_date:
                start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
                # print(f"\nProcessing date range: {start_date} to {end_date}")
                store_query = " OR ".join(stores)
                query = f"after:{start_date_obj.strftime('%Y/%m/%d')} before:{end_date_obj.strftime('%Y/%m/%d')} from:({store_query})"
            else:
                end_date = datetime.date.today() - datetime.timedelta(days=30*month_offset)
                start_date_obj = end_date - datetime.timedelta(days=30)
                
                start_date_str = end_date - datetime.timedelta(days=30)
                end_date_str = datetime.date.today()
                
                print(f"\nProcessing month {month_offset + 1}/{months}: {start_date_str} to {end_date_str}")
                
                store_query = " OR ".join(stores)
                query = f"after:{start_date_obj.strftime('%Y/%m/%d')} from:({store_query})"

            page_token = None
            month_emails = []
            
            while True:
                response = self.service.users().messages().list(
                    userId='me', 
                    q=query, 
                    maxResults=batch_size,
                    pageToken=page_token
                ).execute()
                
                messages = response.get('messages', [])
                if not messages:
                    break
                
                print(f"  Found {len(messages)} emails in this batch")
                
                # Process each email in this batch
                for msg in messages:
                    try:
                        email_data = self.service.users().messages().get(
                            userId='me',
                            id=msg['id'],
                            format='full'
                        ).execute()
                        
                        # Extract email details
                        from_email = ""
                        subject = ""
                        body = self.get_email_body(email_data)
                        html_body = self.get_email_html(email_data)
                        
                        for header in email_data['payload'].get('headers', []):
                            if header['name'].lower() == 'from':
                                from_email = header['value']
                            elif header['name'].lower() == 'subject':
                                subject = header['value']
                        

                        if not any(store in from_email for store in stores):
                            continue
                        

                        if not self.is_food_order_email(subject, body, from_email):
                            print(f"  Skipped promotional email: {subject[:50]}...")
                            continue

                        internal_date = email_data.get("internalDate", "")
                        if internal_date:
                            timestamp = int(internal_date) / 1000
                            readable_date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            readable_date = ""

                        month_emails.append({
                            "gmail_id": msg["id"],
                            "date": readable_date,
                            "subject": subject,
                            "from": from_email,
                            "body": body,
                            "html_body": html_body
                        })
                        total_processed += 1
                        print(f"  Added food order: {subject[:50]}...")
                            
                    except Exception as e:
                        print(f"  Error processing email {msg['id']}: {e}")
                        continue

                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            all_food_emails.extend(month_emails)
            print(f"  Month {month_offset + 1} complete: {len(month_emails)} food emails found")

            if total_processed >= limit:
                print(f"Reached total limit of {limit} emails")
                break
        
        print(f"\nTotal food emails found: {len(all_food_emails)}")
        
        if save_to_file:
            with open('data/food_emails.json', 'w', encoding='utf-8') as f:
                json.dump(all_food_emails, f, indent=2)
            print(f"Saved {len(all_food_emails)} food emails to data/food_emails.json")

        return all_food_emails

    def parse_and_categorize_emails(self, max_results=400, start_date=None, end_date=None):
        """Fetch emails and parse them directly, returning categorized results
        
        Args:
            max_results: Maximum number of emails to process
            start_date: Start date in format 'YYYY-MM-DD' (optional)
            end_date: End date in format 'YYYY-MM-DD' (optional)
        """
        if self.service is None:
            print("Please authenticate first!")
            return []

        emails = self.fetch_food_emails(limit=max_results, save_to_file=False, start_date=start_date, end_date=end_date)
        if not emails:
            print("No emails found to parse")
            return []

        grocery_orders = []
        dining_orders = []
        unknown_orders = []
        category_counts = {"Grocery": 0, "Dining": 0, "Unknown": 0}
        
        for email in emails:
            try:
                parsed_data = parse_email(
                    email['body'], 
                    from_email=email.get('from', ''), 
                    subject=email.get('subject', ''),
                    raw_html=email.get('html_body', '')
                )

                if not parsed_data.get('items'):
                    print(f"  Skipped email with no items: {email.get('subject', '')[:50]}...")
                    continue

                parsed_data['gmail_id'] = email['gmail_id']
                parsed_data['date'] = email['date']
                parsed_data['from'] = email.get('from', '')
                
                category = parsed_data.get('category', 'Unknown')
                category_counts[category] += 1

                if category == "Grocery":
                    grocery_orders.append(parsed_data)
                elif category == "Dining":
                    dining_orders.append(parsed_data)
                else:
                    unknown_orders.append(parsed_data)
                
                print(f"Parsed email {email['gmail_id']}: {len(parsed_data['items'])} items - {category}")
                
            except Exception as e:
                print(f"Error parsing email {email['gmail_id']}: {e}")
                # Add error email with minimal data
                error_email = {
                    'items': [],
                    'totals': {},
                    'category': 'Unknown',
                    'store_name': '',
                    'gmail_id': email['gmail_id'],
                    'date': email['date'],
                    'from': email.get('from', ''),
                    'error': str(e)
                }
                unknown_orders.append(error_email)
                category_counts['Unknown'] += 1

        self.save_orders_to_files(grocery_orders, dining_orders, unknown_orders)
        
        print(f"\nParsing complete!")
        print(f"Category breakdown: {category_counts['Grocery']} Grocery, {category_counts['Dining']} Dining, {category_counts['Unknown']} Unknown")
        
        return {
            "grocery": grocery_orders,
            "dining": dining_orders,
            "unknown": unknown_orders
        }

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
        
        # # Show summary
        # print(f"\n Summary:")
        # print(f"Grocery: {len(grocery_orders)} orders")
        # print(f"Dining: {len(dining_orders)} orders")
        # print(f"Unknown: {len(unknown_orders)} orders")


if __name__ == "__main__":
    parsely = Parsely()
    parsely.authenticate()

    results = parsely.parse_and_categorize_emails(
        max_results=400,
        start_date="2024-01-01",
        end_date="2025-04-05"
    )

    if results:
        grocery_orders = results.get('grocery', [])
        dining_orders = results.get('dining', [])
        unknown_orders = results.get('unknown', [])

        total_items = sum(len(email.get('items', [])) for email in grocery_orders + dining_orders + unknown_orders)
        total_spending = sum(email.get('totals', {}).get('total', 0) for email in grocery_orders + dining_orders + unknown_orders)
        
        # Find the earliest date processed
        all_orders = grocery_orders + dining_orders + unknown_orders
        if all_orders:
            all_orders.sort(key=lambda x: x.get('date', ''), reverse=False)  # Sort ascending for earliest
            earliest_date = all_orders[0].get('date', 'Unknown')
            print(f"\nEARLIEST EMAIL DATE PROCESSED: {earliest_date}")
        
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
