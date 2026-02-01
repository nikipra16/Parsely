# Parsely 

STATUS: PoC (working on some final cleaning)

A personal grocery order tracking system that automatically processes gmail receipts to extract spending insights and 
can be used by users to analyze shopping patterns.

## Overview

Parsely is an end-to-end ETL pipeline that processes grocery order gmails from various retailers to provide actionable insights into personal spending habits. The system automatically extracts order data, transforms it into structured format, and loads it into a database for analysis.

## Tech Stack

- **Extract**: Gmail API
- **Transform**: beautifulsoup4, regex, pandas, spacy
- **Database**: PostgreSQL

## Usage

### Email Processing
```bash
python app.py
```
This will:
- Authenticate with Gmail API
- Process emails from specified date range
- Extract and parse order data
- Store results in PostgreSQL

### Making dashboards!
I exported my grocery data into excel (after converting it to csv) and did some cleaning using power query and python (pandas and regex) and made dashboards.
<img width="635" height="646" alt="tableau_parseley_charts" src="https://github.com/user-attachments/assets/9ea226fc-c08c-468d-b78a-0b673e8ad2ff" />

## Performance Optimizations (Current)
- **Lazy Loading**: Heavy resources loaded only when needed

## Now

- [ ] Finalizing orchestration

## Future Enhancements

- [ ] OCR integration for receipt images ( to add non-gmail grocery items for more accuracy)
- [ ] Recipe recommendation system using external recipe APIs
- [ ] Inventory-based grocery list generation
- [ ] Machine learning for spending predictions

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## License

This project is for personal use only.

## Contact

For questions or suggestions, please open an issue or contact the repository owner.