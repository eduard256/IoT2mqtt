# How to Run REST API Endpoint Tests

## Quick Start

### Run All Working Tests (17 tests)
```bash
cd /home/dev/IoT2mqtt/web/backend
python3 -m pytest tests/test_rest_api_endpoints.py -k "Auth or Devices or Docker" -v
```

**Expected Result:** 17 passed ✅

### Run All REST API Tests (Including Failing)
```bash
python3 -m pytest tests/test_rest_api_endpoints.py -v
```

**Expected Result:** 18 passed, 10 failed, 12 errors

### Run Specific API Tests

#### Auth API Only (7 tests)
```bash
python3 -m pytest tests/test_rest_api_endpoints.py::TestAuthAPI -v
```

#### Devices API Only (4 tests)
```bash
python3 -m pytest tests/test_rest_api_endpoints.py::TestDevicesAPI -v
```

#### Docker API Only (6 tests)
```bash
python3 -m pytest tests/test_rest_api_endpoints.py::TestDockerAPI -v
```

### Run All Backend Tests
```bash
python3 -m pytest tests/ -v
```

**Expected Result:** 248 passed, 56 failed

## Test Coverage Report

### Generate HTML Coverage Report
```bash
python3 -m pytest tests/test_rest_api_endpoints.py --cov=api --cov-report=html
```

Then open `htmlcov/index.html` in browser.

### Generate Terminal Coverage Report
```bash
python3 -m pytest tests/test_rest_api_endpoints.py --cov=api --cov-report=term
```

## Detailed Test Results

### See Detailed Failures
```bash
python3 -m pytest tests/test_rest_api_endpoints.py -v --tb=short
```

### Run With Maximum Verbosity
```bash
python3 -m pytest tests/test_rest_api_endpoints.py -vvs
```

## Test Files

- **Main Test File**: `tests/test_rest_api_endpoints.py`
- **Summary Report**: `TEST_RESULTS_SUMMARY.md`
- **Quick Summary**: `REST_API_TESTS_SUMMARY.txt`

## What's Working

✅ **Authentication API** (7/7 tests)
- Login flow
- Token verification
- Password validation
- Error handling

✅ **Devices API** (4/4 tests)  
- Device listing
- Container status
- Authorization
- Empty states

✅ **Docker API** (6/6 tests)
- Container management
- Start/Stop/Restart operations
- Log retrieval
- Container deletion

## What's Not Working

❌ **Cameras API** (0/3) - Module import errors
❌ **Main Endpoints** (0/9) - Module import errors  
❌ **Integrations API** (1/5) - File system dependencies
❌ **Connectors API** (0/4) - Mocking issues
❌ **MQTT Discovery** (0/2) - Service initialization

## Requirements

```bash
# Install test dependencies
pip3 install -r requirements-test.txt

# Core dependencies
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==5.0.0
httpx==0.27.0
```

## Environment

- Python: 3.10.12
- Framework: FastAPI + pytest
- Test Client: FastAPI TestClient
- Mocking: unittest.mock

## Troubleshooting

### Issue: Permission denied connecting to Docker
**Solution**: Tests mock Docker service, this error is expected and doesn't affect results

### Issue: Module 'cameras' not found  
**Solution**: Some tests require cameras module. Use `-k` filter to skip them:
```bash
pytest tests/test_rest_api_endpoints.py -k "not Cameras and not Main" -v
```

### Issue: MQTT service not connected
**Solution**: Tests mock MQTT service. Use working test filter.

## Success Criteria

✅ All Auth API tests pass (7/7)
✅ All Devices API tests pass (4/4)
✅ All Docker API tests pass (6/6)
✅ No fake/bypassed test passes
✅ Real validation in all assertions

## Next Steps

To fix remaining tests:
1. Fix cameras module imports
2. Add file system mocking for Integrations
3. Properly mock MQTT service initialization
4. Improve connector discovery mocking

---
Last Updated: 2025-10-24
Test Suite Version: 1.0
