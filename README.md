# Laptop Inventory Management System v1.22b (Beta)

A web-based tool for managing laptop inventory, spare parts, sales, warranty tracking, customer order management, and now **Google Drive cloud sync** with **advanced spare parts pricing and customization**. Uses Flask and Docker, stores everything in a database so it works reliably across different computers.

## 🚀 New in v1.22b (Beta)

- **Spare Parts Pricing System:**  
  - Add price tracking to all spare parts (RAM, Storage)
  - View pricing breakdown: Original laptop price + Upgrades value
  - Track spare part prices at time of installation

- **Guest Laptop Customization:**  
  - Customers can add spare parts upgrades to laptops before purchasing
  - Interactive laptop detail page with customization options
  - Real-time price calculation showing base price + upgrades
  - Enhanced cart showing spare parts breakdown and totals

- **Enhanced Admin Features:**
  - Spare parts pricing management with individual cost tracking
  - Laptop detail page shows original price vs. upgraded price
  - Track spare part installation history with pricing
  - Remove spare parts from laptops with price adjustments

## 🚀 Previous Features (v1.2b)

- **Guest & Admin Modes:**  
  - Customers (guests) can browse your store's current stock without logging in.
  - Admins log in to manage inventory, orders, sales, and more.

- **Order System:**  
  - Guests can add multiple laptops to a cart and place an order.
  - Admins can view, confirm, reject, and process orders.
  - Orders move through statuses: unconfirmed, confirmed, in progress, completed.
  - Admins can revert completed sales back to orders if needed.

- **Order Tracking:**  
  - Guests can check their order status by email.

- **Google Drive Sync (v1.21b):**
  - Admins can connect their own Google Drive account in the Settings page.
  - Upload/download the database file (`laptops.db`) to/from Google Drive for easy backup and syncing between computers.
  - Each user must provide their own `credentials.json` (see below).

---

![Admin and Guest](docs/1.png)

![Main Inventory](docs/2.png)

![Orders](docs/3.png)

![Spare Parts Pricing](docs/spareparts_pricing.png)
*NEW: Spare parts with individual pricing and inventory management*

![Guest Customization](docs/guest_customization.png)
*NEW: Customers can customize laptops with spare parts before purchasing*

![Pricing Breakdown](docs/pricing_breakdown.png)
*NEW: Clear pricing breakdown showing original price + upgrades*

![Warranty](docs/warranty.png)
*Add and Track warranties to sold laptops*

![Sales](docs/sales.png)
*See total sales and profit numbers*

![Add Laptop Interface](docs/add_laptops.png)
*Adding a new laptop to the inventory*

![Edit & Image Management](docs/edit_laptop.png)
*Editing existing laptop details*

![Spareparts Management](docs/spareparts.png)
*Edit spareparts such RAM and storage*

![Bulk Operations](docs/bulk_selection.png)
*Selecting multiple laptops for bulk operations like deleting and duplicating*

![Google Drive Connect](docs/google_drive_connect.png)
*Connect your google account to sync your database(new in v1.21b)*

## What It Does

