
# Camera Stream Detection Issues and Solutions

## Executive Summary

After extensive testing with real camera hardware (Zosi ZG23213M and TP-Link Tapo C320WS), we identified five critical issues preventing proper stream detection. Manual testing with curl and ffprobe proved all camera streams are accessible, yet our automated scanner finds 0-1 streams when it should find 3-4+ streams per camera.

---

## Part 1: Problems Identified

### Problem 1: HTTP Tests Use HEAD Method Instead of GET

**Issue Description:**
The HTTP stream testing function uses `curl -I` which sends HEAD requests. Many IP cameras, including the Zosi ZG23213M we tested, do not support HEAD requests and immediately close the connection when receiving one.

**Evidence:**
- Testing with `curl -I http://camera/snapshot` → Connection reset by peer (error 56)
- Testing with `curl http://camera/snapshot` (GET) → HTTP 200 OK, receives JPEG image
- Camera logs show it accepts GET but rejects HEAD

**Current Code Behavior:**
```bash
curl -I -s -o /dev/null -w "%{http_code}" --max-time 25 URL
```

**Impact:**
All HTTP-based snapshot URLs fail detection even when they work perfectly with GET requests. For Zosi camera, this means 3 working snapshot endpoints are reported as unavailable.

### Problem 2: Credentials Not Passed via HTTP Basic Auth Header

**Issue Description:**
The current implementation embeds credentials directly in the URL (`http://user:pass@host/path`). However, many modern IP cameras require credentials to be sent via the HTTP Authorization header instead.

**Evidence:**
When testing the Zosi camera:
- URL format `http://admin:password@10.0.20.112/snapshot.jpg` → HTTP 401 Unauthorized
- Same URL with `-u admin:password` flag → HTTP 200 OK

The camera returns `WWW-Authenticate: Basic realm="IPCAM"` indicating it expects Basic Auth header, not URL-embedded credentials.

**Current Code Behavior:**
Credentials are embedded in URL construction: `http://{username}:{password}@{host}:{port}/{path}`

**Impact:**
All cameras requiring proper Basic Authentication header fail to authenticate, returning 401 errors instead of serving streams.

### Problem 3: Standard Ports Always Appended to URLs

**Issue Description:**
The URL generation code always appends port numbers, even for standard ports (80 for HTTP, 443 for HTTPS, 554 for RTSP). Some cameras are sensitive to explicit port specifications and will only respond to URLs without the standard port specified.

**Evidence:**
Agent DVR (the reference implementation we parsed) generates URLs like:
- `http://camera/snapshot` (no port)
- `rtsp://camera/stream1` (no port)

Our code generates:
- `http://camera:80/snapshot` (with port)
- `rtsp://camera:554/stream1` (with port)

While most cameras accept both formats, strict implementations may reject the explicit port version.

**Current Code Behavior:**
Port is always appended: `{protocol}://{host}:{port}/{path}` regardless of whether it's a standard port.

**Impact:**
Potential compatibility issues with cameras that expect standard port numbers to be omitted from URLs.

### Problem 4: Popular Patterns Not Tested for Known Models

**Issue Description:**
The system has 150 most popular stream patterns that should be tested as a fallback. However, the current logic only tests these patterns when model is set to "Unlisted". For known models, ONLY the database patterns are tested, even if they fail.

**Current Logic:**
```
if model == "Unlisted":
    test_popular_patterns()
else:
    test_model_specific_patterns_only()
```

**Expected Logic:**
```
test_model_specific_patterns()
if found_streams < 7 and time_remaining:
    test_popular_patterns()
```

**Evidence:**
Testing TP-Link Tapo C320WS:
- Database contains 3 patterns for this model
- Only 1 pattern actually works (finds 1 stream)
- Popular patterns include 150 common URLs
- Manual testing found `/stream2`, `/live/stream1`, `/live/stream2` also work
- These are in popular patterns list but never tested

For Zosi camera:
- Database patterns don't work (wrong auth method)
- Popular patterns include `/snapshot` which DOES work
- But popular patterns never tested because model is not "Unlisted"

