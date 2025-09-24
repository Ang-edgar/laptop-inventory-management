from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session, Response, abort
import sqlite3
import datetime
import csv
import io
import os  # This was missing!
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Authentication helpers ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('role') != 'admin':
            flash('Admin access required. Please log in as admin.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Database helper ---
def get_db():
    # Get database path from environment variable or use default
    db_path = os.environ.get('DB_PATH', 'laptops.db')
    # Only create directory if path contains a directory
    if os.path.dirname(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def generate_serial_number(laptop_name):
    """Generate a serial number based on laptop brand, date, and increment"""
    from datetime import datetime
    
    # Extract brand from laptop name
    laptop_name_lower = laptop_name.lower()
    
    # Brand mapping
    if 'asus' in laptop_name_lower or 'asuspro' in laptop_name_lower:
        prefix = 'AS'
    elif 'dell' in laptop_name_lower:
        prefix = 'DE'
    elif 'lenovo' in laptop_name_lower:
        prefix = 'LE'
    elif 'thinkpad' in laptop_name_lower:
        prefix = 'TH'
    elif 'hp' in laptop_name_lower or 'hewlett' in laptop_name_lower:
        prefix = 'HP'
    elif 'acer' in laptop_name_lower:
        prefix = 'AC'
    elif 'msi' in laptop_name_lower:
        prefix = 'MS'
    elif 'macbook' in laptop_name_lower or 'apple' in laptop_name_lower:
        prefix = 'AP'
    elif 'microsoft' in laptop_name_lower or 'surface' in laptop_name_lower:
        prefix = 'SF'
    elif 'samsung' in laptop_name_lower:
        prefix = 'SM'
    else:
        prefix = 'GN'  # Generic
    
    # Get current date in MMYY format
    now = datetime.now()
    date_part = now.strftime("%m%y")  # 0925 for September 2025
    
    # Create the date-based prefix
    date_prefix = f"{prefix}{date_part}"  # DE0925
    
    # Get current count for this brand and month/year combination
    with get_db() as conn:
        try:
            count = conn.execute("SELECT COUNT(*) FROM laptops WHERE serial_number LIKE ?", (f"{date_prefix}%",)).fetchone()[0]
        except:
            count = 0
        
        next_number = count + 1
        
        # Format: PREFIX + MMYY + 2-digit number (01-99)
        serial = f"{date_prefix}{next_number:02d}"
        
        # Ensure uniqueness
        try:
            while conn.execute("SELECT COUNT(*) FROM laptops WHERE serial_number = ?", (serial,)).fetchone()[0] > 0:
                next_number += 1
                if next_number > 99:
                    # If we exceed 99 laptops in one month, add extra digits
                    serial = f"{date_prefix}{next_number:03d}"
                else:
                    serial = f"{date_prefix}{next_number:02d}"
        except:
            pass
    
    return serial

# --- Create table if not exists ---
with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS laptops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        laptop_name TEXT,
        cpu TEXT,
        ram TEXT,
        storage TEXT,
        os TEXT,
        notes TEXT,
        price_bought REAL,
        price_to_sell REAL,
        fees REAL,
        image TEXT,
        image_data BLOB,
        image_mimetype TEXT,
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_edited TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        date_sold TEXT,
        sold INTEGER DEFAULT 0,
        serial_number TEXT UNIQUE
    )
    """)
    
    # Add new columns to existing databases (safe operations)
    columns_to_add = [
        ("image_data", "BLOB"),
        ("image_mimetype", "TEXT"),
        ("serial_number", "TEXT UNIQUE"),
        ("warranty_start_date", "TEXT"),
        ("warranty_duration_days", "INTEGER DEFAULT 0"),
        ("warranty_notes", "TEXT")
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            conn.execute(f"ALTER TABLE laptops ADD COLUMN {column_name} {column_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Create other tables
    conn.execute("""
    CREATE TABLE IF NOT EXISTS spareparts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_type TEXT,
        storage_type TEXT,
        ram_type TEXT,
        ram_speed TEXT,
        capacity TEXT,
        notes TEXT,
        quantity INTEGER DEFAULT 1,
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_edited TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS laptop_spareparts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        laptop_id INTEGER,
        sparepart_id INTEGER,
        installed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (laptop_id) REFERENCES laptops(id),
        FOREIGN KEY (sparepart_id) REFERENCES spareparts(id)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS laptop_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        laptop_id INTEGER,
        image_data BLOB,
        image_mimetype TEXT,
        image_name TEXT,
        is_primary INTEGER DEFAULT 0,
        uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (laptop_id) REFERENCES laptops(id)
    )
    """)
    
    # Create users table for admin/guest authentication
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'guest',
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create orders table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        guest_email TEXT,
        guest_phone TEXT,
        status TEXT DEFAULT 'unconfirmed',
        total_amount REAL DEFAULT 0,
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        confirmed_date TIMESTAMP,
        completed_date TIMESTAMP,
        notes TEXT
    )
    """)
    
    # Create order_items table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        laptop_id INTEGER,
        quantity INTEGER DEFAULT 1,
        price REAL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (laptop_id) REFERENCES laptops(id)
    )
    """)
    
    # Insert default admin user if not exists
    admin_exists = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    if admin_exists == 0:
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                    ('admin', 'admin123', 'admin'))
        print("Default admin user created: admin / admin123")
    
    conn.commit()

# Migrate existing laptops (only once)
def migrate_existing_laptops():
    """Add serial numbers to existing laptops"""
    try:
        with get_db() as conn:
            # Check if we need to migrate
            needs_migration = conn.execute("SELECT COUNT(*) FROM laptops WHERE serial_number IS NULL OR serial_number = ''").fetchone()[0]
            
            if needs_migration > 0:
                print(f"Migrating {needs_migration} laptops to use serial numbers...")
                
                laptops = conn.execute("SELECT id, laptop_name FROM laptops WHERE serial_number IS NULL OR serial_number = '' ORDER BY id").fetchall()
                for laptop in laptops:
                    serial = generate_serial_number(laptop['laptop_name'])
                    conn.execute("UPDATE laptops SET serial_number = ? WHERE id = ?", (serial, laptop['id']))
                    print(f"Laptop ID {laptop['id']} -> Serial {serial}")
                
                conn.commit()
                print("Migration completed!")
    except Exception as e:
        print(f"Migration error: {e}")

# Run migration
migrate_existing_laptops()

# --- Authentication routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                               (username, password)).fetchone()
            
            if user:
                session['logged_in'] = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                flash(f'Welcome, Admin!', 'success')
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin_panel'))
                else:
                    # No more guest login - redirect to main shop
                    return redirect(url_for('guest_shop'))
            else:
                flash('Invalid credentials. Please try again.', 'error')
    
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))  # Redirect to login page

# --- Home page: Redirect to login ---
@app.route("/")
def index():
    return redirect(url_for('login'))

# --- Admin panel (login required) ---
@app.route("/admin")
@admin_required
def admin_panel():
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    search = request.args.get('search', '')

    valid_columns = ['id', 'laptop_name', 'cpu', 'ram', 'storage', 'os', 'price_bought',
                     'price_to_sell', 'fees', 'last_edited', 'created_date']

    if sort_by not in valid_columns:
        sort_by = 'id'
    if order not in ['asc', 'desc']:
        order = 'asc'

    conn = get_db()
    query = f"SELECT * FROM laptops WHERE sold = 0"
    params = []
    if search:
        query += " AND (laptop_name LIKE ? OR cpu LIKE ? OR ram LIKE ? OR storage LIKE ? OR os LIKE ?)"
        params = [f"%{search}%"] * 5
    query += f" ORDER BY {sort_by} {order}"
    laptops = conn.execute(query, params).fetchall()

    # Stats
    total_laptops = conn.execute("SELECT COUNT(*) FROM laptops").fetchone()[0]
    sold_count = conn.execute("SELECT COUNT(*) FROM laptops WHERE sold=1").fetchone()[0]
    available_count = conn.execute("SELECT COUNT(*) FROM laptops WHERE sold=0").fetchone()[0]
    total_profit = conn.execute("SELECT SUM(price_to_sell - (price_bought + fees)) FROM laptops WHERE sold=1").fetchone()[0] or 0

    # --- New code to count spare parts and check for images ---
    laptop_spare_counts = {}
    laptop_has_images = {}
    for laptop in laptops:
        ram_count = conn.execute("""
            SELECT COUNT(*) FROM laptop_spareparts lsp
            JOIN spareparts sp ON lsp.sparepart_id = sp.id
            WHERE lsp.laptop_id=? AND sp.part_type='RAM'
        """, (laptop['id'],)).fetchone()[0]
        storage_count = conn.execute("""
            SELECT COUNT(*) FROM laptop_spareparts lsp
            JOIN spareparts sp ON lsp.sparepart_id = sp.id
            WHERE lsp.laptop_id=? AND sp.part_type='Storage'
        """, (laptop['id'],)).fetchone()[0]
        laptop_spare_counts[laptop['id']] = {'ram': ram_count, 'storage': storage_count}
        
        # Check if laptop has images in the new table
        has_image = conn.execute("SELECT COUNT(*) FROM laptop_images WHERE laptop_id=?", (laptop['id'],)).fetchone()[0] > 0
        laptop_has_images[laptop['id']] = has_image or laptop['image_data'] or laptop['image']

    # Pass laptop_spare_counts and image info to your template
    return render_template("index.html", laptops=laptops, laptop_spare_counts=laptop_spare_counts, 
                       laptop_has_images=laptop_has_images, sold_count=sold_count,
                       available_count=available_count, total_profit=total_profit,
                       sort_by=sort_by, order=order)
# --- Add new laptop page ---
@app.route("/add", methods=["GET", "POST"])
@admin_required
def add():
    if request.method == "POST":
        conn = get_db()
        
        # Generate serial number based on laptop name
        laptop_name = request.form["laptop_name"]
        serial_number = generate_serial_number(laptop_name)
        
        # Insert laptop with serial number
        cursor = conn.execute("""
            INSERT INTO laptops (laptop_name, cpu, ram, storage, os, notes, price_bought, price_to_sell, fees, serial_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            laptop_name,
            request.form["cpu"],
            request.form["ram"],
            request.form["storage"],
            request.form["os"],
            request.form["notes"],
            request.form["price_bought"],
            request.form["price_to_sell"],
            request.form["fees"],
            serial_number
        ))
        
        laptop_id = cursor.lastrowid
        
        # Handle multiple image uploads (same as before)
        if "images" in request.files:
            files = request.files.getlist("images")
            for i, file in enumerate(files):
                if file and allowed_file(file.filename):
                    image_data = file.read()
                    image_mimetype = file.mimetype
                    image_name = secure_filename(file.filename)
                    is_primary = 1 if i == 0 else 0
                    
                    conn.execute("""
                        INSERT INTO laptop_images (laptop_id, image_data, image_mimetype, image_name, is_primary)
                        VALUES (?, ?, ?, ?, ?)
                    """, (laptop_id, image_data, image_mimetype, image_name, is_primary))
        
        conn.commit()
        return redirect(url_for("admin_panel"))
    return render_template("add.html")

