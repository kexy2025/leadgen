# Lead Management Platform - Production Ready
# Flask backend with Railway deployment fixes

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime
import hashlib
from pathlib import Path

app = Flask(__name__)

# PRODUCTION FIX #1: CORS Configuration
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# PRODUCTION FIX #2: Configuration
UPLOAD_FOLDER = 'uploads'
DATABASE = 'leads.db'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# PRODUCTION FIX #3: Ensure uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# PRODUCTION FIX #4: File size limit (50MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_db():
    """Initialize SQLite database with schema"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Leads table
        c.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                last_name TEXT,
                title TEXT,
                company_name TEXT,
                mobile_phone TEXT,
                company_phone TEXT,
                employee_count TEXT,
                person_linkedin_url TEXT,
                website TEXT,
                company_linkedin_url TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                industry TEXT,
                source_file TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lead_status TEXT DEFAULT 'Active',
                duplicate_flag INTEGER DEFAULT 0,
                processing_notes TEXT
            )
        ''')
        
        # Config table for schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_column TEXT UNIQUE NOT NULL,
                header_aliases TEXT,
                required INTEGER DEFAULT 0
            )
        ''')
        
        # Processing log
        c.execute('''
            CREATE TABLE IF NOT EXISTS processing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_file TEXT,
                total_rows INTEGER,
                new_leads INTEGER,
                duplicates INTEGER,
                success_rate REAL,
                user TEXT
            )
        ''')
        
        # Mapping history
        c.execute('''
            CREATE TABLE IF NOT EXISTS mapping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_header TEXT,
                action TEXT,
                target_column TEXT,
                user TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

def seed_config():
    """Seed initial configuration"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Check if config already exists
        c.execute('SELECT COUNT(*) FROM config')
        if c.fetchone()[0] > 0:
            conn.close()
            print("✅ Config already seeded")
            return
        
        # Default schema from user requirements
        default_config = [
            ('name', 'name,first name,full name,fname', 0),
            ('email', 'email,email address,e-mail,work email,email addr', 1),
            ('last_name', 'last name,last,lname,surname', 0),
            ('title', 'title,job title,position,role', 0),
            ('company_name', 'company,company name,organization,employer', 0),
            ('mobile_phone', 'mobile,mobile phone,cell,cell phone,personal phone', 0),
            ('company_phone', 'phone,company phone,work phone,office phone,telephone', 0),
            ('employee_count', 'employees,# employees,company size,headcount,# of employees', 0),
            ('person_linkedin_url', 'linkedin,person linkedin,linkedin url,linkedin profile,profile url', 0),
            ('website', 'website,url,company url,web,site', 0),
            ('company_linkedin_url', 'company linkedin,company linkedin url,organization linkedin', 0),
            ('city', 'city,town,location', 0),
            ('state', 'state,province,region', 0),
            ('country', 'country,nation', 0),
            ('industry', 'industry,sector,vertical,field', 0),
        ]
        
        c.executemany('INSERT INTO config (canonical_column, header_aliases, required) VALUES (?, ?, ?)', 
                      default_config)
        conn.commit()
        conn.close()
        print("✅ Config seeded successfully")
    except Exception as e:
        print(f"❌ Config seeding error: {e}")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize_header(header):
    """Normalize header for matching"""
    if not header:
        return ''
    return ''.join(c for c in str(header).lower() if c.isalnum())

def generate_lead_id(email, phone):
    """Generate unique lead ID from email or phone"""
    if email and email.strip():
        return email.lower().strip()
    elif phone and phone.strip():
        digits = ''.join(c for c in str(phone) if c.isdigit())
        return f"PHONE_{digits}"
    return ''

