from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session, Response, abort
import sqlite3
import datetime
import csv
import io
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for session
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Database helper ---
def get_db():
    # Get database path from environment variable or use default
    db_path = os.environ.get('DB_PATH', 'laptops.db')
    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    return conn

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
        image TEXT, -- stores image filename (legacy)
        image_data BLOB, -- stores image binary data
        image_mimetype TEXT, -- stores image MIME type
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_edited TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        date_sold TEXT,
        sold INTEGER DEFAULT 0
    )
    """)
    
    # Add new columns for existing databases
    try:
        conn.execute("ALTER TABLE laptops ADD COLUMN image_data BLOB")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        conn.execute("ALTER TABLE laptops ADD COLUMN image_mimetype TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.execute("""
    CREATE TABLE IF NOT EXISTS spareparts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_type TEXT,         -- 'Storage' or 'RAM'
        storage_type TEXT,      -- For Storage: '2.5" HDD', '2.5" SSD', 'M.2 NVMe', 'M.2 SATA'
        ram_type TEXT,          -- For RAM: 'DDR3', 'DDR4'
        ram_speed TEXT,         -- For RAM: e.g. '1600MHz', '2400MHz'
        capacity TEXT,          -- e.g. '128GB', '1TB'
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

# --- Home page: list laptops ---
@app.route("/")
def index():
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
def add():
    if request.method == "POST":
        conn = get_db()
        
        # Insert laptop without images first
        cursor = conn.execute("""
            INSERT INTO laptops (laptop_name, cpu, ram, storage, os, notes, price_bought, price_to_sell, fees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["laptop_name"],
            request.form["cpu"],
            request.form["ram"],
            request.form["storage"],
            request.form["os"],
            request.form["notes"],
            request.form["price_bought"],
            request.form["price_to_sell"],
            request.form["fees"]
        ))
        
        laptop_id = cursor.lastrowid
        
        # Handle multiple image uploads
        if "images" in request.files:
            files = request.files.getlist("images")
            for i, file in enumerate(files):
                if file and allowed_file(file.filename):
                    image_data = file.read()
                    image_mimetype = file.mimetype
                    image_name = secure_filename(file.filename)
                    is_primary = 1 if i == 0 else 0  # First image is primary
                    
                    conn.execute("""
                        INSERT INTO laptop_images (laptop_id, image_data, image_mimetype, image_name, is_primary)
                        VALUES (?, ?, ?, ?, ?)
                    """, (laptop_id, image_data, image_mimetype, image_name, is_primary))
        
        conn.commit()
        return redirect(url_for("index"))
    return render_template("add.html")

# --- Completed sales page ---
@app.route("/completed")
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
def edit(laptop_id):
    conn = get_db()
    laptop = conn.execute("SELECT * FROM laptops WHERE id=?", (laptop_id,)).fetchone()
    if request.method == "POST":
        # This should only handle laptop details updates, not image uploads
        # Images are handled by the separate upload_single_image route
        
        # Check if this is a complete form submission (has laptop details)
        if "laptop_name" in request.form:
            try:
                # Update laptop details with proper error handling
                price_bought = float(request.form.get("price_bought", 0) or 0)
                price_to_sell = float(request.form.get("price_to_sell", 0) or 0)
                fees = float(request.form.get("fees", 0) or 0)
                
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
                return redirect(url_for("index"))
            except Exception as e:
                print(f"Error updating laptop: {e}")
                # Stay on the edit page if there's an error
    
    # Get images for display
    images = conn.execute("SELECT * FROM laptop_images WHERE laptop_id=? ORDER BY is_primary DESC, uploaded_date", (laptop_id,)).fetchall()
    return render_template("edit.html", laptop=laptop, images=images)

# --- Delete laptop ---
@app.route("/delete/<int:laptop_id>")
def delete(laptop_id):
    conn = get_db()
    conn.execute("DELETE FROM laptops WHERE id=?", (laptop_id,))
    conn.commit()
    return redirect(url_for("index"))

# --- Mark as sold ---
@app.route("/mark_sold/<int:laptop_id>")
def mark_sold(laptop_id):
    conn = get_db()
    now = datetime.datetime.now()
    conn.execute("""
        UPDATE laptops SET sold=1, last_edited=?, date_sold=?
        WHERE id=?
    """, (now, now, laptop_id))
    conn.commit()
    return redirect(url_for("index"))

# --- Mark as available ---
@app.route("/mark_available/<int:laptop_id>")
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
def settings():
    return render_template("settings.html")

# --- Reset data ---
@app.route("/reset_data", methods=["POST"])
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
def delete_sparepart(part_id):
    conn = get_db()
    conn.execute("DELETE FROM spareparts WHERE id=?", (part_id,))
    conn.commit()
    return redirect(url_for("spareparts"))

# --- Laptop detail page ---
@app.route("/laptop/<int:laptop_id>")
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
                    # Insert duplicated laptop with only essential columns
                    cursor.execute("""
                        INSERT INTO laptops (laptop_name, cpu, ram, storage, os, notes, 
                                           price_bought, price_to_sell, fees, sold)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        f"{laptop['laptop_name']} (Copy)",
                        laptop['cpu'], 
                        laptop['ram'], 
                        laptop['storage'], 
                        laptop['os'],
                        laptop['notes'], 
                        laptop['price_bought'], 
                        laptop['price_to_sell'],
                        laptop['fees'], 
                        0  # sold=0
                    ))
                    
                    new_laptop_id = cursor.lastrowid
                    
                    # Copy images from laptop_images table
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
                    
                    # Copy spare parts relationships
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)