# --- Completed sales page ---
@app.route("/completed")
@admin_required
def completed_sales():
    sort_by = request.args.get('sort', 'laptop_name')
    order = request.args.get('order', 'asc')
    search = request.args.get('search', '')

    valid_columns = ['laptop_name', 'cpu', 'ram', 'storage', 'os', 'price_bought',
                     'price_to_sell', 'fees', 'last_edited', 'created_date']

    if sort_by not in valid_columns:
        sort_by = 'laptop_name'
    if order not in ['asc', 'desc']:
        order = 'asc'

    conn = get_db()
    query = "SELECT * FROM laptops WHERE sold = 1"
    params = []
    if search:
        query += " AND (laptop_name LIKE ? OR cpu LIKE ? OR ram LIKE ? OR storage LIKE ? OR os LIKE ?)"
        params = [f"%{search}%"] * 5
    query += f" ORDER BY {sort_by} {order}"
    laptops = conn.execute(query, params).fetchall()

    # Calculate total profit
    total_profit = sum(laptop['price_to_sell'] - (laptop['price_bought'] + laptop['fees']) for laptop in laptops)
    # Calculate total sale money
    total_sales = sum(laptop['price_to_sell'] for laptop in laptops)

    return render_template("completed.html", laptops=laptops, total_profit=total_profit,
                           total_sales=total_sales, sort_by=sort_by, order=order, search=search)

