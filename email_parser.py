import spacy
import re
import json
from bs4 import BeautifulSoup
from constants import (
    GROCERY_STORES, DINING_STORES, GROCERY_KEYWORDS, DINING_KEYWORDS,
    CUTOFF_KEYWORDS, TOTAL_PATTERNS, SUBTOTAL_PATTERNS, TAX_PATTERNS,
    SERVICE_FEE_PATTERNS, GENERAL_TOTALS_PATTERNS, ITEM_EXTRACTION_PATTERN,
    QTY_PRICE_PATTERN, PRICE_PATTERN, QTY_PRODUCT_PATTERN, PRICE_PRODUCT_PATTERN,
    APOSTROPHE_PATTERN
)

# global vars for Lazy loading 
_nlp = None
_grocery_brands = None
_processed_brands = None

def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

def get_grocery_brands():
    global _grocery_brands
    if _grocery_brands is None:
        _grocery_brands = load_grocery_brands()
    return _grocery_brands

def get_processed_brands():
    global _processed_brands
    if _processed_brands is None:
        brands_data = get_grocery_brands()
        all_brands = []
        for category in brands_data["brands"]:
            all_brands.extend(brands_data["brands"][category])
        # Remove duplicates and sort by length (longest first)
        _processed_brands = sorted(list(set(all_brands)), key=len, reverse=True)
    return _processed_brands

