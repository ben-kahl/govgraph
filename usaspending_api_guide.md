# USAspending.gov API Quick Reference for GovGraph

## Overview

USAspending.gov API endpoints do not currently require any authorization, making it straightforward to integrate into your ETL pipeline.

**Base URL**: `https://api.usaspending.gov`

**API Version**: v2 (current)

**Authentication**: None required

**Rate Limiting**: Not officially documented, but be respectful with request frequency

---

## Key Endpoints for GovGraph

### 1. **Advanced Search - Primary Data Source**

#### `/api/v2/search/spending_by_award/` (POST)

This is your **main endpoint** for bulk contract data retrieval.

**Use Case**: Fetch contracts with filtering by date, agency, amount, vendor, etc.

**Request Example**:
```json
POST https://api.usaspending.gov/api/v2/search/spending_by_award/

{
  "filters": {
    "time_period": [
      {
        "start_date": "2023-01-01",
        "end_date": "2023-12-31"
      }
    ],
    "award_type_codes": ["A", "B", "C", "D"],  // Contract types
    "agencies": [
      {
        "type": "awarding",
        "tier": "toptier",
        "name": "Department of Defense"
      }
    ]
  },
  "fields": [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Awarding Agency",
    "Start Date",
    "End Date",
    "Award Type",
    "NAICS Code",
    "PSC Code",
    "Recipient UEI"
  ],
  "limit": 100,
  "page": 1
}
```

**Response Structure**:
```json
{
  "page_metadata": {
    "page": 1,
    "hasNext": true,
    "total": 25000
  },
  "results": [
    {
      "Award ID": "CONT_AWD_W911S023C0001_9700",
      "Recipient Name": "LOCKHEED MARTIN CORPORATION",
      "Award Amount": 125000000.00,
      "Awarding Agency": "Department of Defense",
      // ... more fields
    }
  ]
}
```

