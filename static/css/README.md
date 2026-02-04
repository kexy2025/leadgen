# Lead Management Platform

A modern lead management system with automatic deduplication, flexible schema, and smart header mapping.

## Features

- Upload CSV/Excel files or import from Google Sheets
- Automatic duplicate detection by Email or Phone
- Flexible schema - add columns anytime
- Smart header mapping with suggestions
- Real-time stats and filtering
- Export to CSV

## Deployment

This app is ready to deploy to Render, Railway, or other Python hosting platforms.

### Deploy to Render

1. Push this repo to GitHub
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Render will auto-detect settings
5. Deploy!

**Build Command:** pip install -r requirements.txt
**Start Command:** gunicorn app:app

## Local Development

pip install -r requirements.txt
python app.py

Open http://localhost:5000

## Tech Stack

- Backend: Flask (Python)
- Database: SQLite
- Frontend: Vanilla HTML/CSS/JavaScript

## License

MIT - Use freely!