# --- Edit laptop ---
@app.route("/edit/<int:laptop_id>", methods=["GET", "POST"])
@admin_required
def edit(laptop_id):
    conn = get_db()
    laptop = conn.execute("SELECT * FROM laptops WHERE id=?", (laptop_id,)).fetchone()
    if request.method == "POST":
        # Check if this is a complete form submission (has laptop details)
        if "laptop_name" in request.form:
            try:
                # Update laptop details with proper error handling
                price_bought = safe_float(request.form.get("price_bought"), 0)
                price_to_sell = safe_float(request.form.get("price_to_sell"), 0)
                fees = safe_float(request.form.get("fees"), 0)
                
                conn.execute("""
                    UPDATE laptops SET laptop_name=?, cpu=?, ram=?, storage=?, os=?, notes=?, 
                                      price_bought=?, price_to_sell=?, fees=?, sold=?, last_edited=?
                    WHERE id=?
                """, (
                    request.form.get("laptop_name", ""),
                    request.form.get("cpu", ""),
                    request.form.get("ram", ""),
                    request.form.get("storage", ""),
                    request.form.get("os", ""),
                    request.form.get("notes", ""),
                    price_bought,
                    price_to_sell,
                    fees,
                    1 if "sold" in request.form else 0,
                    datetime.datetime.now(),
                    laptop_id
                ))
                conn.commit()
                flash("Laptop updated successfully!", "success")
                return redirect(url_for("edit", laptop_id=laptop_id))
            except Exception as e:
                print(f"Error updating laptop: {e}")
                flash("Error updating laptop. Please try again.", "error")
    
    # Get images for display
    images = conn.execute("SELECT * FROM laptop_images WHERE laptop_id=? ORDER BY is_primary DESC, uploaded_date", (laptop_id,)).fetchall()
    return render_template("edit.html", laptop=laptop, images=images)

# --- Delete laptop ---
@app.route("/delete/<int:laptop_id>")
@admin_required
def delete(laptop_id):
    try:
        with get_db() as conn:
            # Delete associated images first
            conn.execute("DELETE FROM laptop_images WHERE laptop_id=?", (laptop_id,))
            # Delete spare parts relationships
            conn.execute("DELETE FROM laptop_spareparts WHERE laptop_id=?", (laptop_id,))
            # Delete the laptop
            conn.execute("DELETE FROM laptops WHERE id=?", (laptop_id,))
            conn.commit()
    except Exception as e:
        print(f"Error deleting laptop {laptop_id}: {e}")
        flash("Error deleting laptop", "error")
    
    return redirect(url_for("admin_panel"))

# --- Mark as sold ---
@app.route("/mark_sold/<int:laptop_id>")
@admin_required
def mark_sold(laptop_id):
    conn = get_db()
    now = datetime.datetime.now()
    conn.execute("""
        UPDATE laptops SET sold=1, last_edited=?, date_sold=?
        WHERE id=?
    """, (now, now, laptop_id))
    conn.commit()
    return redirect(url_for("admin_panel"))

# --- Mark as available ---
@app.route("/mark_available/<int:laptop_id>")
@admin_required
def mark_available(laptop_id):
    conn = get_db()
    conn.execute("""
        UPDATE laptops SET sold=0, last_edited=?
        WHERE id=?
    """, (datetime.datetime.now(), laptop_id))
    conn.commit()
    return redirect(url_for("completed_sales"))

# --- Export data ---
@app.route("/export", methods=["POST"])
@admin_required
def export():
    conn = get_db()
    laptops = conn.execute("SELECT * FROM laptops").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(laptops[0].keys())  # header
    for laptop in laptops:
        writer.writerow([laptop[key] for key in laptop.keys()])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="laptops.csv")

# --- Settings page ---
@app.route("/settings")
@admin_required
def settings():
    return render_template("settings.html")

# --- Reset data ---
@app.route("/reset_data", methods=["POST"])
@admin_required
def reset_data():
    confirm = request.form.get("reset_confirm", "")
    if confirm.strip().lower() == "reset":
        conn = get_db()
        conn.execute("DELETE FROM laptops")
        conn.commit()
        flash("All data has been reset.", "success")
    else:
        flash("Reset confirmation failed. Type 'reset' to confirm.", "danger")
    return redirect(url_for("settings"))

# --- Spare parts page ---
@app.route("/spareparts")
@admin_required
def spareparts():
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    part_type = request.args.get('part_type', '')
    storage_type = request.args.get('storage_type', '')
    ram_type = request.args.get('ram_type', '')
    ram_speed = request.args.get('ram_speed', '')

    valid_columns = ['id', 'part_type', 'storage_type', 'ram_type', 'ram_speed', 'capacity', 'quantity', 'last_edited', 'created_date']
    if sort_by not in valid_columns:
        sort_by = 'id'
    if order not in ['asc', 'desc']:
        order = 'asc'

    conn = get_db()
    query = "SELECT * FROM spareparts WHERE 1=1"
    params = []
    if part_type:
        query += " AND part_type=?"
        params.append(part_type)
    if storage_type:
        query += " AND storage_type=?"
        params.append(storage_type)
    if ram_type:
        query += " AND ram_type=?"
        params.append(ram_type)
    if ram_speed:
        query += " AND ram_speed=?"
        params.append(ram_speed)
    query += f" ORDER BY {sort_by} {order}"
    parts = conn.execute(query, params).fetchall()

    return render_template("spareparts.html", parts=parts, sort_by=sort_by, order=order)

