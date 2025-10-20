from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import json
from dotenv import load_dotenv
import pandas as pd
from functools import wraps
from bson import ObjectId
from firebase import get_firebase_config
from mongo import connect_to_mongodb

load_dotenv()

app = Flask(__name__)
CORS(app)


# No authentication needed for single-user PoC


@app.route('/')
def index():
    firebase_config = get_firebase_config()
    return render_template('index.html', firebase_config=firebase_config)


@app.route('/api/dashboard/stats')
def dashboard_stats():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    #more effciient, mongoDB does work
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_orders": {"$sum": 1},
                "total_spending": {"$sum": "$totals.total"},
                "total_items": {"$sum": {"$size": "$items"}},
                "store_counts": {
                    "$push": {
                        "store": "$store_name",
                        "spending": "$totals.total"
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "total_orders": 1,
                "total_spending": 1,
                "total_items": 1,
                "store_counts": 1
            }
        }
    ]
    
    result = list(db.grocery_og.aggregate(pipeline))
    
    if result:
        stats = result[0]
        total_grocery_orders = stats.get('total_orders', 0)
        total_grocery_spending = stats.get('total_spending', 0)
        total_items = stats.get('total_items', 0)
        
        store_counts = {}
        store_spending = {}
        
        for store_data in stats.get('store_counts', []):
            store = store_data.get('store', 'Unknown')
            spending = store_data.get('spending', 0)
            
            store_counts[store] = store_counts.get(store, 0) + 1
            store_spending[store] = store_spending.get(store, 0) + spending
        
        top_grocery_stores = sorted(store_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        store_spending_list = [{'store': store, 'spending': spending} for store, spending in store_spending.items()]
        store_spending_list.sort(key=lambda x: x['spending'], reverse=True)
    else:
        total_grocery_orders = 0
        total_grocery_spending = 0
        total_items = 0
        top_grocery_stores = []
        store_spending_list = []
    
    return jsonify({
        'total_orders': total_grocery_orders,
        'grocery_orders': total_grocery_orders,
        'total_spending': total_grocery_spending,
        'grocery_spending': total_grocery_spending,
        'total_items': total_items,
        'top_grocery_stores': top_grocery_stores,
        'store_spending_breakdown': store_spending_list
    })

@app.route('/api/orders/grocery')
def get_grocery_orders():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 20)), 100) 
    skip = (page - 1) * limit
    
    orders = list(db.grocery_og.find({}).skip(skip).limit(limit))
    
    for order in orders:
        order['_id'] = str(order['_id'])
    
    return jsonify({
        'orders': orders,
        'page': page,
        'limit': limit,
        'total': db.grocery_og.count_documents({})
    })


@app.route('/api/items/grocery')
def get_grocery_items():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    
    pipeline = [
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.name",
                "total_quantity": {"$sum": "$items.qty"},
                "total_spent": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}},
                "times_bought": {"$sum": 1},
                "latest_bought": {"$max": "$date"},
                "avg_price": {"$avg": "$items.price"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": "$_id",
                "total_quantity": 1,
                "total_spent": 1,
                "times_bought": 1,
                "latest_bought": 1,
                "avg_price": {"$round": ["$avg_price", 2]}
            }
        },
        {"$sort": {"total_quantity": -1}},
        {"$limit": 1000}
    ]
    
    items_list = list(db.grocery_og.aggregate(pipeline))
    
    return jsonify({
        'items': items_list,
        'total_unique_items': len(items_list)
    })

@app.route('/api/items/grocery/update', methods=['POST'])
def update_grocery_item():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    if not old_name or not new_name:
        return jsonify({'error': 'Missing old_name or new_name'}), 400
    
   
    result = db.grocery_og.update_many(
        {'items.name': old_name},
        {'$set': {'items.$[elem].name': new_name}},
        array_filters=[{'elem.name': old_name}]
    )
    
    return jsonify({
        'success': True,
        'updated_count': result.modified_count,
        'message': f'Updated {result.modified_count} items from "{old_name}" to "{new_name}"'
    })

@app.route('/api/items/grocery/merge', methods=['POST'])
def merge_grocery_items():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    data = request.get_json()
    items_to_merge = data.get('items_to_merge', [])
    target_name = data.get('target_name')
    
    if not items_to_merge or not target_name:
        return jsonify({'error': 'Missing items_to_merge or target_name'}), 400
    
    if len(items_to_merge) < 2:
        return jsonify({'error': 'Need at least 2 items to merge'}), 400
    
   
    orders = list(db.grocery_og.find({
        'items.name': {'$in': items_to_merge}
    }))
    
    updated_count = 0
    for order in orders:
        # Update all items in this order that match the items to merge
        for item in order['items']:
            if item['name'] in items_to_merge:
                item['name'] = target_name
                updated_count += 1
        
        # Update the order in the database
        db.grocery_og.update_one(
            {'_id': order['_id']},
            {'$set': {'items': order['items']}}
        )
    
    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'message': f'Merged {len(items_to_merge)} items into "{target_name}"'
    })

@app.route('/api/items/grocery/delete', methods=['POST'])
def delete_grocery_item():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    data = request.get_json()
    item_name = data.get('item_name')
    order_id = data.get('order_id') 
    if not item_name or not order_id:
        return jsonify({'error': 'Missing details'}), 400
    
    result = db.grocery_og.update_one(
        {'_id': ObjectId(order_id)},
        {'$pull': {'items': {'name': item_name}}}
    )
    #The $pull operator removes from an existing array 
    #all instances of a value or values that match a specified condition.
    
    return jsonify({
        'success': True,
        'updated_count': result.modified_count,
        'message': f'Deleted {result.modified_count} items named "{item_name}"'
    })

@app.route('/api/export/csv')
def export_csv():
    client, db = connect_to_mongodb()
    if client is None or db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    

    grocery_data = list(db.grocery_og.find({}).limit(5000))
    
    if grocery_data:
        grocery_df = pd.DataFrame(grocery_data)
        grocery_df.to_csv('grocery_orders.csv', index=False)
    
    return jsonify({
        'message': 'CSV files exported successfully',
        'grocery_orders': len(grocery_data),
        'note': 'Limited to 5000 most recent orders for performance'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
