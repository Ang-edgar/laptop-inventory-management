# Laptop Inventory Management System

A web-based inventory system I built for tracking laptops, spare parts, and sales. Built with Flask and runs in Docker containers.

## Features

### Laptop Management
- Add laptops with specs (CPU, RAM, storage, OS, notes)
- Track purchase price, selling price, and fees
- Automatic profit calculations
- Search through your inventory
- Mark laptops as sold or available

### Image Support
- Upload multiple photos per laptop
- Set one as the primary image
- Images stored in database (works across different computers)
- Thumbnail view in the main list
- Click images to view full size

### Spare Parts Tracking
- Keep track of RAM and storage components
- Support for different types: DDR3/DDR4 RAM, various SSD/HDD formats
- Link spare parts to laptops you've upgraded
- See which laptops have extra components installed

### Bulk Actions
- Select multiple laptops at once
- Delete several laptops together
- Duplicate entries (creates copies with new IDs)
- Selection checkboxes positioned on the right side

### Sales Management
- Move sold laptops to a separate "completed sales" section
- Track when items were sold
- View total profits and sales figures
- Can move items back to inventory if needed

## How to Run

```bash
# Make sure you have Docker installed
git clone https://github.com/Ang-edgar/laptop-inventory-management.git
cd laptop-inventory-management

# Start the application
docker-compose up -d

# Open your browser to http://localhost:5000
```

## Technical Details

- **Backend**: Flask (Python)
- **Database**: SQLite with BLOB image storage
- **Frontend**: HTML/CSS/JavaScript with FontAwesome icons
- **Deployment**: Docker & Docker Compose
- **Storage**: Persistent data volumes

## Why I Built This

I needed a way to track laptops I buy and sell, including their specs, photos, and any upgrades I do. Existing solutions were either too complex or didn't handle images the way I wanted. This system stores everything in a database so it works the same whether I'm on my main computer or laptop.

## License

MIT License - feel free to use and modify as needed.

---

Built by Edgar Effendi, 2025