### Smart Serial Numbers
Instead of just using 1, 2, 3... this generates proper serial numbers like **DE092501** (Dell laptop, added in September 2025, #1 for that month). Works for all major brands and automatically detects them from the laptop name.

### Spare Parts Pricing & Customization (NEW in v1.22b)
Track individual prices for all spare parts and let customers customize laptops:
- **Admin side**: Add prices to RAM and storage components, see pricing breakdowns
- **Customer side**: Browse laptops and add upgrades with real-time price calculation  
- **Cart integration**: Shows "Base: $600 + Upgrades: $150 = Total: $750"
- **Installation tracking**: Track when parts were added and at what price
- **Inventory management**: Automatic quantity updates when parts are installed

### Warranty Tracking
Track warranties for sold laptops with smart countdown timers. Shows **196 days left** in green, **45 days left** in orange, and **15 days left** in red. Separate page for managing all ongoing warranties so you know when to follow up with customers.

### Track Everything
- Laptop specs (CPU, RAM, storage, operating system)
- Purchase price, selling price, fees, and automatic profit calculation
- Multiple photos per laptop stored in the database
- When you bought it, when you sold it, profit margins
- Warranty periods with automatic countdown and color alerts
- **Spare parts pricing and installation history** 🆕
- **Customer laptop customization and upgrade pricing** 🆕
- **Order management and tracking for customers and admins**
- **Google Drive cloud sync for database backup and sharing**
- Search through everything quickly

### Handle Spare Parts with Pricing
Keep track of RAM sticks and storage drives with individual pricing, then link them to laptops when you install upgrades. Shows:
- **Original laptop price** vs **total price with upgrades**
- **Installation history** with dates and prices paid
- **Available upgrades** customers can add to their cart
- **Real-time pricing** as customers customize laptops

### Bulk Operations
Select multiple laptops and delete or duplicate them all at once. The duplicate feature creates copies with new serial numbers and adds "(Copy)" to the name.

### Sales & Warranty Management
- Mark laptops as sold and they move to a separate "completed sales" section.
- Add warranties to sold laptops and track them with color-coded timers.
- See which warranties are expiring soon.
- **Revert completed sales back to orders if needed.**

### Order Management with Customization
- **Guests can customize laptops** with spare parts before adding to cart
- **Interactive pricing** shows breakdown of base price + upgrades
- **Enhanced cart** displays all components and pricing details
- **Admin order processing** includes spare parts in order details
- Orders are split into unconfirmed and confirmed sections for easy management
- Guests can check their order status by email

### Google Drive Sync
- Go to **Settings** in the admin sidebar.
- Connect your Google Drive account (OAuth login).
- Upload/download the database file for backup or to sync between computers.
- **Each user must provide their own `credentials.json` file** (see below).

## How to Enable Google Drive Sync

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project, enable **Google Drive API**.
3. Go to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth client ID**.
5. Choose **Web application**
6. Add URI: http://127.0.0.1:5000/google_drive_callback
7. Go to Oauth consent screen > Audience > Test Users > Add the email you want to use. If you don't do this, you might get an error (Although you can do this later).
8. Download the `credentials.json` file. (rename the file to "credentials.json)
9. Place `credentials.json` in the `/app` folder (next to `app.py`).
10. **Do NOT commit `credentials.json` to git!**  
   Add it to your `.gitignore`:
   ```
   credentials.json
   ```
11. Each user must repeat these steps to use their own Google Drive account.

If `credentials.json` is missing, the Settings page will show instructions.

## Why I Built This

I buy, repair, and sell laptops as a side business. Existing solutions were either too complicated, too expensive, or didn't handle images properly. I wanted something that:

- Stores images in the database (not as files that can get lost)
- Generates professional-looking serial numbers
- Works the same whether I'm on my desktop or laptop
- Handles spare parts and upgrades **with proper pricing tracking**
- **Lets customers see upgrade options and pricing before buying**
- Actually calculates profits correctly **including spare parts costs**
- Tracks customer warranties so I know when they expire
- **Lets me backup and sync my database easily using Google Drive**

## Installation

### With Docker (Recommended)
```bash
git clone https://github.com/Ang-edgar/laptop-inventory-management.git
cd laptop-inventory-management
docker-compose up -d
```
Open http://localhost:5000 in your browser.

### Without Docker
```bash
pip install flask werkzeug google-api-python-client google-auth-httplib2 google-auth-oauthlib
python app/app.py
```

## Features I'm Proud Of

- **Spare parts pricing system**: Track costs and let customers see upgrade pricing
- **Customer laptop customization**: Interactive upgrade selection with real-time pricing
- **Pricing transparency**: Clear breakdown of base price vs. upgrades
- **Image management**: Upload multiple photos, set one as primary, delete individually
- **Bulk operations**: Select multiple laptops and handle them all at once  
- **Smart serial numbers**: Professional inventory codes with date and brand info
- **Spare parts tracking**: Know exactly what components you have, where they're installed, and what they cost
- **Profit calculations**: See exactly how much money you're making (including spare parts)
- **Warranty tracking**: Color-coded countdown timers for customer warranties
- **Order management**: Guests can order laptops with customizations, admins can manage orders
- **Google Drive sync**: Backup and share your database between computers
- **No dependencies**: Runs entirely from the database file, easy to backup

## Who This Is For

- People who buy and sell laptops (like me) who want to offer upgrade options
- Computer repair shops that need inventory, pricing, and warranty tracking
- Anyone managing more than a few laptops and getting tired of spreadsheets
- IT departments tracking company assets and warranties
- **Laptop resellers who want to offer customization options to customers**

## Version History

### v1.22b (Beta) - Spare Parts Pricing & Guest Customization
- **Spare parts pricing system with individual cost tracking**
- **Guest laptop customization with real-time price calculation**
- **Enhanced cart showing pricing breakdown (base + upgrades)**  
- **Admin spare parts pricing management**
- **Installation history tracking with pricing**
- Database improvements for spare parts pricing
- UI enhancements for pricing display

### v1.21b (Beta) - Google Drive Sync
- **Google Drive cloud sync for database backup and sharing**
- Bugfixes and UI improvements

### v1.2b (Beta) - Guest/Admin Modes, Order System & Google Drive Sync
- Guest portal for customers to browse and order laptops (no login required)
- Admin login for full inventory and order management
- Multi-laptop cart and order checkout for guests
- Admin order approval workflow (confirm, reject, start, finish, revert)
- Order tracking for guests by email

### v1.1 - Warranty Tracking
- Complete warranty management system for sold laptops
- Color-coded warranty countdown timers (green/orange/red)
- Dedicated "Ongoing Warranties" page
- Add/edit warranty functionality with preset durations
- Enhanced completed sales page with warranty buttons

### v1.0 - Core System
- Serial number system with date integration (DE092501 format)
- Image upload with drag-and-drop
- Bulk select and operations
- Clean button designs and hover effects
- Toast notifications when you save changes

## Technical Details

- **Backend**: Python Flask with SQLite
- **Database**: SQLite with proper foreign keys and pricing tables
- **Storage**: Images stored as BLOB data (portable across computers)
- **Deployment**: Docker containers with persistent volumes
- **Frontend**: Plain HTML/CSS/JavaScript (no heavy frameworks)
- **New Features**: Spare parts pricing, guest customization, enhanced cart system

Built by Edgar Effendi in 2025. MIT license - use it however you want.

---

**Ready to turn your laptop business into a professional operation with customer customization options? Clone this repo and get started!**