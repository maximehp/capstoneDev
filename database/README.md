### `README.md`
- Documentation explaining the purpose of the database
- Instructions for viewing and using the database files
 ---

# Database

This folder contains the SQLite database used for the Capstone project.  
The database stores user-related information and is designed to be lightweight, portable, and easy to recreate.

---

## Files in this Folder

### `Capstone2026USERS.db`
- The **working SQLite database file**
- Contains the database schema and (eventually) the data
- This is the file used directly by the application

> Note: GitHub cannot preview `.db` files.  
> To view it, you must download the raw file and open it locally.

---

### `schemaCapstone2026.sql`
- The **database schema definition**
- Contains `CREATE TABLE` statements only
- Allows the database structure to be recreated from scratch without data

This file represents the **design/creation** of the database.

---



## How to View the Database

### Option 1: Download and Open the Database (Recommended)

1. Click on `Capstone2026USERS.db`
2. Select **Download raw file**
3. Open the file using a SQLite-compatible tool, such as:
   - DB Browser for SQLite
   - SQLiteStudio
   - Any SQLite client

Once opened, you can browse tables, view columns, and run queries.

---

### Option 2: Recreate the Database Using the Schema

If you do not want to use the `.db` file directly, you can recreate the database:

```bash
sqlite3 database.db < schemaCapstone2026.sql

