# Constants for email parsing
import re

# Grocery store indicators
GROCERY_STORES = [
    'walmart', 'loblaws', 'costco', 'tnt', 'superstore', 'no frills', 
    'metro', 'sobeys', 'pc express', 'save-on-foods', 'freshco', 'instacart'
]

# Restaurant/food delivery indicators
DINING_STORES = [
    'mcdonalds', 'kfc', 'burger king', 'subway', 'pizza hut', 'dominos',
    'a&w', 'wendys', 'taco bell', 'popeyes', 'doordash', 'uber eats',
    'skip the dishes', 'grubhub', 'restaurant', 'cafe', 'bakery'
]

# Grocery keywords for categorization
GROCERY_KEYWORDS = [
    'produce', 'dairy', 'meat', 'pantry', 'frozen', 'bakery',
    'household', 'personal care', 'beauty', 'medicine', 'snacks',
    'beverages', 'drinks', 'pasta', 'rice', 'cereal', 'milk',
    'cheese', 'yogurt', 'bread', 'eggs', 'vegetables', 'fruits',
    'baking', 'cooking', 'kitchen', 'paper', 'cups', 'parchment',
    'foil', 'wrap', 'bags', 'containers', 'utensils', 'tools'
]

# Dining keywords for categorization
DINING_KEYWORDS = [
    'combo', 'meal', 'burger', 'sandwich', 'pizza', 'pasta',
    'soup', 'salad', 'appetizer', 'entree', 'dessert', 'drink',
    'fries', 'nuggets', 'wings', 'wrap', 'bowl', 'platter',
    'thali', 'biryani', 'curry', 'naan', 'roti', 'dosa',
    'chicken strips', 'buddy burger', 'mcnuggets', 'mcmuffin',
    'whopper', 'big mac', 'quarter pounder', 'filet o fish',
    'mcflurry', 'happy meal', 'extra value meal', 'value meal',
    'ramen', 'gyoza', 'dumpling', 'shawarma', 'banh mi',
    'tandoori', 'mangalorean', 'paneer', 'biryani', 'pakora',
    'vada pav', 'dosa', 'roti', 'naan', 'thali', 'curry',
    'laksa', 'udon', 'noodles', 'pho', 'pad thai', 'sushi',
    'roll', 'maki', 'sashimi', 'teriyaki', 'tempura'
]

# Email cutoff keywords
CUTOFF_KEYWORDS = [
    "privacy policy",
    "download the app",
    "help center",
    "shop gift cards",
    "deliver with doordash",
    "©2025 doordash"
]

# Compiled regex patterns for better performance
TOTAL_PATTERNS = [
    re.compile(r'Total charged \(CAD\)</td>\s*<td[^>]*>\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Total CAD[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Total[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Order Totals[:\s]*([0-9]+\.[0-9]{2})')
]

SUBTOTAL_PATTERNS = [
    re.compile(r'Items Subtotal[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Subtotal[:\s]*\$([0-9]+\.[0-9]{2})')
]

TAX_PATTERNS = [
    re.compile(r'Item GST[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Item PST[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Tax[:\s]*\$([0-9]+\.[0-9]{2})')
]

SERVICE_FEE_PATTERNS = [
    re.compile(r'Service Fee[:\s]*\$([0-9]+\.[0-9]{2})'),
    re.compile(r'Service fee[:\s]*\$([0-9]+\.[0-9]{2})')
]

# General totals patterns
GENERAL_TOTALS_PATTERNS = {
    "subtotal": re.compile(r"subtotal\s*\$([0-9]+\.[0-9]{2})"),
    "taxes": re.compile(r"taxes\s*\$([0-9]+\.[0-9]{2})"),
    "total": re.compile(r"total charged\s*\$([0-9]+\.[0-9]{2})")
}

# Item extraction pattern
ITEM_EXTRACTION_PATTERN = re.compile(r"(\d+)x\s+([\s\S]+?)\n.*?\$([0-9]+\.[0-9]{2})")

# Quantity and price pattern
QTY_PRICE_PATTERN = re.compile(r'(\d+)\s*x\s*\$([0-9]+\.[0-9]{2})')

# Price only pattern
PRICE_PATTERN = re.compile(r'\$([0-9]+\.[0-9]{2})')

# Quantity pattern for product names
QTY_PRODUCT_PATTERN = re.compile(r'\(\d+\s*x\s*[^)]+\)')

# Price pattern in product names
PRICE_PRODUCT_PATTERN = re.compile(r'\d+\s*x\s*\$[0-9]+\.[0-9]{2}')

# Apostrophe normalization pattern
APOSTROPHE_PATTERN = re.compile(r"(\w+)\s+'\s*([sS])")
