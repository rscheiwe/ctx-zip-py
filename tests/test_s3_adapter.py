"""Tests for S3 storage adapter."""

import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from io import BytesIO

# Skip all tests if boto3 is not installed
pytest.importorskip("boto3")

from ctxzippy.adapters import StorageWriteParams, StorageReadParams
from ctxzippy.adapters.s3 import S3StorageAdapter, S3StorageOptions, s3_uri_to_options


class TestS3StorageAdapter:
    """Test suite for S3 storage adapter."""
    
    @patch("boto3.client")
    def test_init_with_bucket(self, mock_boto_client):
        """Test initializing adapter with bucket name."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        options = S3StorageOptions(bucket="test-bucket")
        adapter = S3StorageAdapter(options)
        
        assert adapter.bucket == "test-bucket"
        assert adapter.prefix == ""
        mock_s3.head_bucket.assert_called_once_with(Bucket="test-bucket")
    
    @patch("boto3.client")
    def test_init_with_prefix(self, mock_boto_client):
        """Test initializing adapter with bucket and prefix."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        options = S3StorageOptions(bucket="test-bucket", prefix="data/ctx")
        adapter = S3StorageAdapter(options)
        
        assert adapter.bucket == "test-bucket"
        assert adapter.prefix == "data/ctx"
    
    @patch("boto3.client")
    def test_init_with_credentials(self, mock_boto_client):
        """Test initializing adapter with explicit credentials."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        options = S3StorageOptions(
            bucket="test-bucket",
            region="us-west-2",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
        adapter = S3StorageAdapter(options)
        
        mock_boto_client.assert_called_once_with(
            service_name="s3",
            region_name="us-west-2",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
    
    @patch("boto3.client")
    def test_resolve_key(self, mock_boto_client):
        """Test key resolution with path safety."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Without prefix
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test"))
        assert adapter.resolve_key("file.txt") == "file.txt"
        assert adapter.resolve_key("path/to/file.txt") == "path/to/file.txt"
        
        # With prefix
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test", prefix="data"))
        assert adapter.resolve_key("file.txt") == "data/file.txt"
        assert adapter.resolve_key("sub/file.txt") == "data/sub/file.txt"
        
        # Path traversal attempts should be sanitized
        assert adapter.resolve_key("../file.txt") == "data/file.txt"
        assert adapter.resolve_key("../../file.txt") == "data/file.txt"
        assert adapter.resolve_key("/absolute/path") == "data/absolute/path"
    
    @patch("boto3.client")
    def test_write_text(self, mock_boto_client):
        """Test writing text content to S3."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket"))
        params = StorageWriteParams(
            key="test.txt",
            body="Hello, S3!",
            content_type="text/plain"
        )
        
        result = adapter.write(params)
        
        assert result.key == "test.txt"
        assert result.url == "s3://test-bucket/test.txt"
        
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test.txt",
            Body=b"Hello, S3!",
            ContentType="text/plain"
        )
    
    @patch("boto3.client")
    def test_write_bytes(self, mock_boto_client):
        """Test writing binary content to S3."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket", prefix="data"))
        binary_data = b"\x00\x01\x02\x03"
        params = StorageWriteParams(key="binary.dat", body=binary_data)
        
        result = adapter.write(params)
        
        assert result.key == "data/binary.dat"
        assert result.url == "s3://test-bucket/data/binary.dat"
        
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="data/binary.dat",
            Body=binary_data
        )
    
    @patch("boto3.client")
    def test_read_text(self, mock_boto_client):
        """Test reading text content from S3."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock the get_object response
        mock_response = {
            "Body": MagicMock(read=MagicMock(return_value=b"Hello from S3!"))
        }
        mock_s3.get_object.return_value = mock_response
        
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket"))
        content = adapter.read_text(StorageReadParams(key="test.txt"))
        
        assert content == "Hello from S3!"
        mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test.txt"
        )
    
    @patch("boto3.client")
    def test_read_nonexistent_key(self, mock_boto_client):
        """Test reading a key that doesn't exist."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock NoSuchKey exception
        mock_s3.exceptions.NoSuchKey = Exception
        mock_s3.get_object.side_effect = mock_s3.exceptions.NoSuchKey("Key not found")
        
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket"))
        
        with pytest.raises(FileNotFoundError, match="S3 key not found"):
            adapter.read_text(StorageReadParams(key="nonexistent.txt"))
    
    @patch("boto3.client")
    def test_open_read_stream(self, mock_boto_client):
        """Test opening a read stream from S3."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock streaming body
        mock_body = BytesIO(b"Streaming content")
        mock_response = {"Body": mock_body}
        mock_s3.get_object.return_value = mock_response
        
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket"))
        stream = adapter.open_read_stream(StorageReadParams(key="stream.txt"))
        
        assert stream == mock_body
        mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="stream.txt"
        )
    
    @patch("boto3.client")
    def test_string_representation(self, mock_boto_client):
        """Test the string representation of the adapter."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Without prefix
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket"))
        assert str(adapter) == "s3://test-bucket"
        
        # With prefix
        adapter = S3StorageAdapter(S3StorageOptions(bucket="test-bucket", prefix="data/ctx"))
        assert str(adapter) == "s3://test-bucket/data/ctx"


class TestS3UriParsing:
    """Test S3 URI parsing functions."""
    
    def test_parse_bucket_only(self):
        """Test parsing S3 URI with bucket only."""
        options = s3_uri_to_options("s3://my-bucket")
        assert options.bucket == "my-bucket"
        assert options.prefix is None
    
    def test_parse_with_prefix(self):
        """Test parsing S3 URI with prefix."""
        options = s3_uri_to_options("s3://my-bucket/path/to/data")
        assert options.bucket == "my-bucket"
        assert options.prefix == "path/to/data"
    
    def test_parse_with_trailing_slash(self):
        """Test parsing S3 URI with trailing slash."""
        options = s3_uri_to_options("s3://my-bucket/prefix/")
        assert options.bucket == "my-bucket"
        assert options.prefix == "prefix/"
    
    def test_invalid_scheme(self):
        """Test parsing URI with invalid scheme."""
        with pytest.raises(ValueError, match="Invalid S3 URI scheme"):
            s3_uri_to_options("http://bucket/path")
    
    def test_missing_bucket(self):
        """Test parsing S3 URI without bucket."""
        with pytest.raises(ValueError, match="No bucket specified"):
            s3_uri_to_options("s3://")


class TestS3Integration:
    """Integration tests with create_storage_adapter."""
    
    @patch("boto3.client")
    def test_create_from_uri(self, mock_boto_client):
        """Test creating S3 adapter from URI using resolver."""
        from ctxzippy.storage.resolver import create_storage_adapter
        
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        adapter = create_storage_adapter("s3://test-bucket/prefix")
        
        assert isinstance(adapter, S3StorageAdapter)
        assert adapter.bucket == "test-bucket"
        assert adapter.prefix == "prefix"
    
