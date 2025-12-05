from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus
import pandas as pd
import ast

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

def export_grocery_items_flattened(collection_name='grocery_og', output_file='grocery_items_flattened.csv'):
  
    client, db = connect_to_mongodb()
    if client is None or db is None:
        print("Database connection failed")
        return False
    
    collection = db[collection_name]
    orders = list(collection.find({}))
    
    if not orders:
        print(f"No data found in collection '{collection_name}'")
        return False
    
    flattened_data = []
    
    for order in orders:
        # Get order-level info
        order_date = order.get('date', '')
        store_name = order.get('store_name', '')
        category = order.get('category', '')
        gmail_id = order.get('gmail_id', '')
        order_id = order.get('order_id', '')
        
        # Get totals (handle both dict and string formats)
        totals = order.get('totals', {})
        if isinstance(totals, str):
            try:
                totals = ast.literal_eval(totals)  # Safer than eval()
            except (ValueError, SyntaxError):
                totals = {}
        
        order_total = totals.get('total', order.get('total', 0)) if isinstance(totals, dict) else order.get('total', 0)
        order_subtotal = totals.get('subtotal', order.get('subtotal', 0)) if isinstance(totals, dict) else order.get('subtotal', 0)
        order_tax = totals.get('tax', totals.get('taxes', 0)) if isinstance(totals, dict) else 0
        
        # Get items (handle both list and string formats)
        items = order.get('items', [])
        if isinstance(items, str):
            try:
                items = ast.literal_eval(items)  # Safer than eval()
            except (ValueError, SyntaxError):
                items = []
        
        # If no items, create one row with order info
        if not items:
            flattened_data.append({
                'order_date': order_date,
                'order_id': order_id,
                'gmail_id': gmail_id,
                'store_name': store_name,
                'category': category,
                'brand': '',
                'item_name': 'No items parsed',
                'quantity': 0,
                'item_price': 0,
                'item_total': 0,
                'order_total': order_total,
                'order_subtotal': order_subtotal,
                'order_tax': order_tax
            })
        else:
            # One row per item
            for item in items:
                # Handle both data structures
                if 'product' in item:
                    # Simulated data structure
                    brand = ''
                    item_name = item.get('product', '')
                    quantity = item.get('quantity', 0)
                    item_price = item.get('price_per_unit', 0)
                    item_total = item.get('total_price', quantity * item_price)
                else:
                    # Real parsed data structure
                    brand = item.get('brand', '')
                    item_name = item.get('name', '')
                    quantity = item.get('qty', 0)
                    item_price = item.get('price', 0)
                    item_total = quantity * item_price
                
                flattened_data.append({
                    'order_date': order_date,
                    'order_id': order_id,
                    'gmail_id': gmail_id,
                    'store_name': store_name,
                    'category': category,
                    'brand': brand,
                    'item_name': item_name,
                    'quantity': quantity,
                    'item_price': item_price,
                    'item_total': item_total,
                    'order_total': order_total,
                    'order_subtotal': order_subtotal,
                    'order_tax': order_tax
                })
    
    # Create DataFrame and export as CSV
    df = pd.DataFrame(flattened_data)
    df.to_csv(output_file, index=False)
    
    print(f"Exported {len(flattened_data)} items from {len(orders)} orders to '{output_file}'")
    print(f"Columns: {', '.join(df.columns)}")
    
    return True

