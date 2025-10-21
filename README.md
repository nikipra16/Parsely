# Parsely 

STATUS: PoC

A personal grocery order tracking system that automatically processes gmail receipts to extract spending insights and 
can be used by users to analyze shopping patterns.

## Overview

Parsely is an end-to-end ETL pipeline that processes grocery order gmails from various retailers to provide actionable insights into personal spending habits. The system automatically extracts order data, transforms it into structured format, and loads it into a database for analysis.

## Features

- **Automated Email Processing**: Extracts order data from Gmail receipts
- **Multi-Store Support**: Handles different email formats from Instacart, DoorDash, and other retailers
- **Smart Data Parsing**: Uses Beautiful Soup and regex patterns to parse various HTML structures
- **Brand Recognition**: Leverages spaCy NLP for product name processing and brand extraction
- **Web Dashboard**: Interactive Flask-based dashboard for spending analytics
- **Performance Optimized**: MongoDB aggregation pipelines and lazy loading for efficient data processing
- **Data Export**: CSV export functionality for external analysis

## Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Data Processing**: Pandas, Regex, JSON
- **Database**: MongoDB 

## Project Structure

```
Parsely/
├── app.py                 # Main email processing application
├── web_app.py            # Flask web application
├── email_parser.py       # Email parsing and data extraction
├── mongo.py              # Database connection and operations
├── constants.py          # Shared constants and regex patterns
├── requirements.txt      # Python dependencies
├── data/                 # Processed data files (not uploaded on github)
├── static/               # CSS and JavaScript files
├── templates/            # HTML templates
└── priv_data/            # Private credentials and tokens
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Parsely
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Gmail API credentials**
   - Create a Google Cloud Console project
   - Enable the Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials.json and place in `priv_data/` folder
   - Run the application to authenticate and generate token.pickle
   - Both `credentials.json` and `token.pickle` should be in the `priv_data/` folder

4. **Set up MongoDB**
   - Create a MongoDB Atlas cluster
   - Update connection details in `.env` file

## Usage

### Email Processing
```bash
python app.py
```
This will:
- Authenticate with Gmail API
- Process emails from specified date range
- Extract and parse order data
- Store results in MongoDB

### Web Dashboard
```bash
python web_app.py
```
Access the dashboard at `http://localhost:5002`


## ETL Pipeline

### Extract
- **Gmail API**: Retrieves email receipts from inbox
- **Email Parsing**: Extracts HTML/text content from email bodies

### Transform
- **HTML Processing**: Beautiful Soup converts HTML to structured data
- **Text Processing**: Regex patterns extract items, quantities, and prices
- **NLP Processing**: spaCy tokenizes and cleans product names
- **Brand Recognition**: Extracts brand names from product descriptions
- **Data Cleaning**: Normalizes and categorizes order data

### Load
- **MongoDB Storage**: Stores processed data in structured collections
- **Upsert Operations**: Updates existing orders or creates new ones

[//]: # (## API Endpoints)

[//]: # ()
[//]: # (- `GET /` - Main dashboard)

[//]: # (- `GET /api/dashboard/stats` - Dashboard statistics)

[//]: # (- `GET /api/orders/grocery` - Paginated grocery orders)

[//]: # (- `GET /api/items/grocery` - Item analysis and statistics)

[//]: # (- `POST /api/items/grocery/update` - Update item names)

[//]: # (- `POST /api/items/grocery/merge` - Merge duplicate items)

[//]: # (- `POST /api/items/grocery/delete` - Delete specific items)

[//]: # (- `GET /api/export/csv` - Export data to CSV)

## Data Schema

### Order Document
```json
{
  "items": [
    {
      "brand": "BRAND",
      "name": "NAME",
      "qty": 2,
      "price": 3.50
    }
  ],
  "totals": {
    "total": 45.67,
    "subtotal": 42.50,
    "tax": 2.17
  },
  "category": "Grocery",
  "store_name": "STORE",
  "date": "2024-01-15 14:30:00",
  "gmail_id": "abc123"
}
```

## Performance Optimizations (Current)

- **MongoDB Aggregation**: Database-level calculations instead of Python processing
- **Lazy Loading**: Heavy resources loaded only when needed
- **Pagination**: Efficient data loading for large datasets

## Future Enhancements

- [ ] Recipe recommendation system using external recipe APIs
- [ ] Inventory-based grocery list generation
- [ ] OCR integration for receipt images
- [ ] Machine learning for spending predictions

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## License

This project is for personal use only.

## Contact

For questions or suggestions, please open an issue or contact the repository owner.