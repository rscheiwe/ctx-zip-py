"""AWS S3 storage adapter for ctx-zip."""

import io
from typing import Optional, Any, BinaryIO
from urllib.parse import urlparse
from dataclasses import dataclass

from .base import (
    StorageAdapter,
    StorageWriteParams,
    StorageWriteResult,
    StorageReadParams,
)


@dataclass
class S3StorageOptions:
    """Configuration options for S3 storage adapter."""
    bucket: str
    prefix: Optional[str] = None
    region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services


class S3StorageAdapter:
    """AWS S3 storage adapter implementation."""
    
    def __init__(self, options: S3StorageOptions):
        """
        Initialize S3 storage adapter.
        
        Args:
            options: S3 configuration options
        """
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 storage. Install with: pip install ctxzippy[s3]"
            )
        
        self.bucket = options.bucket
        self.prefix = options.prefix or ""
        
        # Build boto3 client configuration
        client_kwargs = {"service_name": "s3"}
        if options.region:
            client_kwargs["region_name"] = options.region
        if options.endpoint_url:
            client_kwargs["endpoint_url"] = options.endpoint_url
        if options.aws_access_key_id and options.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = options.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = options.aws_secret_access_key
            if options.aws_session_token:
                client_kwargs["aws_session_token"] = options.aws_session_token
        
        self.s3_client = boto3.client(**client_kwargs)
        self._boto3 = boto3
        
        # Verify bucket exists and we have access
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except Exception as e:
            raise ValueError(f"Cannot access S3 bucket '{self.bucket}': {e}")
    
    def resolve_key(self, name: str) -> str:
        """
        Apply prefix and sanitize the key name.
        
        Args:
            name: The base key name
            
        Returns:
            The resolved S3 key with prefix applied
        """
        # Sanitize the key name - remove path traversal attempts
        safe_name = name.replace("\\", "/").lstrip("/")
        # Remove any ../ sequences
        while "../" in safe_name:
            safe_name = safe_name.replace("../", "")
        while "..\\" in safe_name:
            safe_name = safe_name.replace("..\\", "")
        
        if self.prefix:
            # Ensure prefix ends with / if it's not empty
            prefix = self.prefix.rstrip("/") + "/" if self.prefix else ""
            return f"{prefix}{safe_name}"
        return safe_name
    
    def write(self, params: StorageWriteParams) -> StorageWriteResult:
        """
        Write content to S3.
        
        Args:
            params: Write parameters including key and content
            
        Returns:
            Result with the S3 key and URL
        """
        resolved_key = self.resolve_key(params.key)
        
        # Convert body to bytes if it's a string
        if isinstance(params.body, str):
            body = params.body.encode("utf-8")
        else:
            body = params.body
        
        # Prepare put kwargs
        put_kwargs = {
            "Bucket": self.bucket,
            "Key": resolved_key,
            "Body": body,
        }
        
        if params.content_type:
            put_kwargs["ContentType"] = params.content_type
        
        # Upload to S3
        try:
            self.s3_client.put_object(**put_kwargs)
        except Exception as e:
            raise IOError(f"Failed to write to S3: {e}")
        
        # Construct the S3 URL (not a signed URL, just the canonical form)
        url = f"s3://{self.bucket}/{resolved_key}"
        
        return StorageWriteResult(key=resolved_key, url=url)
    
    def read_text(self, params: StorageReadParams) -> str:
        """
        Read text content from S3.
        
        Args:
            params: Read parameters including the key
            
        Returns:
            The text content of the S3 object
        """
        resolved_key = self.resolve_key(params.key)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=resolved_key
            )
            content = response["Body"].read()
            return content.decode("utf-8")
        except self.s3_client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 key not found: {resolved_key}")
        except Exception as e:
            raise IOError(f"Failed to read from S3: {e}")
    
    def open_read_stream(self, params: StorageReadParams) -> BinaryIO:
        """
        Open a readable stream for S3 content.
        
        Args:
            params: Read parameters including the key
            
        Returns:
            A file-like object for reading the S3 content
        """
        resolved_key = self.resolve_key(params.key)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=resolved_key
            )
            # Return the streaming body directly
            return response["Body"]
        except self.s3_client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 key not found: {resolved_key}")
        except Exception as e:
            raise IOError(f"Failed to open S3 stream: {e}")
    
    def __str__(self) -> str:
        """Return a human-readable identifier for this adapter."""
        if self.prefix:
            return f"s3://{self.bucket}/{self.prefix}"
        return f"s3://{self.bucket}"


def s3_uri_to_options(uri: str) -> S3StorageOptions:
    """
    Parse an S3 URI into storage options.
    
    Args:
        uri: S3 URI in the format s3://bucket/prefix
        
    Returns:
        S3StorageOptions with parsed bucket and prefix
        
    Examples:
        >>> s3_uri_to_options("s3://my-bucket")
        S3StorageOptions(bucket='my-bucket', prefix=None)
        
        >>> s3_uri_to_options("s3://my-bucket/path/to/prefix")
        S3StorageOptions(bucket='my-bucket', prefix='path/to/prefix')
    """
    parsed = urlparse(uri)
    
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI scheme: {uri}")
    
    bucket = parsed.netloc
    if not bucket:
        raise ValueError(f"No bucket specified in S3 URI: {uri}")
    
    # Get prefix from path, removing leading slash
    prefix = parsed.path.lstrip("/") if parsed.path else None
    
    return S3StorageOptions(bucket=bucket, prefix=prefix)