# --- Add new spare part page ---
@app.route("/add_sparepart", methods=["GET", "POST"])
@admin_required
def add_sparepart():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            INSERT INTO spareparts (part_type, storage_type, ram_type, ram_speed, capacity, notes, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["part_type"],
            request.form.get("storage_type", ""),
            request.form.get("ram_type", ""),
            request.form.get("ram_speed", ""),
    
            request.form["capacity"],
            request.form["notes"],
            request.form["quantity"],
        ))
        conn.commit()
        return redirect(url_for("spareparts"))
    return render_template("add_spareparts.html")

# --- Edit spare part ---
@app.route("/edit_sparepart/<int:part_id>", methods=["GET", "POST"])
@admin_required
def edit_sparepart(part_id):
    conn = get_db()
    part = conn.execute("SELECT * FROM spareparts WHERE id=?", (part_id,)).fetchone()
    if request.method == "POST":
        conn.execute("""
            UPDATE spareparts SET
                part_type=?,
                storage_type=?,
                ram_type=?,
                ram_speed=?,
                capacity=?,
                notes=?,
                quantity=?,
                last_edited=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            request.form["part_type"],
            request.form.get("storage_type", ""),
            request.form.get("ram_type", ""),
            request.form.get("ram_speed", ""),
            request.form["capacity"],
            request.form["notes"],
            request.form["quantity"],
            part_id
        ))
        conn.commit()
        return redirect(url_for("spareparts"))
    return render_template("edit_sparepart.html", part=part)

# --- Delete spare part ---
@app.route("/delete_sparepart/<int:part_id>")
@admin_required
def delete_sparepart(part_id):
    conn = get_db()
    conn.execute("DELETE FROM spareparts WHERE id=?", (part_id,))
    conn.commit()
    return redirect(url_for("spareparts"))

# --- Laptop detail page ---
@app.route("/laptop/<int:laptop_id>")
@admin_required
def laptop_detail(laptop_id):
    conn = get_db()
    laptop = conn.execute("SELECT * FROM laptops WHERE id=?", (laptop_id,)).fetchone()
    installed_parts = conn.execute("""
        SELECT sp.* FROM laptop_spareparts lsp
        JOIN spareparts sp ON lsp.sparepart_id = sp.id
        WHERE lsp.laptop_id=?
    """, (laptop_id,)).fetchall()
    images = conn.execute("SELECT * FROM laptop_images WHERE laptop_id=? ORDER BY is_primary DESC, uploaded_date", (laptop_id,)).fetchall()
    return render_template("laptop_detail.html", laptop=laptop, installed_parts=installed_parts, images=images)

# --- Add spare part to laptop ---
@app.route("/add_sparepart_to_laptop/<int:laptop_id>", methods=["GET", "POST"])
@admin_required
def add_sparepart_to_laptop(laptop_id):
    conn = get_db()
    # Only show spare parts with quantity > 0
    spareparts = conn.execute("SELECT * FROM spareparts WHERE quantity > 0").fetchall()
    if request.method == "POST":
        sparepart_id = int(request.form["sparepart_id"])
        # Link spare part to laptop
        conn.execute("INSERT INTO laptop_spareparts (laptop_id, sparepart_id) VALUES (?, ?)", (laptop_id, sparepart_id))
        # Decrement quantity
        conn.execute("UPDATE spareparts SET quantity = quantity - 1 WHERE id=?", (sparepart_id,))
        conn.commit()
        return redirect(url_for("laptop_detail", laptop_id=laptop_id))
    return render_template("add_sparepart_to_laptop.html", laptop_id=laptop_id, spareparts=spareparts)

# --- Remove spare part from laptop ---
@app.route("/remove_sparepart_from_laptop/<int:laptop_id>/<int:sparepart_id>", methods=["POST"])
@admin_required
def remove_sparepart_from_laptop(laptop_id, sparepart_id):
    conn = get_db()
    # Remove the link
    conn.execute("DELETE FROM laptop_spareparts WHERE laptop_id=? AND sparepart_id=? LIMIT 1", (laptop_id, sparepart_id))
    # Increment quantity
    conn.execute("UPDATE spareparts SET quantity = quantity + 1 WHERE id=?", (sparepart_id,))
    conn.commit()
    return redirect(url_for("laptop_detail", laptop_id=laptop_id))

# --- Serve images from database ---
@app.route("/image/<int:laptop_id>")
def serve_image(laptop_id):
    conn = get_db()
    # First try to get primary image from new table
    image = conn.execute("SELECT image_data, image_mimetype FROM laptop_images WHERE laptop_id=? AND is_primary=1", (laptop_id,)).fetchone()
    
    if not image:
        # Get any image from new table
        image = conn.execute("SELECT image_data, image_mimetype FROM laptop_images WHERE laptop_id=? ORDER BY uploaded_date LIMIT 1", (laptop_id,)).fetchone()
    
    if image and image["image_data"]:
        return Response(image["image_data"], mimetype=image["image_mimetype"])
    
    # Fallback to old single image system for backward compatibility
    laptop = conn.execute("SELECT image_data, image_mimetype, image FROM laptops WHERE id=?", (laptop_id,)).fetchone()
    if laptop and laptop["image_data"]:
        return Response(laptop["image_data"], mimetype=laptop["image_mimetype"])
    elif laptop and laptop["image"]:
        try:
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], laptop["image"])
            if os.path.exists(image_path):
                return send_file(image_path)
        except:
            pass
    
    abort(404)

# --- Serve specific image by image ID ---
@app.route("/image/<int:laptop_id>/<int:image_id>")
def serve_specific_image(laptop_id, image_id):
    conn = get_db()
    image = conn.execute("SELECT image_data, image_mimetype FROM laptop_images WHERE id=? AND laptop_id=?", (image_id, laptop_id)).fetchone()
    
    if image and image["image_data"]:
        return Response(image["image_data"], mimetype=image["image_mimetype"])
    
    abort(404)

# --- Upload single image ---
@app.route("/upload_single_image/<int:laptop_id>", methods=["POST"])
@admin_required
def upload_single_image(laptop_id):
    conn = get_db()
    
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename and allowed_file(file.filename):
            image_data = file.read()
            image_mimetype = file.mimetype
            image_name = secure_filename(file.filename)
            
            conn.execute("""
                INSERT INTO laptop_images (laptop_id, image_data, image_mimetype, image_name, is_primary)
                VALUES (?, ?, ?, ?, ?)
            """, (laptop_id, image_data, image_mimetype, image_name, 0))
            conn.commit()
            return Response("Success", status=200)
    
    return Response("Failed", status=400)

# --- Delete specific image ---
@app.route("/delete_image/<int:laptop_id>/<int:image_id>", methods=["POST"])
@admin_required
def delete_image(laptop_id, image_id):
    conn = get_db()
    
    try:
        # Check if the image exists and if it's primary
        image_check = conn.execute("SELECT is_primary FROM laptop_images WHERE id=? AND laptop_id=?", (image_id, laptop_id)).fetchone()
        
        if image_check:
            is_primary = image_check["is_primary"]
            
            # Delete the image
            conn.execute("DELETE FROM laptop_images WHERE id=? AND laptop_id=?", (image_id, laptop_id))
            
            # If we deleted a primary image, make another one primary
            if is_primary == 1:
                # Find the next available image for this laptop
                next_image = conn.execute("SELECT id FROM laptop_images WHERE laptop_id=? LIMIT 1", (laptop_id,)).fetchone()
                if next_image:
                    conn.execute("UPDATE laptop_images SET is_primary=1 WHERE id=?", (next_image["id"],))
            
            conn.commit()
            return Response("Success", status=200)
        else:
            return Response("Image not found", status=404)
        
    except Exception as e:
        print(f"Error in delete_image: {e}")
        conn.rollback()
        return Response("Error deleting image", status=500)

# --- Set primary image ---
@app.route("/set_primary_image/<int:laptop_id>/<int:image_id>", methods=["POST"])
@admin_required
def set_primary_image(laptop_id, image_id):
    try:
        conn = get_db()
        # Remove primary flag from all images for this laptop
        conn.execute("UPDATE laptop_images SET is_primary=0 WHERE laptop_id=?", (laptop_id,))
        # Set new primary image
        conn.execute("UPDATE laptop_images SET is_primary=1 WHERE id=? AND laptop_id=?", (image_id, laptop_id))
        conn.commit()
        return Response("Success", status=200)
    except Exception as e:
        print(f"Error setting primary image: {e}")
        return Response("Error setting primary image", status=500)

# --- Bulk delete laptops ---
@app.route("/bulk_delete", methods=["POST"])
@admin_required
def bulk_delete():
    try:
        data = request.get_json()
        laptop_ids = data.get('laptop_ids', [])
        
        if not laptop_ids:
            return Response("No laptop IDs provided", status=400)
        
        with get_db() as conn:
            # Delete all images for these laptops first
            for laptop_id in laptop_ids:
                conn.execute("DELETE FROM laptop_images WHERE laptop_id = ?", (laptop_id,))
            
            # Delete laptop_spareparts relationships
            placeholders = ','.join(['?' for _ in laptop_ids])
            conn.execute(f"DELETE FROM laptop_spareparts WHERE laptop_id IN ({placeholders})", laptop_ids)
            
            # Delete the laptops
            conn.execute(f"DELETE FROM laptops WHERE id IN ({placeholders})", laptop_ids)
            conn.commit()
        
        return Response("Laptops deleted successfully", status=200)
    except Exception as e:
        print(f"Error in bulk delete: {e}")
        return Response("Error deleting laptops", status=500)

# --- Bulk duplicate laptops ---
@app.route("/bulk_duplicate", methods=["POST"])
@admin_required
def bulk_duplicate():
    try:
        data = request.get_json()
        laptop_ids = data.get('laptop_ids', [])
        
        if not laptop_ids:
            return Response("No laptop IDs provided", status=400)
        
        with get_db() as conn:
            cursor = conn.cursor()
            for laptop_id in laptop_ids:
                # Get the original laptop data
                laptop = cursor.execute("SELECT * FROM laptops WHERE id = ?", (laptop_id,)).fetchone()
                if laptop:
                    # Generate new serial number for the copy
                    copy_name = f"{laptop['laptop_name']} (Copy)"
                    new_serial = generate_serial_number(copy_name)
                    
                    # Insert duplicated laptop with new serial number
                    cursor.execute("""
                        INSERT INTO laptops (laptop_name, cpu, ram, storage, os, notes, 
                                           price_bought, price_to_sell, fees, sold, serial_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        copy_name,
                        laptop['cpu'], 
                        laptop['ram'], 
                        laptop['storage'], 
                        laptop['os'],
                        laptop['notes'], 
                        laptop['price_bought'], 
                        laptop['price_to_sell'],
                        laptop['fees'], 
                        0,  # sold=0
                        new_serial
                    ))
                    
                    new_laptop_id = cursor.lastrowid
                    
                    # Copy images and spare parts (same as before)
                    images = cursor.execute("SELECT * FROM laptop_images WHERE laptop_id = ?", (laptop_id,)).fetchall()
                    for image in images:
                        cursor.execute("""
                            INSERT INTO laptop_images (laptop_id, image_data, image_mimetype, 
                                                     image_name, is_primary)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            new_laptop_id, image['image_data'], image['image_mimetype'],
                            image['image_name'], image['is_primary']
                        ))
                    
                    spare_parts = cursor.execute("SELECT sparepart_id FROM laptop_spareparts WHERE laptop_id = ?", (laptop_id,)).fetchall()
                    for spare_part in spare_parts:
                        cursor.execute("INSERT INTO laptop_spareparts (laptop_id, sparepart_id) VALUES (?, ?)", 
                                     (new_laptop_id, spare_part['sparepart_id']))
            
            conn.commit()
        
        return Response("Laptops duplicated successfully", status=200)
    except Exception as e:
        print(f"Error in bulk duplicate: {e}")
        import traceback
        traceback.print_exc()
        return Response(f"Error duplicating laptops: {str(e)}", status=500)

def get_warranty_status(warranty_start_date, warranty_duration_days):
    """Calculate warranty status and days remaining"""
    if not warranty_start_date or not warranty_duration_days:
        return None, None, None
    
    from datetime import datetime, timedelta
    
    try:
        start_date = datetime.strptime(warranty_start_date, '%Y-%m-%d')
        end_date = start_date + timedelta(days=warranty_duration_days)
        today = datetime.now()
        
        if today > end_date:
            return "expired", 0, "expired"
        
        days_remaining = (end_date - today).days + 1
        
        if days_remaining > 60:
            status_color = "green"
        elif days_remaining > 30:
            status_color = "orange"
        else:
            status_color = "red"
            
        return "active", days_remaining, status_color
        
    except ValueError:
        return None, None, None

def format_warranty_display(days_remaining, status_color):
    """Format warranty display text with color"""
    if days_remaining is None:
        return ""
    
    if days_remaining == 0:
        return '<span style="background: #ef4444; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: bold;">EXPIRED</span>'
    
    color_map = {
        "green": "#10b981",
        "orange": "#f59e0b", 
        "red": "#ef4444"
    }
    
    return f'<span style="background: {color_map[status_color]}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: bold;">{days_remaining} days left</span>'

# Add these routes after your existing routes

@app.route("/ongoing_warranties")
@admin_required
def ongoing_warranties():
    """Show laptops with active warranties"""
    conn = get_db()
    
    # Get sold laptops with active warranties
    laptops = conn.execute("""
        SELECT * FROM laptops 
        WHERE sold = 1 
        AND warranty_start_date IS NOT NULL 
        AND warranty_duration_days > 0
        ORDER BY warranty_start_date DESC
    """).fetchall()
    
    # Calculate warranty status for each laptop
    warranty_laptops = []
    for laptop in laptops:
        status, days_remaining, color = get_warranty_status(
            laptop['warranty_start_date'], 
            laptop['warranty_duration_days']
        )
        
        if status == "active":  # Only show active warranties
            laptop_dict = dict(laptop)
            laptop_dict['warranty_status'] = status
            laptop_dict['days_remaining'] = days_remaining
            laptop_dict['status_color'] = color
            laptop_dict['warranty_display'] = format_warranty_display(days_remaining, color)
            warranty_laptops.append(laptop_dict)
    
    return render_template("ongoing_warranties.html", laptops=warranty_laptops)

@app.route("/add_warranty/<int:laptop_id>", methods=["GET", "POST"])
@admin_required
def add_warranty(laptop_id):
    """Add warranty to a sold laptop"""
    conn = get_db()
    laptop = conn.execute("SELECT * FROM laptops WHERE id = ? AND sold = 1", (laptop_id,)).fetchone()
    
    if not laptop:
        flash("Laptop not found or not sold", "error")
        return redirect(url_for("completed_sales"))
    
    if request.method == "POST":
        warranty_start_date = request.form.get("warranty_start_date")
        warranty_duration_days = safe_float(request.form.get("warranty_duration_days"), 0)
        warranty_notes = request.form.get("warranty_notes", "")
        
        try:
            conn.execute("""
                UPDATE laptops 
                SET warranty_start_date = ?, warranty_duration_days = ?, warranty_notes = ?
                WHERE id = ?
            """, (warranty_start_date, int(warranty_duration_days), warranty_notes, laptop_id))
            conn.commit()
            flash("Warranty added successfully!", "success")
            return redirect(url_for("completed_sales"))
        except Exception as e:
            flash("Error adding warranty", "error")
            print(f"Error adding warranty: {e}")
    
    return render_template("add_warranty.html", laptop=laptop)

@app.route("/edit_warranty/<int:laptop_id>", methods=["GET", "POST"])
@admin_required
def edit_warranty(laptop_id):
    """Edit warranty for a laptop"""
    conn = get_db()
    laptop = conn.execute("SELECT * FROM laptops WHERE id = ?", (laptop_id,)).fetchone()
    
    if not laptop:
        flash("Laptop not found", "error")
        return redirect(url_for("completed_sales"))
    
    if request.method == "POST":
        warranty_start_date = request.form.get("warranty_start_date")
        warranty_duration_days = safe_float(request.form.get("warranty_duration_days"), 0)
        warranty_notes = request.form.get("warranty_notes", "")
        
        try:
            conn.execute("""
                UPDATE laptops 
                SET warranty_start_date = ?, warranty_duration_days = ?, warranty_notes = ?
                WHERE id = ?
            """, (warranty_start_date, int(warranty_duration_days), warranty_notes, laptop_id))
            conn.commit()
            flash("Warranty updated successfully!", "success")
            return redirect(url_for("ongoing_warranties"))
        except Exception as e:
            flash("Error updating warranty", "error")
            print(f"Error updating warranty: {e}")
    
    return render_template("edit_warranty.html", laptop=laptop)

# --- Guest Shopping Routes ---
@app.route("/shop")
def guest_shop():
    # No login required - this is now the public guest interface
    
    search = request.args.get('search', '')
    
    conn = get_db()
    query = "SELECT * FROM laptops WHERE sold = 0"
    params = []
    
    if search:
        query += " AND (laptop_name LIKE ? OR cpu LIKE ? OR ram LIKE ? OR storage LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param])
    
    query += " ORDER BY id DESC"
    laptops = conn.execute(query, params).fetchall()
    
    # Convert to list of dictionaries and add image data
    laptops_with_images = []
    for laptop in laptops:
        laptop_dict = dict(laptop)
        
        # Get primary image from laptop_images table
        primary_image = conn.execute("""
            SELECT image_data FROM laptop_images 
            WHERE laptop_id = ? AND is_primary = 1 
            ORDER BY uploaded_date DESC LIMIT 1
        """, (laptop['id'],)).fetchone()
        
        # If no primary image, get any image
        if not primary_image:
            primary_image = conn.execute("""
                SELECT image_data FROM laptop_images 
                WHERE laptop_id = ? 
                ORDER BY uploaded_date DESC LIMIT 1
            """, (laptop['id'],)).fetchone()
        
        # Add image data to laptop dict
        if primary_image:
            import base64
            laptop_dict['image_data'] = base64.b64encode(primary_image['image_data']).decode('utf-8')
        else:
            laptop_dict['image_data'] = None
            
        laptops_with_images.append(laptop_dict)
    
    conn.close()
    
    # Get cart count
    cart_count = len(session.get('cart', []))
    
    return render_template('guest_shop.html', laptops=laptops_with_images, search=search, cart_count=cart_count)

@app.route("/add_to_cart/<int:laptop_id>")
def add_to_cart(laptop_id):
    # No login required - anyone can add to cart
    
    # Initialize cart if not exists
    if 'cart' not in session:
        session['cart'] = []
    
    # Check if laptop exists and is available
    with get_db() as conn:
        laptop = conn.execute("SELECT * FROM laptops WHERE id = ? AND sold = 0", (laptop_id,)).fetchone()
        if not laptop:
            flash('Laptop not available.', 'error')
            return redirect(url_for('guest_shop'))
    
    # Check if already in cart
    if laptop_id not in session['cart']:
        session['cart'].append(laptop_id)
        flash(f'{laptop["laptop_name"]} added to cart!', 'success')
    else:
        flash('This laptop is already in your cart.', 'warning')
    
    return redirect(url_for('guest_shop'))

@app.route("/remove_from_cart/<int:laptop_id>")
def remove_from_cart(laptop_id):
    # No login required
    
    if 'cart' in session and laptop_id in session['cart']:
        session['cart'].remove(laptop_id)
        flash('Item removed from cart.', 'info')
    
    return redirect(url_for('view_cart'))

@app.route("/cart")
def view_cart():
    # No login required
    
    cart_items = []
    total_amount = 0
    
    if 'cart' in session and session['cart']:
        with get_db() as conn:
            placeholders = ','.join(['?'] * len(session['cart']))
            cart_laptops = conn.execute(
                f"SELECT * FROM laptops WHERE id IN ({placeholders}) AND sold = 0", 
                session['cart']
            ).fetchall()
            
            # Convert to list of dictionaries and add image data
            for laptop in cart_laptops:
                laptop_dict = dict(laptop)
                
                # Get primary image from laptop_images table
                primary_image = conn.execute("""
                    SELECT image_data FROM laptop_images 
                    WHERE laptop_id = ? AND is_primary = 1 
                    ORDER BY uploaded_date DESC LIMIT 1
                """, (laptop['id'],)).fetchone()
                
                # If no primary image, get any image
                if not primary_image:
                    primary_image = conn.execute("""
                        SELECT image_data FROM laptop_images 
                        WHERE laptop_id = ? 
                        ORDER BY uploaded_date DESC LIMIT 1
                    """, (laptop['id'],)).fetchone()
                
                # Add image data to laptop dict
                if primary_image:
                    import base64
                    laptop_dict['image_data'] = base64.b64encode(primary_image['image_data']).decode('utf-8')
                else:
                    laptop_dict['image_data'] = None
                    
                cart_items.append(laptop_dict)
                total_amount += laptop['price_to_sell']
    
    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    # No login required - collect guest info at checkout
    
    if 'cart' not in session or not session['cart']:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('guest_shop'))  # Redirect to guest shop
    
    if request.method == "GET":
        # Show checkout form with guest information fields
        cart_items = []
        total_amount = 0
        
        with get_db() as conn:
            placeholders = ','.join(['?'] * len(session['cart']))
            cart_laptops = conn.execute(
                f"SELECT * FROM laptops WHERE id IN ({placeholders}) AND sold = 0", 
                session['cart']
            ).fetchall()
            
            # Convert to list of dictionaries and add image data
            for laptop in cart_laptops:
                laptop_dict = dict(laptop)
                
                # Get primary image from laptop_images table
                primary_image = conn.execute("""
                    SELECT image_data FROM laptop_images 
                    WHERE laptop_id = ? AND is_primary = 1 
                    ORDER BY uploaded_date DESC LIMIT 1
                """, (laptop['id'],)).fetchone()
                
                # If no primary image, get any image
                if not primary_image:
                    primary_image = conn.execute("""
                        SELECT image_data FROM laptop_images 
                        WHERE laptop_id = ? 
                        ORDER BY uploaded_date DESC LIMIT 1
                    """, (laptop['id'],)).fetchone()
                
                # Add image data to laptop dict
                if primary_image:
                    import base64
                    laptop_dict['image_data'] = base64.b64encode(primary_image['image_data']).decode('utf-8')
                else:
                    laptop_dict['image_data'] = None
                    
                cart_items.append(laptop_dict)
                total_amount += laptop['price_to_sell']
        
        return render_template('checkout.html', cart_items=cart_items, total_amount=total_amount)
    
    # POST request - process the order
    guest_name = request.form.get('guest_name')
    guest_email = request.form.get('guest_email')
    guest_phone = request.form.get('guest_phone', '')
    notes = request.form.get('notes', '')
    
    if not guest_name or not guest_email:
        flash('Please provide your name and email address.', 'error')
        return redirect(url_for('checkout'))
    
    with get_db() as conn:
        # Verify all items are still available
        placeholders = ','.join(['?'] * len(session['cart']))
        available_laptops = conn.execute(
            f"SELECT * FROM laptops WHERE id IN ({placeholders}) AND sold = 0", 
            session['cart']
        ).fetchall()
        
        if len(available_laptops) != len(session['cart']):
            flash('Some items in your cart are no longer available.', 'error')
            return redirect(url_for('view_cart'))
        
        # Calculate total
        total_amount = sum(laptop['price_to_sell'] for laptop in available_laptops)
        
        # Create order
        cursor = conn.execute("""
            INSERT INTO orders (guest_name, guest_email, guest_phone, total_amount, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (guest_name, guest_email, guest_phone, total_amount, notes))
        
        order_id = cursor.lastrowid
        
        # Add order items
        for laptop in available_laptops:
            conn.execute("""
                INSERT INTO order_items (order_id, laptop_id, quantity, price)
                VALUES (?, ?, 1, ?)
            """, (order_id, laptop['id'], laptop['price_to_sell']))
        
        conn.commit()
    
    # Clear cart
    session['cart'] = []
    
    flash('Your order has been submitted! Order ID: #' + str(order_id), 'success')
    return redirect(url_for('guest_orders'))

@app.route("/my_orders", methods=["GET", "POST"])
def guest_orders():
    # No login required - check orders by email
    
    if request.method == "GET":
        return render_template('order_lookup.html')
    
    # POST - lookup orders by email
    email = request.form.get('email')
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('guest_orders'))
    
    with get_db() as conn:
        orders = conn.execute("""
            SELECT o.*, COUNT(oi.id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.guest_email = ?
            GROUP BY o.id
            ORDER BY o.created_date DESC
        """, (email,)).fetchall()
    
    return render_template('guest_orders.html', orders=orders, email=email)