**Key Parameters**:
- `limit`: Max 100 per request (you'll need pagination)
- `award_type_codes`: 
  - `A`, `B`, `C`, `D`: Various contract types
  - `02`, `03`, `04`, `05`: Grant types
  - `06`, `07`, `08`: Loan types
- `filters.time_period`: Date range for awards

**Pagination Strategy**:
```python
page = 1
while True:
    response = fetch_awards(page=page, limit=100)
    if not response['page_metadata']['hasNext']:
        break
    page += 1
```

---

### 2. **Download Endpoint - Bulk Data**

#### `/api/v2/download/awards/` (POST)

For **large-scale data extraction** (better than paginating through thousands of requests).

**Use Case**: Download all contracts for a fiscal year as CSV.

**Request Example**:
```json
POST https://api.usaspending.gov/api/v2/download/awards/

{
  "filters": {
    "award_type_codes": ["A", "B", "C", "D"],
    "time_period": [
      {
        "start_date": "2023-10-01",
        "end_date": "2024-09-30"
      }
    ]
  },
  "columns": [],  // Empty = all columns
  "file_format": "csv"
}
```

**Response**:
```json
{
  "status_url": "https://api.usaspending.gov/api/v2/download/status/?file_name=...",
  "file_name": "...",
  "status": "generating"
}
```

**Download Flow**:
1. Submit POST request → get `status_url`
2. Poll `status_url` until `status: "finished"`
3. Download from `file_url` in response
4. Unzip and process CSV files

**Important**: Files can take 5-30 minutes to generate for large requests.

---

### 3. **Award Details**

#### `/api/v2/awards/<AWARD_ID>/` (GET)

**Use Case**: Get complete details for a specific award (useful for enriching data).

**Example**:
```
GET https://api.usaspending.gov/api/v2/awards/CONT_AWD_W911S023C0001_9700/
```

**Returns**:
- Full award description
- All transaction history
- Parent/child award relationships
- Federal account funding sources

---

### 4. **Transactions for an Award**

#### `/api/v2/transactions/` (POST)

**Use Case**: Get all modifications/amendments for a specific contract.

**Request**:
```json
POST https://api.usaspending.gov/api/v2/transactions/

{
  "award_id": "CONT_AWD_W911S023C0001_9700",
  "limit": 5000,
  "page": 1
}
```

**Use This To**:
- Track contract modifications over time
- Build `parent_contract_id` relationships in your schema
- Calculate total contract value with all amendments

---

### 5. **Recipient Search & Details**

#### `/api/v2/recipient/duns/<DUNS_OR_UEI>/` (GET)

**Use Case**: Get canonical vendor information for entity resolution.

**Example**:
```
GET https://api.usaspending.gov/api/v2/recipient/duns/006928857/
```

**Returns**:
- Legal business name
- DBA names (doing business as)
- UEI (Unique Entity Identifier)
- Parent/child company relationships
- All addresses

**Critical for**: Your LLM entity resolution pipeline—provides ground truth for major vendors.

---

### 6. **Agency Information**

#### `/api/v2/references/toptier_agencies/` (GET)

**Use Case**: Get the canonical list of federal agencies with codes.

**Returns**:
```json
[
  {
    "agency_id": 183,
    "toptier_code": "097",
    "abbreviation": "DOD",
    "agency_name": "Department of Defense"
  },
  // ...
]
```

**Use This**: Populate your `agencies` table with official data.

---

### 7. **Autocomplete Endpoints**

#### `/api/v2/autocomplete/recipient/` (POST)

**Use Case**: Search for vendor names (useful for manual verification in your entity resolution UI).

**Request**:
```json
POST https://api.usaspending.gov/api/v2/autocomplete/recipient/

{
  "search_text": "lockheed",
  "limit": 10
}
```

**Returns**: List of matching recipient names with UEIs.

---

## Award Type Codes Reference

```
Contracts:
  A = BPA Call (Blanket Purchase Agreement)
  B = Purchase Order
  C = Delivery Order
  D = Definitive Contract

IDVs (Indefinite Delivery Vehicles):
  IDV_A = GWAC (Government Wide Acquisition Contract)
  IDV_B = IDC (Indefinite Delivery Contract)
  IDV_B_A = FSS (Federal Supply Schedule)
  IDV_B_B = BOA (Basic Ordering Agreement)
  IDV_B_C = BPA (Blanket Purchase Agreement)
  IDV_C = IDC (Indefinite Delivery Contract)
  IDV_D = Definitive Contract
  IDV_E = Purchase Order

Grants:
  02 = Block Grant
  03 = Formula Grant  
  04 = Project Grant
  05 = Cooperative Agreement

Loans:
  06 = Direct Payment with Unrestricted Use
  07 = Direct Loan
  08 = Guaranteed/Insured Loan
```

---

## Recommended ETL Strategy for GovGraph

### Phase 1: Historical Backfill
```python
# Download 5 years of contract data
for fiscal_year in range(2020, 2025):
    download_request = {
        "filters": {
            "time_period": [{
                "start_date": f"{fiscal_year-1}-10-01",
                "end_date": f"{fiscal_year}-09-30"
            }],
            "award_type_codes": ["A", "B", "C", "D"]
        },
        "file_format": "csv"
    }
    
    # Submit and poll for file
    job = submit_download(download_request)
    file_url = poll_until_ready(job['status_url'])
    
    # Load into raw_contracts table
    load_csv_to_postgres(file_url, 'raw_contracts')
```

### Phase 2: Incremental Updates
```python
# Daily: Fetch new/modified contracts from last 7 days
filters = {
    "time_period": [{
        "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d")
    }],
    "award_type_codes": ["A", "B", "C", "D"]
}

# Use search endpoint for smaller, recent data
page = 1
while True:
    results = search_awards(filters, page=page, limit=100)
    load_to_postgres(results)
    if not results['page_metadata']['hasNext']:
        break
    page += 1
```

### Phase 3: Enrichment
```python
# For each unique recipient DUNS/UEI in raw data
for recipient_id in get_unique_recipients():
    try:
        details = fetch_recipient_details(recipient_id)
        # Use for entity resolution context
        enrich_vendor_record(recipient_id, details)
    except NotFound:
        # Mark for manual review or LLM resolution
        flag_for_resolution(recipient_id)
```

---

## Key Fields Mapping to Your Schema

### From USAspending → PostgreSQL `contracts` table

| USAspending Field | Your Field | Notes |
|-------------------|------------|-------|
| `Award ID` | `contract_id` | Natural key (string) |
| `Recipient UEI` | → lookup in `vendors` | Join key |
| `Awarding Agency` | → lookup in `agencies` | Join key |
| `Federal Action Obligation` | `obligated_amount` | Actual committed $$ |
| `Total Dollars Obligated` | `total_value` | Lifetime value |
| `Award Base Action Date` | `signed_date` | When signed |
| `Period of Performance Start Date` | `start_date` | Contract start |
| `Period of Performance Current End Date` | `current_end_date` | May change with mods |
| `NAICS Code` | `naics_code` | Industry |
| `Product or Service Code` | `psc_code` | What's being bought |
| `Award Type` | `award_type` | Contract, Grant, etc. |

### From USAspending → PostgreSQL `vendors` table

| USAspending Field | Your Field | Notes |
|-------------------|------------|-------|
| `Recipient Name` | `canonical_name` (after LLM) | Needs entity resolution |
| `Recipient Legal Business Name` | `legal_name` | Official name |
| `Recipient UEI` | `uei` | Unique Entity ID |
| `Recipient DUNS Number` | `duns` | Legacy ID |
| `Primary Place of Performance State` | `state` | Location |
| `Business Types` | `business_types` | Array of flags |

---

## Rate Limiting & Best Practices

1. **Use bulk download for historical data** - Don't paginate through 100k+ records
2. **Use search endpoint for recent/incremental** - Last 7-30 days of data
3. **Cache agency/recipient lookups** - Don't re-fetch the same agency info repeatedly
4. **Implement exponential backoff** - If you get 5xx errors
5. **Process CSVs in batches** - Don't load 1M rows at once into Postgres
6. **Use JSONB for raw_payload** - Store original API response for debugging

---

## Common Pitfalls

### 1. **Vendor Name Variations**
```
"LOCKHEED MARTIN CORPORATION"
"Lockheed Martin Corp"
"LOCKHEED MARTIN CORP."
"LOCKHEED-MARTIN CORPORATION"
```
→ This is why you need LLM entity resolution

### 2. **Award ID Format Changes**
- Natural IDs (strings): `CONT_AWD_W911S023C0001_9700` ✅ Use these
- Numeric IDs: `12345678` ❌ Deprecated

### 3. **Missing Subcontract Data**
USAspending has **limited subcontract visibility**. You'll need:
- FPDS (Federal Procurement Data System) for prime contracts ✅
- FSRS (FFATA Subaward Reporting System) for subs → requires separate integration

### 4. **Fiscal Year vs Calendar Year**
Federal fiscal year: October 1 - September 30
- FY 2024 = Oct 1, 2023 → Sep 30, 2024

---

## Testing Queries

**Get 10 recent DoD contracts**:
```bash
curl -X POST https://api.usaspending.gov/api/v2/search/spending_by_award/ \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "time_period": [{"start_date": "2024-01-01", "end_date": "2024-12-31"}],
      "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
      "award_type_codes": ["A", "B", "C", "D"]
    },
    "fields": ["Award ID", "Recipient Name", "Award Amount"],
    "limit": 10,
    "page": 1
  }'
```

**Check API status**:
```bash
curl https://api.usaspending.gov/api/v2/awards/last_updated/
```

---

## Additional Resources

- **Full API Docs**: https://api.usaspending.gov/docs/
- **Data Dictionary**: https://www.usaspending.gov/data-dictionary
- **Analyst Guide**: https://www.usaspending.gov/data-sources (FAQs)
- **GitHub Repo**: https://github.com/fedspendingtransparency/usaspending-api

---

## Next Steps for GovGraph

1. **Start with a small test**: Fetch 1,000 contracts from a single month
2. **Build raw ingestion**: Load into `raw_contracts` table
3. **Test entity resolution**: Try resolving vendor names with LLM
4. **Scale incrementally**: Once working, backfill 5 years of data
5. **Add subcontract data**: Integrate FSRS API later (separate effort)

The API is well-designed and reliable. Your main challenge will be entity resolution on messy vendor names, not API integration.