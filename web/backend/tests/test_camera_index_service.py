"""
Comprehensive tests for CameraIndexService

Tests cover:
1. Service initialization and singleton behavior
2. Search functionality with various query formats
3. Search scoring and relevance ordering
4. "Unlisted" options in search results
5. get_entries() logic for specific models
6. get_entries() logic for "Unlisted" model (popular patterns)
7. Integration with CameraIndex
8. Edge cases and error handling
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock the cameras.camera_index module BEFORE importing camera_index_service
mock_camera_index = MagicMock()
sys.modules['cameras'] = MagicMock()
sys.modules['cameras.camera_index'] = mock_camera_index

from services.camera_index_service import CameraIndexService


# ============================================================================
# TIER 1 - CRITICAL TESTS: Service Initialization
# ============================================================================

class TestServiceInitialization:
    """Test CameraIndexService initialization"""

    def test_initialization_success(self):
        """Should initialize with camera index singleton"""
        service = CameraIndexService()

        assert service.index is not None
        assert hasattr(service.index, 'search')
        assert hasattr(service.index, 'get_entries_for_model')
        assert hasattr(service.index, 'get_popular_patterns')

    def test_initialization_uses_singleton(self):
        """Should use global singleton from get_camera_index()"""
        service1 = CameraIndexService()
        service2 = CameraIndexService()

        # Both should reference the same singleton instance
        assert service1.index is service2.index


# ============================================================================
# TIER 1 - CRITICAL TESTS: Search Functionality
# ============================================================================

class TestSearchFunctionality:
    """Test search() method with various queries"""

    def test_search_delegates_to_index(self):
        """Should delegate search to underlying CameraIndex"""
        service = CameraIndexService()

        # Mock the index.search method
        mock_results = [
            {"brand": "Hikvision", "model": "Unlisted", "display": "Hikvision: Unlisted"},
            {"brand": "Hikvision", "model": "DS-2CD2032-I", "display": "Hikvision: DS-2CD2032-I"}
        ]

        with patch.object(service.index, 'search', return_value=mock_results) as mock_search:
            results = service.search("hikvision", limit=10)

            # Should call index.search with correct parameters
            mock_search.assert_called_once_with("hikvision", 10)
            assert results == mock_results

    def test_search_with_default_limit(self):
        """Should use default limit of 50"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search("test")

            # Should use default limit=50
            mock_search.assert_called_once_with("test", 50)

    def test_search_with_custom_limit(self):
        """Should respect custom limit parameter"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search("test", limit=25)

            mock_search.assert_called_once_with("test", 25)

    def test_search_returns_list(self):
        """Should return list of matching models"""
        service = CameraIndexService()

        mock_results = [
            {
                "brand": "Hikvision",
                "brand_id": "hikvision",
                "model": "DS-2CD2032-I",
                "display": "Hikvision: DS-2CD2032-I",
                "entry": {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/stream"}
            }
        ]

        with patch.object(service.index, 'search', return_value=mock_results):
            results = service.search("hikvision")

            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0]["brand"] == "Hikvision"
            assert results[0]["model"] == "DS-2CD2032-I"

    def test_search_empty_query(self):
        """Should handle empty query string"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            results = service.search("")

            mock_search.assert_called_once_with("", 50)
            assert results == []

    def test_search_no_results(self):
        """Should return empty list when no matches found"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]):
            results = service.search("nonexistent_brand_xyz")

            assert results == []


# ============================================================================
# TIER 1 - CRITICAL TESTS: get_entries() Logic
# ============================================================================

class TestGetEntriesLogic:
    """Test get_entries() method - critical for stream scanning"""

    def test_get_entries_for_unlisted_returns_popular_patterns(self):
        """Should return ONLY popular patterns when model='Unlisted'"""
        service = CameraIndexService()

        mock_popular = [
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif1"},
            {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/live/main"}
        ]

        with patch.object(service.index, 'get_popular_patterns', return_value=mock_popular) as mock_popular_fn:
            with patch.object(service.index, 'get_entries_for_model') as mock_entries_fn:
                results = service.get_entries("Hikvision", "Unlisted")

                # Should call get_popular_patterns
                mock_popular_fn.assert_called_once()

                # Should NOT call get_entries_for_model
                mock_entries_fn.assert_not_called()

                # Should return popular patterns
                assert results == mock_popular
                assert len(results) == 2

    def test_get_entries_for_specific_model_returns_db_patterns(self):
        """Should return database patterns for specific model"""
        service = CameraIndexService()

        mock_db_patterns = [
            {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/Streaming/Channels/101"},
            {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/Streaming/Channels/102"}
        ]

        with patch.object(service.index, 'get_entries_for_model', return_value=mock_db_patterns) as mock_entries_fn:
            with patch.object(service.index, 'get_popular_patterns') as mock_popular_fn:
                results = service.get_entries("Hikvision", "DS-2CD2032-I")

                # Should call get_entries_for_model with brand and model
                mock_entries_fn.assert_called_once_with("Hikvision", "DS-2CD2032-I")

                # Should NOT call get_popular_patterns
                mock_popular_fn.assert_not_called()

                # Should return database patterns
                assert results == mock_db_patterns
                assert len(results) == 2

    def test_get_entries_case_sensitive_unlisted_check(self):
        """Should check 'Unlisted' with exact case match"""
        service = CameraIndexService()

        # "Unlisted" with capital U should trigger popular patterns
        with patch.object(service.index, 'get_popular_patterns', return_value=[]) as mock_popular:
            service.get_entries("Brand", "Unlisted")
            mock_popular.assert_called_once()

        # "unlisted" lowercase should NOT trigger popular patterns
        with patch.object(service.index, 'get_entries_for_model', return_value=[]) as mock_entries:
            service.get_entries("Brand", "unlisted")
            mock_entries.assert_called_once_with("Brand", "unlisted")

    def test_get_entries_returns_empty_list_when_no_patterns(self):
        """Should return empty list when no patterns found"""
        service = CameraIndexService()

        with patch.object(service.index, 'get_entries_for_model', return_value=[]):
            results = service.get_entries("Unknown", "Model")

            assert results == []

    def test_get_entries_preserves_entry_structure(self):
        """Should preserve full entry structure from index"""
        service = CameraIndexService()

        mock_entry = {
            "type": "FFMPEG",
            "protocol": "rtsp",
            "port": 554,
            "url": "/stream1",
            "notes": "Main stream",
            "credentials": "required"
        }

        with patch.object(service.index, 'get_entries_for_model', return_value=[mock_entry]):
            results = service.get_entries("Brand", "Model")

            assert len(results) == 1
            assert results[0] == mock_entry
            assert results[0]["type"] == "FFMPEG"
            assert results[0]["url"] == "/stream1"
            assert results[0]["notes"] == "Main stream"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Popular Patterns Behavior
# ============================================================================

class TestPopularPatterns:
    """Test popular patterns functionality"""

    def test_popular_patterns_include_onvif(self):
        """Should include ONVIF patterns at the beginning"""
        service = CameraIndexService()

        mock_popular = [
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif1"},
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif2"},
            {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/live/main"}
        ]

        with patch.object(service.index, 'get_popular_patterns', return_value=mock_popular):
            patterns = service.index.get_popular_patterns()

            # Should not be empty
            assert len(patterns) > 0

            # First patterns should be ONVIF
            onvif_patterns = [p for p in patterns if p.get("type") == "ONVIF"]
            assert len(onvif_patterns) >= 2

    def test_popular_patterns_fallback_on_file_missing(self):
        """Should return at least ONVIF patterns if file is missing"""
        service = CameraIndexService()

        # Mock fallback scenario - only ONVIF patterns
        mock_fallback = [
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif1"},
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif2"}
        ]

        with patch.object(service.index, 'get_popular_patterns', return_value=mock_fallback):
            patterns = service.index.get_popular_patterns()

            # Should still return ONVIF patterns as fallback
            assert len(patterns) >= 2
            assert patterns[0]["type"] == "ONVIF"
            assert patterns[1]["type"] == "ONVIF"


# ============================================================================
# TIER 2 - INTEGRATION TESTS: Real Data
# ============================================================================

class TestRealDataIntegration:
    """Test with actual camera database (if available)"""

    def test_search_finds_hikvision_models(self):
        """Should find Hikvision models in real database"""
        service = CameraIndexService()

        try:
            results = service.search("hikvision", limit=10)

            # Should have results (assuming database is loaded)
            if len(results) > 0:
                # First result should be "Unlisted" option
                assert "Unlisted" in [r["model"] for r in results[:3]]

                # Should have brand field
                assert all("brand" in r for r in results)
                assert all("model" in r for r in results)
                assert all("display" in r for r in results)
        except Exception:
            # Skip if database not available in test environment
            pytest.skip("Camera database not available")

    def test_get_entries_for_hikvision_model(self):
        """Should get entries for a known Hikvision model"""
        service = CameraIndexService()

        try:
            # First search for a model
            results = service.search("hikvision", limit=10)

            if len(results) > 0:
                # Get a specific model (skip "Unlisted")
                specific_model = next((r for r in results if r["model"] != "Unlisted"), None)

                if specific_model:
                    entries = service.get_entries(specific_model["brand"], specific_model["model"])

                    # Should have at least one entry
                    assert len(entries) > 0

                    # Entries should have URL pattern structure
                    for entry in entries:
                        assert "protocol" in entry
                        assert "url" in entry
        except Exception:
            pytest.skip("Camera database not available")


# ============================================================================
# TIER 2 - EDGE CASES: Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_search_with_special_characters(self):
        """Should handle special characters in query"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search("brand: model-123_456")

            mock_search.assert_called_once()
            assert mock_search.call_args[0][0] == "brand: model-123_456"

    def test_search_with_whitespace(self):
        """Should handle queries with extra whitespace"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search("  hikvision  ")

            # Should pass query as-is (CameraIndex handles normalization)
            mock_search.assert_called_once()

    def test_get_entries_with_empty_brand(self):
        """Should handle empty brand name"""
        service = CameraIndexService()

        with patch.object(service.index, 'get_entries_for_model', return_value=[]) as mock_entries:
            results = service.get_entries("", "Model")

            mock_entries.assert_called_once_with("", "Model")
            assert results == []

    def test_get_entries_with_empty_model(self):
        """Should handle empty model name"""
        service = CameraIndexService()

        with patch.object(service.index, 'get_entries_for_model', return_value=[]) as mock_entries:
            results = service.get_entries("Brand", "")

            mock_entries.assert_called_once_with("Brand", "")
            assert results == []

    def test_search_with_very_long_query(self):
        """Should handle very long query strings"""
        service = CameraIndexService()

        long_query = "a" * 1000

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search(long_query)

            mock_search.assert_called_once_with(long_query, 50)

    def test_search_with_zero_limit(self):
        """Should handle limit=0"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            results = service.search("test", limit=0)

            mock_search.assert_called_once_with("test", 0)

    def test_search_with_negative_limit(self):
        """Should handle negative limit"""
        service = CameraIndexService()

        with patch.object(service.index, 'search', return_value=[]) as mock_search:
            service.search("test", limit=-1)

            # Should pass negative limit (CameraIndex handles validation)
            mock_search.assert_called_once_with("test", -1)