def validate_data_quality(collection_name='grocery_og'):
    """
    Use MongoDB aggregations to perform data quality validation checks
    Returns validation report with issues found
    """
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return None
    
    collection = db[collection_name]
    validation_report = {'total_orders': 0, 'issues': []}
    
    # mongoDB aggregation pipeline
    order_quality_pipeline = [
        {
            "$project": {
                "missing_gmail_id": {"$cond": [{"$ifNull": ["$gmail_id", False]}, 0, 1]},
                "missing_date": {"$cond": [{"$ifNull": ["$date", False]}, 0, 1]},
                "missing_items": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$items", []]}}, 0]}, 0, 1]},
                "missing_totals": {"$cond": [{"$ifNull": ["$totals", False]}, 0, 1]},
                "missing_store_name": {"$cond": [{"$ifNull": ["$store_name", False]}, 0, 1]}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_orders": {"$sum": 1},
                "missing_gmail_id": {"$sum": "$missing_gmail_id"},
                "missing_date": {"$sum": "$missing_date"},
                "missing_items": {"$sum": "$missing_items"},
                "missing_totals": {"$sum": "$missing_totals"},
                "missing_store_name": {"$sum": "$missing_store_name"}
            }
        }
    ]
    
    result = list(collection.aggregate(order_quality_pipeline))
    if result:
        stats = result[0]
        validation_report['total_orders'] = stats.get('total_orders', 0)
        
        field_checks = [
            ('gmail_id', 'high'), ('date', 'high'), ('items', 'high'),
            ('totals', 'medium'), ('store_name', 'medium')
        ]
        for field, severity in field_checks:
            count = stats.get(f'missing_{field}', 0)
            if count > 0:
                validation_report['issues'].append({
                    'type': 'Missing Field',
                    'field': field,
                    'count': count,
                    'severity': severity
                })
    
    # Combined check: Item-level validation (prices, quantities, names)
    item_quality_pipeline = [
        {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "invalid_price": {"$or": [
                    {"$not": {"$ifNull": ["$items.price", False]}},
                    {"$lte": ["$items.price", 0]},
                    {"$gt": ["$items.price", 10000]}
                ]},
                "invalid_qty": {"$or": [
                    {"$not": {"$ifNull": ["$items.qty", False]}},
                    {"$lte": ["$items.qty", 0]},
                    {"$gt": ["$items.qty", 1000]}
                ]},
                "missing_name": {"$or": [
                    {"$not": {"$ifNull": ["$items.name", False]}},
                    {"$eq": ["$items.name", ""]}
                ]}
            }
        },
        {
            "$group": {
                "_id": None,
                "invalid_prices": {"$sum": {"$cond": ["$invalid_price", 1, 0]}},
                "invalid_quantities": {"$sum": {"$cond": ["$invalid_qty", 1, 0]}},
                "missing_names": {"$sum": {"$cond": ["$missing_name", 1, 0]}}
            }
        }
    ]
    
    result = list(collection.aggregate(item_quality_pipeline))
    if result:
        stats = result[0]
        if stats.get('invalid_prices', 0) > 0:
            validation_report['issues'].append({
                'type': 'Invalid Value',
                'field': 'item.price',
                'count': stats['invalid_prices'],
                'severity': 'high',
                'description': 'Price must be > 0 and < 10000'
            })
        if stats.get('invalid_quantities', 0) > 0:
            validation_report['issues'].append({
                'type': 'Invalid Value',
                'field': 'item.qty',
                'count': stats['invalid_quantities'],
                'severity': 'high',
                'description': 'Quantity must be > 0 and < 1000'
            })
        if stats.get('missing_names', 0) > 0:
            validation_report['issues'].append({
                'type': 'Missing Field',
                'field': 'item.name',
                'count': stats['missing_names'],
                'severity': 'medium'
            })
    
    # Check for duplicate gmail_ids
    duplicate_pipeline = [
        {"$group": {"_id": "$gmail_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}, "_id": {"$ne": None}}},
        {"$group": {"_id": None, "duplicate_count": {"$sum": 1}}}
    ]
    
    result = list(collection.aggregate(duplicate_pipeline))
    if result and result[0].get('duplicate_count', 0) > 0:
        validation_report['issues'].append({
            'type': 'Data Integrity',
            'field': 'gmail_id',
            'count': result[0]['duplicate_count'],
            'severity': 'high',
            'description': 'Duplicate IDs found'
        })
    
    return validation_report

def print_validation_report(collection_name='grocery_og'):
    """Print a formatted validation report"""
    report = validate_data_quality(collection_name)
    
    if not report:
        return None
    
    print(f"\nData Quality Validation: {collection_name}")
    print(f"Total Orders: {report['total_orders']} | Issues: {len(report['issues'])}")
    
    if not report['issues']:
        print("No issues found")
        return report
    
    for issue in report['issues']:
        severity = issue['severity'].upper()
        field = issue['field']
        count = issue['count']
        desc = issue.get('description', '')
        print(f"  [{severity}] {field}: {count}" + (f" - {desc}" if desc else ""))
    
    return report

def main():
    # Test connection
    if test_connection():
        upsert_orders('data/grocery_orders.json', 'grocery_og')
        # upsert_orders('data/simulated_grocery_orders.json', 'grocery_orders')
        # upsert_orders('data/dining_orders.json', 'dining_orders')
        
        # Data quality validation using aggregations
        print_validation_report(collection_name='grocery_og')
        
        # Export flattened (better for Excel)
        export_grocery_items_flattened(collection_name='grocery_og', output_file='grocery_items_flattened.csv')
        
        # Or export raw nested structure
        # export_to_csv_all()

if __name__ == "__main__":
    main()