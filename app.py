import os
import pickle
import base64
import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class Parsely:
    def __init__(self, cred_file = 'credentials.json', token_file = 'token.pickle'):
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
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.cred_file, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)
        print('Authenticated!')

    def fetch_emails(self,months = 6, stores=None,save_path='data/raw_emails.txt'):
        if self.service is None:
            raise Exception('Authenticate first!')

        if stores is None:
            stores = ['doordash.com', 'walmart.com', 'loblaws.ca', 'costco.ca']

        #Gmail query
        start_date = (datetime.date.today() - datetime.timedelta(days=30*months)).strftime('%Y-%m-%d')
        store_name = " OR ".join(stores)
        query = f"after:{start_date} from:({store_name})"

        #Notes for myself
        # Gmail API organizes resources under “users.” your own account, we use userId='me'
        # messages() gives us access to methods to list, get, modify emails
        #list() is the method to fetch a list of emails
        response = self.service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])

        #to handle pagination of emails
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = self.service.users().messages().list(userId='me', q=query, maxResults=100, pageToken=page_token).execute()
            messages.extend(response.get('messages', []))

        print(f"Found {len(messages)} grocery emails")

        # os.makedirs(os.path.dirname(save_path), exist_ok=True)
        # with open(save_path, 'w', encoding='utf-8') as f:
        #     for msg in messages:
        #         email = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        #         snippet = email.get('snippet','')
        #         f.write(snippet+'\n\n')
        #
        # print(f"Saved grocery emails to {save_path}")

if __name__ == "__main__":
    parsely = Parsely()
    parsely.authenticate()

    # folder = input("Enter Gmail label/folder (default INBOX): ") or "INBOX"
    parsely.fetch_emails()