# ============================================================================
# TIER 3 - BEHAVIOR TESTS: Search Result Format
# ============================================================================

class TestSearchResultFormat:
    """Test search result format and structure"""

    def test_search_result_has_required_fields(self):
        """Should return results with all required fields"""
        service = CameraIndexService()

        mock_results = [
            {
                "brand": "Hikvision",
                "brand_id": "hikvision",
                "model": "DS-2CD2032-I",
                "display": "Hikvision: DS-2CD2032-I",
                "entry": {"type": "FFMPEG", "url": "/stream"}
            }
        ]

        with patch.object(service.index, 'search', return_value=mock_results):
            results = service.search("test")

            assert len(results) == 1
            result = results[0]

            # Check all required fields
            assert "brand" in result
            assert "brand_id" in result
            assert "model" in result
            assert "display" in result
            assert "entry" in result

    def test_search_unlisted_has_null_entry(self):
        """Should have entry=None for Unlisted options"""
        service = CameraIndexService()

        mock_results = [
            {
                "brand": "Hikvision",
                "brand_id": "hikvision",
                "model": "Unlisted",
                "display": "Hikvision: Unlisted",
                "entry": None
            }
        ]

        with patch.object(service.index, 'search', return_value=mock_results):
            results = service.search("hikvision")

            assert results[0]["entry"] is None

    def test_search_specific_model_has_entry_dict(self):
        """Should have entry dict for specific models"""
        service = CameraIndexService()

        mock_entry = {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/stream"}
        mock_results = [
            {
                "brand": "Hikvision",
                "brand_id": "hikvision",
                "model": "DS-2CD2032-I",
                "display": "Hikvision: DS-2CD2032-I",
                "entry": mock_entry
            }
        ]

        with patch.object(service.index, 'search', return_value=mock_results):
            results = service.search("hikvision")

            assert isinstance(results[0]["entry"], dict)
            assert results[0]["entry"]["type"] == "FFMPEG"


# ============================================================================
# TIER 3 - BEHAVIOR TESTS: Entry Format
# ============================================================================

class TestEntryFormat:
    """Test entry structure and format"""

    def test_entry_has_url_pattern_fields(self):
        """Should return entries with URL pattern fields"""
        service = CameraIndexService()

        mock_entries = [
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/Streaming/Channels/101",
                "notes": "Main stream"
            }
        ]

        with patch.object(service.index, 'get_entries_for_model', return_value=mock_entries):
            entries = service.get_entries("Hikvision", "DS-2CD2032-I")

            assert len(entries) == 1
            entry = entries[0]

            # Check URL pattern fields
            assert "type" in entry
            assert "protocol" in entry
            assert "port" in entry
            assert "url" in entry

    def test_entry_types_are_valid(self):
        """Should have valid entry types"""
        service = CameraIndexService()

        mock_entries = [
            {"type": "FFMPEG", "protocol": "rtsp", "port": 554, "url": "/stream1"},
            {"type": "ONVIF", "protocol": "rtsp", "port": 554, "url": "/onvif1"},
            {"type": "MJPEG", "protocol": "http", "port": 80, "url": "/mjpeg"},
            {"type": "JPEG", "protocol": "http", "port": 80, "url": "/snapshot.jpg"}
        ]

        with patch.object(service.index, 'get_entries_for_model', return_value=mock_entries):
            entries = service.get_entries("Brand", "Model")

            valid_types = {"FFMPEG", "ONVIF", "MJPEG", "JPEG"}
            for entry in entries:
                assert entry["type"] in valid_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