# --- Admin Order Management Routes ---
@app.route("/admin/orders")
@admin_required
def admin_orders():
    with get_db() as conn:
        unconfirmed_orders = conn.execute("""
            SELECT o.*, COUNT(oi.id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'unconfirmed'
            GROUP BY o.id
            ORDER BY o.created_date DESC
        """).fetchall()
        
        confirmed_orders = conn.execute("""
            SELECT o.*, COUNT(oi.id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status IN ('confirmed', 'in_progress')
            GROUP BY o.id
            ORDER BY o.created_date DESC
        """).fetchall()
    
    return render_template('admin_orders.html', 
                         unconfirmed_orders=unconfirmed_orders,
                         confirmed_orders=confirmed_orders)

@app.route("/admin/order/<int:order_id>")
@admin_required
def admin_order_details(order_id):
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('admin_orders'))
        
        order_items = conn.execute("""
            SELECT oi.*, l.laptop_name, l.cpu, l.ram, l.storage, l.serial_number
            FROM order_items oi
            JOIN laptops l ON oi.laptop_id = l.id
            WHERE oi.order_id = ?
        """, (order_id,)).fetchall()
    
    return render_template('admin_order_details.html', order=order, order_items=order_items)

@app.route("/admin/order/<int:order_id>/confirm", methods=["POST"])
@admin_required
def confirm_order(order_id):
    with get_db() as conn:
        conn.execute("""
            UPDATE orders SET status = 'confirmed', confirmed_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (order_id,))
        conn.commit()
    
    flash('Order confirmed successfully!', 'success')
    return redirect(url_for('admin_orders'))

@app.route("/admin/order/<int:order_id>/reject", methods=["POST"])
@admin_required
def reject_order(order_id):
    with get_db() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
    
    flash('Order rejected and deleted.', 'info')
    return redirect(url_for('admin_orders'))

@app.route("/admin/order/<int:order_id>/start", methods=["POST"])
@admin_required
def start_order(order_id):
    with get_db() as conn:
        conn.execute("""
            UPDATE orders SET status = 'in_progress'
            WHERE id = ?
        """, (order_id,))
        conn.commit()
    
    flash('Order started!', 'info')
    return redirect(url_for('admin_orders'))

@app.route("/admin/order/<int:order_id>/finish", methods=["POST"])
@admin_required
def finish_order(order_id):
    with get_db() as conn:
        # Get order items
        order_items = conn.execute("""
            SELECT laptop_id FROM order_items WHERE order_id = ?
        """, (order_id,)).fetchall()
        
        # Mark laptops as sold
        for item in order_items:
            conn.execute("""
                UPDATE laptops SET sold = 1, date_sold = ?
                WHERE id = ?
            """, (datetime.datetime.now().strftime('%Y-%m-%d'), item['laptop_id']))
        
        # Update order status
        conn.execute("""
            UPDATE orders SET status = 'completed', completed_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (order_id,))
        
        conn.commit()
    
    flash('Order completed! Laptops moved to sales.', 'success')
    return redirect(url_for('admin_orders'))

@app.route("/admin/order/<int:order_id>/undo", methods=["POST"])
@admin_required
def undo_order(order_id):
    with get_db() as conn:
        conn.execute("""
            UPDATE orders SET status = 'unconfirmed', confirmed_date = NULL
            WHERE id = ?
        """, (order_id,))
        conn.commit()
    
    flash('Order moved back to unconfirmed.', 'info')
    return redirect(url_for('admin_orders'))

@app.route("/admin/order/<int:order_id>/delete", methods=["POST"])
@admin_required
def delete_order(order_id):
    with get_db() as conn:
        # Get order items to return laptops to inventory
        order_items = conn.execute("""
            SELECT laptop_id FROM order_items WHERE order_id = ?
        """, (order_id,)).fetchall()
        
        # Mark laptops as available again
        for item in order_items:
            conn.execute("""
                UPDATE laptops SET sold = 0, date_sold = NULL
                WHERE id = ?
            """, (item['laptop_id'],))
        
        # Delete order (cascade will delete order_items)
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
    
    flash('Order deleted and items returned to inventory.', 'success')
    return redirect(url_for('admin_orders'))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)