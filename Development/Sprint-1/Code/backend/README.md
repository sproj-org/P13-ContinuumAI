# 📘 ContinuumAI Backend – Developer Setup

## 1. Overview
This backend uses **FastAPI** + **MySQL** hosted on Railway.  
Schema and ETL files are already in `/database/`.  
You do **not** need the raw CSVs to run the app — only the connection string in `.env`.

---

## 2. Environment Setup

### Step 1: Create your `.env` file
```bash
# Copy the example file
cp env.example .env
```

### Step 2: Configure environment variables
1. Keep the provided Railway connection string (read/write access)
2. Replace `SECRET_KEY` with any random string for JWT tokens
3. (Optional) If you prefer local MySQL, update the `DATABASE_URL` line accordingly

**Example `.env` file:**
```env
DATABASE_URL=mysql+pymysql://root:hIbVQJNyAyBsgVIxIPEcWNciReGvvkWy@switchback.proxy.rlwy.net:11435/continuum_ai
SECRET_KEY=your-super-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256
DEBUG=True
```

---

## 3. Accessing the Database Schema

### Inspect or modify schema:
- Open `/database/schema.sql` for the DDL
- Run `SHOW TABLES;` from MySQL Workbench or CLI:

```bash
mysql -u root -p'hIbVQJNyAyBsgVIxIPEcWNciReGvvkWy' -h switchback.proxy.rlwy.net -P 11435 -D continuum_ai
```

### Available Tables:
- **Dimension Tables:** `Products`, `Customers`, `Regions`, `SalesReps`, `Users`
- **Fact Tables:** `SalesTransactions`, `Opportunities`

---

## 4. Database ETL Pipeline

### Regenerate data (if needed):
```bash
cd database
python full_etl_pipeline.py
```

This will:
- Extract data from `data/SampleSuperstore.csv`
- Transform into star schema format
- Generate 6 processed CSV files in `data/processed/`

### Import data to Railway:
```powershell
# Add MySQL to PATH
$env:PATH += ";C:\Program Files\MySQL\MySQL Server 8.4\bin"

# Import all data
Get-Content database\import_processed.sql | mysql -u root -p'hIbVQJNyAyBsgVIxIPEcWNciReGvvkWy' -h switchback.proxy.rlwy.net -P 11435 -D continuum_ai --local-infile=1
```

---

## 5. Database Architecture

### Star Schema Design:
```
┌──────────────┐      ┌─────────────────┐      ┌──────────────┐
│   Products   │──────│SalesTransactions│──────│  Customers   │
└──────────────┘      └─────────────────┘      └──────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
            ┌───────▼──────┐   ┌─────▼──────┐
            │   SalesReps  │   │   Regions  │
            └──────────────┘   └────────────┘
```

### Current Data Counts:
- Products: **1,862**
- Customers: **793**
- Regions: **4** (Central, East, South, West)
- SalesReps: **10**
- SalesTransactions: **5,009**
- Opportunities: **475**

---

## 6. Installation & Running

### Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Run the backend server:
```bash
uvicorn app.main:app --reload
```

The API will be available at: `http://localhost:8000`

### API Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 7. Project Structure

```
backend/
├── database/
│   ├── schema.sql                    # Database DDL
│   ├── fix_schema_complete.sql       # Schema fixes
│   ├── import_processed.sql          # Data import script
│   ├── full_etl_pipeline.py          # ETL pipeline
│   ├── fix_etl.py                    # ETL fixes
│   ├── VERIFICATION_CHECKLIST.md     # Setup status
│   └── data/
│       ├── SampleSuperstore.csv      # Source data
│       └── processed/                # Generated CSVs (gitignored)
├── .env.example                      # Environment template
├── .env                              # Your config (gitignored)
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

---

## 8. Database Verification Queries

### Check all table counts:
```sql
SELECT 'Products' as table_name, COUNT(*) as count FROM Products
UNION ALL SELECT 'Customers', COUNT(*) FROM Customers  
UNION ALL SELECT 'Regions', COUNT(*) FROM Regions
UNION ALL SELECT 'SalesReps', COUNT(*) FROM SalesReps
UNION ALL SELECT 'SalesTransactions', COUNT(*) FROM SalesTransactions
UNION ALL SELECT 'Opportunities', COUNT(*) FROM Opportunities;
```

### Test foreign key relationships:
```sql
SELECT r.region_name, 
       COUNT(DISTINCT sr.rep_id) as reps_count,
       COUNT(DISTINCT st.transaction_id) as transactions_count,
       ROUND(SUM(st.sales_amount), 2) as total_sales
FROM Regions r
LEFT JOIN SalesReps sr ON r.region_id = sr.region_id  
LEFT JOIN SalesTransactions st ON sr.rep_id = st.rep_id
GROUP BY r.region_id, r.region_name
ORDER BY total_sales DESC;
```

### Top 5 customers by sales:
```sql
SELECT c.customer_name,
       c.segment,
       COUNT(st.transaction_id) as purchase_count,
       ROUND(SUM(st.sales_amount), 2) as total_sales,
       ROUND(AVG(st.sales_amount), 2) as avg_order_value
FROM Customers c
JOIN SalesTransactions st ON c.customer_id = st.customer_id
GROUP BY c.customer_id, c.customer_name, c.segment
ORDER BY total_sales DESC
LIMIT 5;
```

---

## 9. Troubleshooting

### Issue: "mysql command not found"
**Solution:**
```powershell
$env:PATH += ";C:\Program Files\MySQL\MySQL Server 8.4\bin"
```

### Issue: "Access denied for user 'root'"
**Solution:** Verify the Railway connection string in your `.env` file matches `.env.example`

### Issue: "Foreign key constraint fails"
**Solution:** Re-run the schema fix:
```bash
mysql -u root -p'...' -h switchback.proxy.rlwy.net -P 11435 -D continuum_ai < database/fix_schema_complete.sql
```

---

## 10. Next Steps

- [ ] Complete authentication implementation (JWT)
- [ ] Create RESTful API endpoints for each table
- [ ] Add data validation with Pydantic models
- [ ] Implement role-based access control (RBAC)
- [ ] Connect frontend to backend API

---

## 📚 Additional Resources

- [Railway MySQL Documentation](https://docs.railway.app/databases/mysql)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM Guide](https://docs.sqlalchemy.org/en/20/)
- [Star Schema Design Patterns](https://en.wikipedia.org/wiki/Star_schema)

---

## 🔐 Quick Auth Test (Local)

### 1️⃣ Register a new user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo\",\"email\":\"demo@example.com\",\"password\":\"DemoPass123!\"}"
```

### 2️⃣ Login to get JWT token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username_or_email\":\"demo\",\"password\":\"DemoPass123!\"}"
```

### 3️⃣ Access protected endpoint (replace TOKEN with your JWT)
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/auth/me
```

### PowerShell equivalent:
```powershell
# 1️⃣ Register
Invoke-WebRequest -Uri "http://localhost:8000/auth/register" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"username":"demo","email":"demo@example.com","password":"DemoPass123!"}'

# 2️⃣ Login
$response = Invoke-WebRequest -Uri "http://localhost:8000/auth/login" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"username_or_email":"demo","password":"DemoPass123!"}'
$token = ($response.Content | ConvertFrom-Json).access_token

# 3️⃣ Get current user
Invoke-WebRequest -Uri "http://localhost:8000/auth/me" -Headers @{"Authorization"="Bearer $token"}
```

---

**🚀 Happy Coding!**
