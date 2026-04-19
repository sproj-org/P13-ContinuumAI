# ContinuumAI Organization Onboarding (Concise)

## 1) What we need from the company

- Organization info: name, slug, description.
- Member list: username, email, role (`admin` or `standard`).
- Initial access credentials plan: temporary password per member and secure delivery channel.
- Data onboarding details:
  - Static snapshot or dynamic/continuously changing.
  - Source type (CSV/export/DB), refresh frequency, and owner contact.
  - DB connection details (if source is a DB): host, port, database, username, password/secret, SSL requirements.

## 2) Create organization in DB

Preferred: Admin API.

```bash
POST /api/admin/organizations
{
  "name": "Acme Retail",
  "slug": "acme-retail",
  "description": "Retail analytics client"
}
```

Equivalent SQL:

```sql
INSERT INTO organizations (name, slug, description, is_active)
VALUES ('Acme Retail', 'acme-retail', 'Retail analytics client', TRUE)
RETURNING id;
```

## 3) Add members to that organization

Use admin API so password hashing is handled by backend.

```bash
POST /api/admin/users
{
  "username": "acmeadmin",
  "email": "admin@acme.com",
  "password": "<TEMP_PASSWORD>",
  "organization_id": <ORG_ID>,
  "is_admin": true
}
```

Credentials needed for each member:
- Username
- Email
- Temporary password (minimum policy-compliant length)
- Role (`is_admin` true/false)

## 4) Grant dataset access for the org

```bash
POST /api/admin/organizations/<ORG_ID>/datasets
{
  "dataset_name": "silkroute",
  "display_name": "Acme Analytics"
}
```

## 5) Add their data to DB

### A) If data is static (one-time or occasional snapshots)

1. Take an immutable copy of the delivered data (raw snapshot archive).
2. Load into analytics tables using backend loader.
3. Generate profiles used by the app.


### B) If data is dynamic (frequently changing)

1. Set up recurring ingestion (hourly/daily as agreed).
2. Run scheduled refresh into tables.
3. Re-generate profiles after refresh so analytics stays aligned with latest data.
4. Add monitoring + failure alerting for ingestion jobs.

Minimum operational policy for dynamic data:
- Defined refresh SLA (for example: every 24h).
- Retry + alert on failed loads.
- Last-success timestamp and row-count sanity checks.

## 6) Quick validation after onboarding

- New member can log in: `POST /api/auth/login`.
- Member sees allowed datasets: `GET /api/datasets/available`.
- Org, users, and dataset mappings exist in DB (`organizations`, `users`, `organization_datasets`).
