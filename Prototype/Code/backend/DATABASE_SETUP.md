# Railway MySQL Database Setup

## Current Database Status
✅ **Database is live on Railway**
- Host: `maglev.proxy.rlwy.net:56816`
- Database: `railway`
- Schema: Created with 9 tables
- Data: Imported (1,862 products, 793 customers, 5,009 transactions, etc.)

## For Team Members

### Step 1: Get Railway Credentials
Contact the project admin to get Railway MySQL credentials or be added as a team member on Railway.

### Step 2: Setup Environment Variables
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with Railway credentials:
   ```env
   DATABASE_URL=mysql+pymysql://root:PASSWORD@HOST.proxy.rlwy.net:PORT/railway
   DB_HOST=HOST.proxy.rlwy.net
   DB_PORT=PORT
   DB_USER=root
   DB_PASSWORD=PASSWORD
   DB_NAME=railway
   ```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Test Connection
```bash
python -c "import pymysql; from app.core.config import settings; conn = pymysql.connect(host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER, password=settings.DB_PASSWORD, database=settings.DB_NAME); print('✓ Connected!'); conn.close()"
```

### Step 5: Run Backend
```bash
.\start_server.ps1
# OR
uvicorn app.main:app --reload
```

## Database Schema

### Tables (9):
1. **Products** - Product catalog with categories
2. **Customers** - Customer information and segments
3. **Regions** - Geographic regions
4. **SalesReps** - Sales representatives
5. **SalesTransactions** - Sales transaction records
6. **Opportunities** - Sales opportunities/pipeline
7. **Users** - Application users (authentication)
8. **SalesSummary** - View for sales analytics
9. **OpportunitiesSummary** - View for opportunity analytics

## Database Scripts

### Schema Setup
- `database/schema.sql` - Original schema
- `database/fix_schema_railway.sql` - Railway-compatible schema
- `setup_railway_db.py` - Automated schema creation script

### Data Import
- `database/full_etl_pipeline.py` - Generate CSV data from source
- `import_to_railway.py` - Import processed CSVs to Railway

### Running ETL (if needed)
```bash
# Generate processed data
python database/full_etl_pipeline.py

# Import to Railway
python import_to_railway.py
```

## Connecting from MySQL Client

```bash
mysql -h maglev.proxy.rlwy.net -P 56816 -u root -p railway
# Enter password when prompted
```

## Using Railway CLI

```bash
# Install
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# Connect to MySQL
railway connect MySQL
```

## Important Notes

⚠️ **Security:**
- Never commit `.env` file with real credentials
- Keep Railway credentials secure
- Use environment variables for all sensitive data

⚠️ **Railway Free Tier Limits:**
- Connection limits may apply
- Database storage limits
- Shared resources

⚠️ **Data Persistence:**
- Railway MySQL data persists across deploys
- Backup important data regularly
- Use Railway snapshots for backups

## Troubleshooting

### Connection Timeout
```bash
# Add connection timeout in code
connect_timeout=30
```

### Missing cryptography package
```bash
pip install cryptography
```

### Date format issues
- CSVs use MM/DD/YYYY format
- Database expects YYYY-MM-DD format
- Import script handles conversion automatically

## Support
For Railway-specific issues, check:
- Railway Dashboard: https://railway.app
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