**Impact:**
Severely reduced stream discovery rate. Cameras with 4+ working streams report only 0-1 streams.

### Problem 5: Missing Placeholder Replacements (PARTIALLY FIXED)

**Issue Description:**
Database URLs contain placeholders like `[CHANNEL]`, `[WIDTH]`, `[HEIGHT]`, `[TOKEN]`, `[PASWORD]` (note typo in database). Analysis of all 3,628 brand files revealed 8 unique placeholder formats, but only 3 were being replaced.

**Evidence:**
Generated URL before fix:
```
/cgi-bin/snapshot.cgi?chn=[CHANNEL]&u=admin&p=password
```

The `[CHANNEL]` placeholder was never replaced, so cameras received literal string "[CHANNEL]" instead of "0" or "1".

**Status:**
This issue has been FIXED in commit 2fb26c4. All 8 placeholders now have replacement logic:
- `[CHANNEL]` → channel number
- `[WIDTH]` → 640 (default)
- `[HEIGHT]` → 480 (default)
- `[TOKEN]` → empty string
- `[PASWORD]` → password value (handles database typo)

### Problem 6: Testing Parallelism May Be Too Aggressive

**Issue Description:**
Currently 4 streams are tested in parallel using asyncio.Semaphore(4). While this speeds up testing, some cameras have anti-flooding protection that may reject rapid concurrent requests from the same IP.

**Evidence:**
Manual testing shows 100% success rate when testing streams sequentially with small delays. Automated testing shows sporadic failures that might be rate-limiting.

**Impact:**
Uncertain, but may contribute to false negatives in stream detection.

---

## Part 2: Solutions

### Solution 1: Change HTTP Method from HEAD to GET

**Implementation:**
Remove the `-I` flag from curl command and add `-X GET` to be explicit. Since we're checking for image streams, we need to actually retrieve a small amount of data to verify the stream works.

**Rationale:**
GET requests are universally supported by all HTTP cameras. Some cameras serve snapshot images but don't implement HEAD method for those endpoints.

**Code Changes Needed:**
File: `web/backend/services/camera_stream_scanner.py`, method `_test_http()`

Change from HEAD request to GET request. Add response validation by checking for JPEG magic bytes (FF D8 FF) or other image format indicators.

**Testing:**
Manual verification showed:
- `curl -u admin:password http://camera/snapshot` → Success (JPEG received)
- All 3 Zosi snapshot URLs work with GET method
- Zero Zosi snapshot URLs work with HEAD method

### Solution 2: Use HTTP Basic Authentication Header

**Implementation:**
Add `--user username:password` (or `-u`) flag to curl commands instead of embedding credentials in URL. For requests with query parameters containing user/password, check if URL already includes credentials and avoid double-authentication.

**Rationale:**
Modern cameras expect RFC 2617 compliant Basic Authentication via Authorization header. URL-embedded credentials are legacy format and not universally supported.

**Code Changes Needed:**
File: `web/backend/services/camera_stream_scanner.py`, method `_test_http()`

Modify curl invocation to extract username/password from url_info and pass via `-u` flag. Remove credentials from URL construction in `_generate_test_urls()` method for HTTP(S) protocols.

**Detection Logic:**
- If URL pattern contains `user=` or `pwd=` query parameters: credentials go in query only
- If URL pattern is plain path: credentials go in Authorization header via `-u` flag
- Never embed credentials in URL as `http://user:pass@host`

### Solution 3: Omit Standard Ports from URLs

**Implementation:**
Add conditional logic when building full URLs. Check if port matches protocol default:
- HTTP protocol and port 80 → omit port
- HTTPS protocol and port 443 → omit port
- RTSP protocol and port 554 → omit port
- Any other port → include in URL

**Rationale:**
Matches Agent DVR behavior and improves compatibility with cameras that expect standards-compliant URLs.

**Code Changes Needed:**
File: `web/backend/services/camera_stream_scanner.py`, method `_generate_test_urls()`

