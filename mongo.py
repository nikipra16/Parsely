from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus
import pandas as pd

load_dotenv()

def connect_to_mongodb():
    MONGO_USER = os.getenv("MONGO_USER")
    MONGO_PASS = os.getenv("MONGO_PASS")
    MONGO_PASS_ENCODED = quote_plus(MONGO_PASS)

    uri = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS_ENCODED}@parselycluster.ao1xtao.mongodb.net/?retryWrites=true&w=majority&appName=ParselyCluster"
    
    client = MongoClient(uri, server_api=ServerApi('1'))
    
    try:
        client.admin.command('ping')
        print("Connected to MongoDB!")
        db = client['ParselyDB']
        return client, db
    except Exception as e:
        print(e)
        return None, None

def test_connection():
    client, db = connect_to_mongodb()
    if client is not None and db is not None:
        print("Connection test successful!")
        return True
    return False


def upsert_orders(file_path, collection_name):
    # update or insert orders
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return False
        
    collection = db[collection_name]

    updated_count = 0
    inserted_count = 0

    with open(file_path, 'r') as f:
        orders = json.load(f)

    for order in orders:
        if 'order_id' in order:
            # id_value = order['order_id']
            result = collection.replace_one(
                {'order_id': order['order_id']},
                order,
                upsert=True
            )
        elif 'gmail_id' in order:
            # id_value = order['gmail_id']
            result = collection.replace_one(
                {'gmail_id': order['gmail_id']},
                order,
                upsert=True
            )
        else:
            continue
        
        if result.upserted_id:
            inserted_count += 1
        else:
            updated_count += 1
            
    return True

def export_to_csv(collection_name, output_file):
    client, db = connect_to_mongodb()
    collection = db[collection_name]

    data = list(collection.find({}))

    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)


def export_to_csv_all():
    """Export all collections to CSV files for Tableau"""
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return False
    
    grocery_data = list(db['grocery_orders'].find({}))
    grocery_df = pd.DataFrame(grocery_data)
    grocery_df.to_csv('grocery_orders.csv', index=False)
     
    dining_data = list(db['dining_orders'].find({}))
    dining_df = pd.DataFrame(dining_data)
    dining_df.to_csv('dining_orders.csv', index=False)
    
    return True

def main():
    # Test connection
    if test_connection():
        upsert_orders('data/grocery_orders.json', 'grocery_og')
        upsert_orders('data/simulated_grocery_orders.json', 'grocery_orders')
        # upsert_orders('data/dining_orders.json', 'dining_orders')
        
        # export_to_csv_all()

if __name__ == "__main__":
    main()