def html_to_text(html_email):
    soup = BeautifulSoup(html_email, "html.parser")
    text = soup.get_text(separator="\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text.lower()

def clean_email_text(raw_email):
    clean_email = raw_email
    for keyword in CUTOFF_KEYWORDS:
        if keyword in clean_email:
            clean_email = clean_email.split(keyword)[0]
            break
    return clean_email

def extract_instacart_items(html_email, subject=""):
    items = []
    totals = {}
    soup = BeautifulSoup(html_email, "html.parser")

    name_divs = soup.find_all('div', class_='item-name')
    
    for name_div in name_divs:
        try:
            name_text = name_div.get_text(strip=True)
            
            # Mynotes:
            # The text might be like "Red Bull Watermelon Energy Drink(4 x 250 ml)1 x $8.99"
            # We need to separate the product name from quantity/price info

            product_name = name_text
            # Remove quantity patterns like "(4 x 250 ml)"
            product_name = QTY_PRODUCT_PATTERN.sub('', product_name)
            # Remove price patterns like "1 x $8.99"
            product_name = PRICE_PRODUCT_PATTERN.sub('', product_name)

            product_name = product_name.strip()
            
            if not product_name:
                continue

            qty = 1
            price = 0.0
            
            # Look for quantity pattern like "1 x $8.99"
            qty_match = QTY_PRICE_PATTERN.search(name_text)
            if qty_match:
                qty = int(qty_match.group(1))
                price = float(qty_match.group(2))
            else:
                price_match = PRICE_PATTERN.search(name_text)
                if price_match:
                    price = float(price_match.group(1))

            doc = get_nlp()(product_name)
            # Preserve apostrophes "President's Choice"
            clean_name = " ".join([t.text for t in doc if not t.is_punct or t.text == "'"])
            
            clean_name = APOSTROPHE_PATTERN.sub(r"\1'\2", clean_name)
            brand, item_name = extract_brand_and_item(clean_name)
            
            items.append({
                "brand": brand,
                "name": item_name,
                "qty": qty,
                "price": price
            })
            
        except Exception as e:
            print(f"Error parsing Instacart item: {e}")
            continue

    try:
        # Use compiled patterns for better performance
        for pattern in TOTAL_PATTERNS:
            total_match = pattern.search(html_email)
            if total_match:
                totals['total'] = float(total_match.group(1))
                break
        
        for pattern in SUBTOTAL_PATTERNS:
            subtotal_match = pattern.search(html_email)
            if subtotal_match:
                totals['subtotal'] = float(subtotal_match.group(1))
                break
        
        tax_total = 0.0
        for pattern in TAX_PATTERNS:
            tax_match = pattern.search(html_email)
            if tax_match:
                tax_total += float(tax_match.group(1))
        
        if tax_total > 0:
            totals['tax'] = tax_total
        
        for pattern in SERVICE_FEE_PATTERNS:
            service_match = pattern.search(html_email)
            if service_match:
                totals['service_fee'] = float(service_match.group(1))
                break
                
    except Exception as e:
        print(f"Error parsing Instacart totals: {e}")
    
    return items, totals

def extract_items(cleaned_email, from_email="", subject="", raw_html=""):
    items = []

    if 'instacart' in from_email.lower():
        if 'receipt' not in subject.lower():
            return [], {}
        if raw_html:
            return extract_instacart_items(raw_html, subject)
        return [], {}

    
    for match in ITEM_EXTRACTION_PATTERN.finditer(cleaned_email):
        qty, name, price = match.groups()
        
        
        is_doordash_dining = False
        restaurant_name = ""
        
        if 'doordash' in from_email.lower():
            # Check if this DoorDash order is grocery or dining
            is_grocery_order = any(store in subject.lower() for store in GROCERY_STORES)
            
            if not is_grocery_order:
                is_doordash_dining = True
                restaurant_name = extract_restaurant_name_from_subject(subject)
        
        if is_doordash_dining:
            # For dining orders, use restaurant as brand and keep original name
            brand = restaurant_name
            item_name = name.strip().title()
        else:
            # For grocery orders, use existing logic
            doc = get_nlp()(name)
            product_name = " ".join([t.text for t in doc if not t.is_punct])
            brand, item_name = extract_brand_and_item(product_name)
        
        items.append({
            "brand": brand,
            "name": item_name,
            "qty": int(qty),
            "price": float(price)
        })
    
    totals = extract_totals(cleaned_email)
    
    return items, totals

def load_grocery_brands():
    try:
        with open('grocery_brands.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"brands": {}}

def extract_restaurant_name_from_subject(subject):
    if not subject:
        return ""
    
    subject_lower = subject.lower()
    
    # Pattern 1: "from [Restaurant Name]"
    if " from " in subject_lower:
        parts = subject.split(" from ")
        if len(parts) > 1:
            restaurant = parts[1].strip()
            restaurant = restaurant.replace(" is ready", "").replace(" confirmed", "").replace(" order", "")
            return restaurant.strip()
    
    # Pattern 2: "order from [Restaurant Name]"
    if "order from " in subject_lower:
        parts = subject.split("order from ")
        if len(parts) > 1:
            restaurant = parts[1].strip()
            restaurant = restaurant.replace(" is ready", "").replace(" confirmed", "").replace(" order", "")
            return restaurant.strip()
    
    return ""

def extract_grocery_store_name(from_email, subject):
    from_email_lower = from_email.lower()
    subject_lower = subject.lower()

    if 'doordash' in from_email_lower:
        for store in GROCERY_STORES:
            if store in subject_lower:
                if store in subject:
                    return store.title()
                return store.title()
        return "DoorDash Grocery"

    for store in GROCERY_STORES:
        if store in from_email_lower:
            return store.title()

    for store in GROCERY_STORES:
        if store in subject_lower:
            return store.title()
    
    return "Unknown Grocery Store"

def extract_brand_and_item(product_name, from_email="", subject="", is_dining=False, restaurant_name=""):
    product_name = product_name.lower()
    
    # For DoorDash dining orders, use restaurant name as brand
    if is_dining and restaurant_name:
        # Keep original product name with punctuation for dining items
        return restaurant_name, product_name

    sorted_brands = get_processed_brands()
    
    for brand in sorted_brands:
        # Normalize both strings for better matching
        brand_normalized = brand.lower().replace("'", "'").replace("'", "'").replace("`", "'")
        product_normalized = product_name.replace("'", "'").replace("'", "'").replace("`", "'")
        
        if product_normalized.startswith(brand_normalized):
            brand_length = len(brand)
            item_name = product_name[brand_length:].strip()
            return brand, item_name
    
    words = product_name.split()
    if len(words) >= 2:
        brand = words[0].title()
        item_name = " ".join(words[1:]).title()
    else:
        brand = "Unknown"
        item_name = product_name.title()
    
    return brand, item_name


def extract_totals(cleaned_email):
    totals = {}
    
    for key, pattern in GENERAL_TOTALS_PATTERNS.items():
        match = pattern.search(cleaned_email)
        if match:
            totals[key] = float(match.group(1))
    return totals

def categorize_order(items, from_email="", subject=""):
    from_email_lower = from_email.lower()
    subject_lower = subject.lower()
    if 'doordash' in from_email_lower:
        if any(store in subject_lower for store in GROCERY_STORES):
            return "Grocery"
        else:
            return "Dining"

    elif any(store in from_email_lower for store in GROCERY_STORES):
        return "Grocery"

    elif any(store in from_email_lower for store in DINING_STORES):
        return "Dining"

    elif any(store in subject_lower for store in GROCERY_STORES):
        return "Grocery"
    
    elif any(store in subject_lower for store in DINING_STORES):
        return "Dining"

    grocery_indicators = 0
    dining_indicators = 0
    
    for item in items:
        item_name = item.get('name', '').lower()
        brand = item.get('brand', '').lower()

        if any(keyword in item_name for keyword in GROCERY_KEYWORDS):
            grocery_indicators += 1
        if any(keyword in item_name for keyword in DINING_KEYWORDS):
            dining_indicators += 1

        if any(keyword in brand for keyword in GROCERY_KEYWORDS):
            grocery_indicators += 1
        if any(keyword in brand for keyword in DINING_KEYWORDS):
            dining_indicators += 1

    if grocery_indicators > dining_indicators:
        return "Grocery"
    elif dining_indicators > grocery_indicators:
        return "Dining"
    else:
        if not items and (not from_email and not subject):
            return "Unknown"
        else:
            return "Grocery"

def parse_email(raw_email, from_email="", subject="", raw_html=""):
    text_email = html_to_text(raw_email)
    cleaned = clean_email_text(text_email)
    items, totals = extract_items(cleaned, from_email, subject, raw_html)

    if not totals:
        totals = extract_totals(cleaned)
    
    category = categorize_order(items, from_email, subject)

    # Extract store name based on category
    store_name = ""
    if category == "Grocery":
        store_name = extract_grocery_store_name(from_email, subject)
    elif category == "Dining":
        store_name = extract_restaurant_name_from_subject(subject)
    
    return {
        "items": items,
        "totals": totals,
        "category": category,
        "store_name": store_name
    }