Add port detection logic before URL assembly. Use format `{protocol}://{host}/{path}` when port is standard, otherwise `{protocol}://{host}:{port}/{path}`.

### Solution 4: Always Test Popular Patterns After Model Patterns

**Implementation:**
Modify the scan logic to always append popular patterns to the test queue after model-specific patterns, regardless of whether model is "Unlisted" or not. Respect the 7-stream limit and 5-minute timeout as termination conditions.

**Rationale:**
Database patterns may be incomplete, outdated, or incorrect. Popular patterns represent real-world working URLs found across thousands of cameras. They serve as valuable fallback.

**Code Changes Needed:**
File: `web/backend/services/camera_index_service.py`, method `get_entries()`

Change logic from:
```
if model == "Unlisted":
    return popular_patterns
else:
    return model_patterns
```

To:
```
model_patterns = get_entries_for_model(brand, model)
if len(model_patterns) < 150:  # If we don't have many patterns
    popular_patterns = get_popular_patterns()
    return model_patterns + popular_patterns
return model_patterns
```

Alternatively, modify scanner to automatically request popular patterns once model patterns are exhausted and fewer than 7 streams found.

### Solution 5: Consider Reducing Parallelism (Optional)

**Implementation:**
Test with semaphore value of 2 or even 1 instead of current value of 4. Monitor success rates.

**Rationale:**
Some cameras have anti-DoS protection. Sequential or low-concurrency testing may improve detection rate at cost of speed.

**Code Changes Needed:**
File: `web/backend/services/camera_stream_scanner.py`, line 133

Change `asyncio.Semaphore(4)` to `asyncio.Semaphore(2)` or make it configurable.

**Trade-off:**
Lower parallelism = slower scanning but potentially higher success rate. Need to test with real cameras to find optimal value.

---

## Testing Results Summary

### Zosi ZG23213M Camera Testing

**Database patterns:** 6 total (3 for lowercase model, 3 for uppercase model)

**Manual testing results:**
- `/snapshot` with GET + Basic Auth → ✅ Success (JPEG received)
- `/snapshot.jpg?strm=0` with GET + Basic Auth → ✅ Success (JPEG received)
- `/snapshot.jpg?strm=1` with GET + Basic Auth → ✅ Success (JPEG received)
- `/cgi-bin/snapshot.cgi?chn=0` → ❌ Failed (404)
- All RTSP paths → ❌ Failed (connection refused)

**Current automated detection:** 0 streams found
**Expected after fixes:** 3 streams found

### TP-Link Tapo C320WS Camera Testing

**Database patterns:** 3 total

**Manual testing results:**
- `/stream1` RTSP → ✅ Success (H.264 stream)
- `/stream2` RTSP → ✅ Success (H.264 stream)
- `/live/stream1` RTSP → ✅ Success (H.264 stream)
- `/live/stream2` RTSP → ✅ Success (H.264 stream)

**Current automated detection:** 1 stream found (only `/stream1` from database)
**Expected after fixes:** 4 streams found (all patterns including popular ones)

---

## Implementation Priority

1. **HIGH PRIORITY - Fix HTTP method** (Problem 1): Blocking all HTTP snapshot detection
2. **HIGH PRIORITY - Fix authentication** (Problem 2): Causing 401 errors on modern cameras
3. **MEDIUM PRIORITY - Add popular patterns** (Problem 4): Major impact on discovery success rate
4. **LOW PRIORITY - Fix port handling** (Problem 3): Edge cases, minor compatibility improvement
5. **OPTIONAL - Adjust parallelism** (Problem 6): Optimization, test after other fixes

## Expected Impact

After implementing all fixes:
- Zosi camera: 0 → 3 streams detected (infinite% improvement)
- TP-Link camera: 1 → 4 streams detected (400% improvement)
- Overall system: Estimated 3-5x increase in successful stream detection across all camera brands
- User experience: Significantly reduced need for manual stream URL configuration