def get_schema():
    """Get current schema from config"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT canonical_column, header_aliases, required FROM config')
    rows = c.fetchall()
    conn.close()
    
    schema = {
        'columns': [],
        'alias_map': {},
        'required_columns': []
    }
    
    for row in rows:
        canonical, aliases_str, required = row
        schema['columns'].append(canonical)
        
        if required:
            schema['required_columns'].append(canonical)
        
        # Parse aliases
        aliases = [a.strip() for a in aliases_str.split(',') if a.strip()]
        aliases.append(canonical)  # Add canonical name as alias
        
        # Build alias map
        for alias in aliases:
            normalized = normalize_header(alias)
            schema['alias_map'][normalized] = canonical
    
    return schema

def map_headers(headers, schema):
    """Map upload headers to canonical columns"""
    header_map = {}
    unknown_headers = []
    
    for original_header in headers:
        normalized = normalize_header(original_header)
        
        if normalized in schema['alias_map']:
            header_map[original_header] = schema['alias_map'][normalized]
        else:
            unknown_headers.append(original_header)
    
    return header_map, unknown_headers

def check_duplicate(email, phone):
    """Check if lead already exists"""
    lead_id = generate_lead_id(email, phone)
    if not lead_id:
        return False
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM leads WHERE lead_id = ?', (lead_id,))
    exists = c.fetchone()[0] > 0
    conn.close()
    
    return exists

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DATABASE),
        'uploads_folder': os.path.exists(UPLOAD_FOLDER)
    })

@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Total leads
        c.execute("SELECT COUNT(*) FROM leads WHERE lead_status = 'Active'")
        total_leads = c.fetchone()[0]
        
        # Duplicates
        c.execute("SELECT COUNT(*) FROM leads WHERE lead_status = 'Duplicate'")
        duplicates = c.fetchone()[0]
        
        # Recent uploads
        c.execute("SELECT COUNT(*) FROM processing_log WHERE date(timestamp) = date('now')")
        today_uploads = c.fetchone()[0]
        
        # Success rate
        c.execute("SELECT AVG(success_rate) FROM processing_log WHERE timestamp >= datetime('now', '-7 days')")
        avg_success_rate = c.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'total_leads': total_leads,
            'duplicates': duplicates,
            'today_uploads': today_uploads,
            'success_rate': round(avg_success_rate, 1)
        })
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads')
def get_leads():
    """Get leads with pagination and filtering"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        status = request.args.get('status', 'Active')
        search = request.args.get('search', '')
        
        offset = (page - 1) * per_page
        
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Build query
        query = "SELECT * FROM leads WHERE lead_status = ?"
        params = [status]
        
        if search:
            query += " AND (email LIKE ? OR name LIKE ? OR company_name LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY date_added DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        c.execute(query, params)
        rows = c.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM leads WHERE lead_status = ?"
        count_params = [status]
        if search:
            count_query += " AND (email LIKE ? OR name LIKE ? OR company_name LIKE ?)"
            count_params.extend([search_param, search_param, search_param])
        
        c.execute(count_query, count_params)
        total = c.fetchone()[0]
        
        conn.close()
        
        leads = [dict(row) for row in rows]
        
        return jsonify({
            'leads': leads,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        print(f"❌ Get leads error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    """Handle file upload and processing"""
    # PRODUCTION FIX #5: Handle preflight requests
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        print("📁 Upload request received")
        
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        print(f"📄 File received: {file.filename}")
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Use CSV or Excel.'}), 400
        
        # Save file
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        print(f"💾 File saved: {filepath}")
        
        # Parse file
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='ignore')
        else:
            df = pd.read_excel(filepath)
        
        print(f"📊 Parsed {len(df)} rows")
        
        # Get schema
        schema = get_schema()
        
        # Map headers
        headers = df.columns.tolist()
        header_map, unknown_headers = map_headers(headers, schema)
        
        print(f"🗺️ Mapped {len(header_map)} headers, {len(unknown_headers)} unknown")
        
        # If unknown headers, return for user mapping
        if unknown_headers:
            # Get sample data
            samples = {}
            for header in unknown_headers:
                samples[header] = df[header].dropna().head(3).tolist()
            
            return jsonify({
                'status': 'needs_mapping',
                'unknown_headers': unknown_headers,
                'samples': samples,
                'schema_columns': schema['columns'],
                'temp_file': filename
            })
        
        # Process data
        result = process_data(df, header_map, schema, filename)
        print(f"✅ Processing complete: {result}")
        
        return jsonify(result)
    
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/apply_mapping', methods=['POST'])
def apply_mapping():
    """Apply user-provided header mappings"""
    data = request.json
    mappings = data.get('mappings', [])
    temp_file = data.get('temp_file')
    
    if not temp_file:
        return jsonify({'error': 'No temp file specified'}), 400
    
    try:
        filepath = os.path.join(UPLOAD_FOLDER, temp_file)
        
        # Parse file
        if temp_file.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Apply mappings to config
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        for mapping in mappings:
            action = mapping.get('action')
            original_header = mapping.get('originalHeader')
            
            if action == 'map_existing':
                target_column = mapping.get('targetColumn')
                # Add alias to existing column
                c.execute('SELECT header_aliases FROM config WHERE canonical_column = ?', (target_column,))
                row = c.fetchone()
                if row:
                    current_aliases = row[0]
                    new_aliases = f"{current_aliases},{original_header}"
                    c.execute('UPDATE config SET header_aliases = ? WHERE canonical_column = ?', 
                             (new_aliases, target_column))
            
            elif action == 'create_new':
                new_column = mapping.get('newColumnName')
                is_required = mapping.get('isRequired', False)
                # Create new column in config
                c.execute('INSERT OR IGNORE INTO config (canonical_column, header_aliases, required) VALUES (?, ?, ?)',
                         (new_column, original_header, 1 if is_required else 0))
                
                # Add column to leads table
                try:
                    c.execute(f'ALTER TABLE leads ADD COLUMN {new_column} TEXT')
                except:
                    pass  # Column may already exist
            
            # Log mapping
            c.execute('INSERT INTO mapping_history (original_header, action, target_column, user) VALUES (?, ?, ?, ?)',
                     (original_header, action, mapping.get('targetColumn') or mapping.get('newColumnName'), 'system'))
        
        conn.commit()
        conn.close()
        
        # Re-process with new mappings
        schema = get_schema()
        headers = df.columns.tolist()
        header_map, unknown_headers = map_headers(headers, schema)
        
        result = process_data(df, header_map, schema, temp_file)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_data(df, header_map, schema, source_file):
    """Process and insert data into database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    total_rows = len(df)
    new_leads = 0
    duplicates = 0
    
    for _, row in df.iterrows():
        # Map row data to canonical columns
        lead_data = {}
        for original_header, canonical_column in header_map.items():
            value = row.get(original_header, '')
            lead_data[canonical_column] = str(value) if pd.notna(value) else ''
        
        # Generate lead ID
        email = lead_data.get('email', '')
        phone = lead_data.get('mobile_phone') or lead_data.get('company_phone', '')
        lead_id = generate_lead_id(email, phone)
        
        if not lead_id:
            continue  # Skip if no identifier
        
        # Check duplicate
        if check_duplicate(email, phone):
            duplicates += 1
            continue
        
        # Insert lead
        try:
            c.execute('''
                INSERT INTO leads (
                    lead_id, name, email, last_name, title, company_name,
                    mobile_phone, company_phone, employee_count,
                    person_linkedin_url, website, company_linkedin_url,
                    city, state, country, industry, source_file, lead_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
            ''', (
                lead_id,
                lead_data.get('name', ''),
                lead_data.get('email', ''),
                lead_data.get('last_name', ''),
                lead_data.get('title', ''),
                lead_data.get('company_name', ''),
                lead_data.get('mobile_phone', ''),
                lead_data.get('company_phone', ''),
                lead_data.get('employee_count', ''),
                lead_data.get('person_linkedin_url', ''),
                lead_data.get('website', ''),
                lead_data.get('company_linkedin_url', ''),
                lead_data.get('city', ''),
                lead_data.get('state', ''),
                lead_data.get('country', ''),
                lead_data.get('industry', ''),
                source_file
            ))
            new_leads += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    
    # Log processing
    success_rate = (new_leads / total_rows * 100) if total_rows > 0 else 0
    c.execute('''
        INSERT INTO processing_log (source_file, total_rows, new_leads, duplicates, success_rate, user)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (source_file, total_rows, new_leads, duplicates, success_rate, 'system'))
    
    conn.commit()
    conn.close()
    
    return {
        'status': 'success',
        'total_rows': total_rows,
        'new_leads': new_leads,
        'duplicates': duplicates,
        'success_rate': round(success_rate, 1)
    }

@app.route('/api/export')
def export_leads():
    """Export leads to CSV"""
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT * FROM leads WHERE lead_status = 'Active'", conn)
    conn.close()
    
    export_path = os.path.join(UPLOAD_FOLDER, f'export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df.to_csv(export_path, index=False)
    
    return send_file(export_path, as_attachment=True)

@app.route('/api/config')
def get_config():
    """Get current configuration"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM config ORDER BY id')
    rows = c.fetchall()
    conn.close()
    
    config = [dict(row) for row in rows]
    return jsonify(config)

# ============================================================================
# INITIALIZATION & MAIN
# ============================================================================

# PRODUCTION FIX #6: Initialize database on import (for Railway)
print("🚀 Lead Management Platform - Production Mode")
print("=" * 50)
if init_db():
    seed_config()
    print("✅ Application ready!")
else:
    print("❌ Application failed to initialize")
print("=" * 50)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Server starting on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)
