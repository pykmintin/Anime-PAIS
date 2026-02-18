# NDIS Export Package

**Generated:** 2026-02-17  
**Total Receipts:** 171  
**Export File:** NDIS_EXPORT_20260217_204633.tar.gz (19 MB)

---

## Contents

### 1. pending.csv
- **Rows:** 171 (plus header)
- **Columns:** file_hash, filename, filepath, date_raw, amount_raw, merchant_raw, merchant_normalized, category, description, status, confidence
- **Date Range:** 13 May 2025 - 29 Jan 2026
- **Amount Range:** -$5.30 to -$434.00
- **Confidence:** 95% average

### 2. Renamed Receipt Images
All files renamed to format: `YYYY-MM-DD_Merchant_Amount.jpg`

**Examples:**
- `2025-11-10_Reddy-express-Shell-Reddy-Expr_-$9.00.jpg`
- `2025-12-22_Grill-em_-$15.17.jpg`
- `2025-10-06_Aldi-Mobile_-$25.00.jpg`

---

## Data Quality

- ✅ **171/171** receipts processed
- ✅ **0** failed
- ✅ **0** duplicates
- ✅ **100%** OCR success rate
- ✅ **95%** average confidence

---

## Usage

### View in Excel/LibreOffice:
```bash
libreoffice --calc pending.csv
```

### Extract images by date:
```bash
# All receipts from November 2025
ls Screenshots/2025-11-*.jpg
```

### Calculate total expenses:
```bash
python3 -c "
import csv
total = 0
count = 0
with open('pending.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        amount = row['amount_raw'].replace('$', '').replace('-', '')
        total += float(amount)
        count += 1
print(f'Total: ${total:.2f} across {count} receipts')
"
```

---

## Notes

- All receipts are in "pending" status (awaiting confirmation)
- Categories are all set to "Other" (can be updated in GUI)
- File paths in CSV reference Screenshots/ directory
- Original screenshot files have been renamed to date format

---

## Next Steps

1. Open GUI to review and categorize receipts
2. Confirm transactions to move to completed.csv
3. Export final report for NDIS submission
