# 🔍 Camera Search Logic Documentation

## Overview

The camera search system supports intelligent, multi-strategy searching across 73,000+ camera models from 3,600+ brands.

---

## Supported Query Formats

### 1. **Brand Only**
```
Query: "trassir"
Result: All Trassir camera models
```

### 2. **Model Only**
```
Query: "2141"
Result: All cameras with model containing "2141" (across all brands)
```

### 3. **Brand + Model (Colon Separator)**
```
Query: "trassir: 2141"
Result: Only Trassir cameras with model containing "2141"
```

### 4. **Brand + Model (Space Separator)**
```
Query: "trassir 2141"
Result: Cameras where display contains both "trassir" AND "2141"
```

### 5. **Brand with Empty Model**
```
Query: "trassir:"
Result: All Trassir camera models (same as brand only)
```

### 6. **Multi-word Brands**
```
Query: "255 ip cam"
Result: All models from brand "255 Ip Cam"
```

### 7. **Multi-word Brand + Model**
```
Query: "255 ip cam: 255"
Result: Models from "255 Ip Cam" containing "255"
```

### 8. **Brands with Dashes**
```
Query: "d-link"
Query: "tp-link: c200"
Result: Handles brands like D-Link, TP-Link correctly
```

---

## Scoring System

Results are ranked by relevance using a scoring algorithm (0-100):

### Without Colon (`:`)

| Match Type | Score | Example |
|------------|-------|---------|
| Exact display match | 100 | Query "trassir: 2141" = Display "Trassir: 2141" |
| Exact brand match | 90 | Query "trassir" = Brand "Trassir" |
| Exact model match | 80 | Query "2141" = Model "2141" |
| Brand starts with query | 70 | Query "hikv" matches "Hikvision" |
| Model starts with query | 60 | Query "ds-2" matches "DS-2CD2142FWD-I" |
| Brand contains query | 50 | Query "link" matches "D-Link" |
| Model contains query | 40 | Query "2cd" matches "DS-2CD2142FWD-I" |
| Multi-token match | 35 | Query "trassir 2141" (both tokens in display) |
| Display contains query | 30 | Query found anywhere in display |

### With Colon (`:`)

Strict filtering mode:
- Brand must contain the text before `:`
- Model must contain the text after `:` (if provided)
- Scoring based on exact/starts-with/contains for each part

---

## Features

### ✅ Case-Insensitive
```
"HIKVISION" = "hikvision" = "Hikvision"
```

### ✅ Whitespace Tolerant
```
"   trassir   " → automatically trimmed
```

### ✅ Deduplication
Only unique camera models are returned (no duplicate displays).

### ✅ "Unlisted" Option
For each brand found, an "Unlisted" option is automatically prepended for unknown models.

### ✅ Relevance Sorting
Results are sorted by score (highest first), so most relevant matches appear at the top.

---

## Edge Cases Covered

| Scenario | Query | Behavior |
|----------|-------|----------|
| Empty query | `""` | Returns empty array |
| Brand with spaces | `"255 ip cam"` | Correctly identifies as single brand |
| Brand + model (space) | `"trassir 2141"` | Multi-token search finds matches |
| Brand + model (colon) | `"trassir: 2141"` | Strict filter mode |
| Only colon | `"trassir:"` | All models of brand |
| Partial matches | `"hikv"` | Finds "Hikvision" |
| Brands with dashes | `"tp-link"` | Handles correctly |
| Multi-word search | `"hikvision ds-2cd"` | Token-based matching |
| Non-existent model | `"brand: xyz999"` | Returns only "Unlisted" option |

---

## Implementation Details

**File:** `/home/eduard/IoT2mqtt/connectors/cameras/camera_index.py`

**Method:** `CameraIndex.search(query: str, limit: int = 50)`

**Algorithm:**
1. Normalize query (lowercase, trim)
2. Detect colon separator
3. If colon present: strict brand+model filtering
4. If no colon: multi-strategy scoring
5. Sort by score (descending)
6. Deduplicate by display
7. Apply limit
8. Add "Unlisted" options for found brands
9. Return results

---

## Testing

Run the test suite:
```bash
cd /home/eduard/IoT2mqtt/connectors/cameras
python3 test_search.py
```

**Test Coverage:**
- ✅ Brand only search
- ✅ Model only search
- ✅ Brand + model (colon)
- ✅ Brand + model (space)
- ✅ Multi-word brands
- ✅ Brands with dashes
- ✅ Case variations
- ✅ Partial matches
- ✅ Whitespace handling
- ✅ Empty model (brand:)

---

## Performance

- **Database Size:** 73,691 models across 3,628 brands
- **Search Time:** O(n) linear scan with early termination at limit
- **Memory:** All models loaded in RAM (~50MB)
- **Typical Response:** <100ms for 50 results

---

## Future Improvements

Potential optimizations:
- [ ] Fuzzy matching (Levenshtein distance)
- [ ] Trigram indexing for faster partial matches
- [ ] Caching of frequent queries
- [ ] Full-text search with Elasticsearch/PostgreSQL FTS
- [ ] Weighted scoring based on popularity
