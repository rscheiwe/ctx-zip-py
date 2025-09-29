#!/usr/bin/env python3
"""
Example of using ctx-zip with AWS S3 storage.

Requirements:
    pip install ctxzippy[s3]
    
    Configure AWS credentials via one of:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - ~/.aws/credentials file
    - IAM role (if running on EC2/Lambda)
"""

import asyncio
import json
from typing import List, Dict, Any

from ctxzippy import compact_messages, CompactOptions
from ctxzippy.adapters import S3StorageAdapter, S3StorageOptions


async def example_with_s3_adapter():
    """Example using S3 adapter with explicit configuration."""
    
    # Create S3 adapter with configuration
    s3_adapter = S3StorageAdapter(
        S3StorageOptions(
            bucket="my-ctx-storage",  # Your S3 bucket
            prefix="sessions/2025-09",  # Optional path prefix
            region="us-west-2",  # Optional, uses default region if not specified
            # Credentials are optional - uses boto3's credential chain if not provided
            # aws_access_key_id="...",
            # aws_secret_access_key="...",
        )
    )
    
    # Create sample messages with large tool output
    messages = [
        {"role": "system", "content": "You are a data analyst assistant."},
        {"role": "user", "content": "Analyze our Q3 sales data"},
        {
            "role": "tool",
            "content": [
                {
                    "type": "tool-result",
                    "toolName": "get_sales_data",
                    "output": {
                        "type": "json",
                        "value": {
                            "quarter": "Q3-2025",
                            "total_revenue": 15234567.89,
                            "transactions": [
                                {
                                    "id": f"TXN-{i:05d}",
                                    "amount": 1000 * i,
                                    "product": f"Product-{i % 100}",
                                    "customer": f"Customer-{i % 500}",
                                    "metadata": {"notes": f"Transaction details for {i}" * 50}
                                }
                                for i in range(5000)  # 5000 transactions
                            ],
                            "summary": {
                                "by_product": {f"Product-{i}": i * 12345.67 for i in range(100)},
                                "by_region": {
                                    "North": 5000000,
                                    "South": 4000000,
                                    "East": 3234567.89,
                                    "West": 3000000
                                }
                            }
                        }
                    },
                }
            ],
        },
        {"role": "assistant", "content": "I've analyzed the Q3 sales data."},
    ]
    
    print("🚀 S3 Storage Example")
    print(f"📦 Using S3 bucket: {s3_adapter.bucket}")
    print(f"📁 With prefix: {s3_adapter.prefix or '(root)'}")
    
    # Calculate original size
    original_size = len(json.dumps(messages))
    print(f"\n📊 Original message size: {original_size:,} bytes")
    
    # Compact messages using S3 storage
    compacted = await compact_messages(
        messages,
        CompactOptions(
            storage=s3_adapter,
            boundary="entire-conversation"
        )
    )
    
    # Calculate compacted size
    compacted_size = len(json.dumps(compacted))
    reduction = ((original_size - compacted_size) / original_size) * 100
    print(f"📊 Compacted size: {compacted_size:,} bytes")
    print(f"✨ Reduction: {reduction:.1f}%")
    
    # Show the S3 reference
    tool_msg = compacted[2]
    if tool_msg["role"] == "tool":
        output = tool_msg["content"][0]["output"]
        print(f"\n🔗 S3 Reference:")
        print(f"   {output['value'][:200]}...")
    
    return compacted


async def example_with_s3_uri():
    """Example using S3 URI directly."""
    
    messages = [
        {"role": "user", "content": "Generate report"},
        {
            "role": "tool",
            "content": [
                {
                    "type": "tool-result",
                    "output": {
                        "type": "text",
                        "text": "Large report content " * 10000  # Large text output
                    }
                }
            ]
        },
        {"role": "assistant", "content": "Report generated."}
    ]
    
    print("\n🚀 S3 URI Example")
    
    # Use S3 URI directly - will use default AWS credentials
    compacted = await compact_messages(
        messages,
        CompactOptions(
            storage="s3://my-ctx-storage/reports/2025",  # S3 URI format
            boundary="entire-conversation"
        )
    )
    
    print("✅ Successfully compacted to S3 using URI format")
    return compacted


async def example_with_s3_compatible():
    """Example using S3-compatible service like MinIO or Wasabi."""
    
    # Configure for S3-compatible service
    s3_adapter = S3StorageAdapter(
        S3StorageOptions(
            bucket="ctx-storage",
            prefix="minio-data",
            endpoint_url="http://localhost:9000",  # MinIO endpoint
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )
    )
    
    messages = [
        {"role": "user", "content": "Process data"},
        {
            "role": "tool",
            "content": [
                {
                    "type": "tool-result",
                    "output": {"type": "json", "value": {"data": "test" * 1000}}
                }
            ]
        },
        {"role": "assistant", "content": "Processed."}
    ]
    
    print("\n🚀 S3-Compatible Service Example (MinIO)")
    
    compacted = await compact_messages(
        messages,
        CompactOptions(storage=s3_adapter)
    )
    
    print("✅ Successfully compacted to MinIO")
    return compacted


async def main():
    """Run S3 examples."""
    
    print("=" * 60)
    print("ctx-zip S3 Storage Examples")
    print("=" * 60)
    
    try:
        # Example 1: S3 with explicit adapter
        await example_with_s3_adapter()
    except Exception as e:
        print(f"⚠️  S3 adapter example failed: {e}")
        print("   Make sure you have configured AWS credentials and bucket exists")
    
    try:
        # Example 2: S3 with URI
        await example_with_s3_uri()
    except Exception as e:
        print(f"⚠️  S3 URI example failed: {e}")
    
    try:
        # Example 3: S3-compatible service
        await example_with_s3_compatible()
    except Exception as e:
        print(f"⚠️  S3-compatible example failed: {e}")
        print("   This example requires a local MinIO instance")
    
    print("\n" + "=" * 60)
    print("✨ Examples complete!")


if __name__ == "__main__":
    # Check if boto3 is installed
    try:
        import boto3
        asyncio.run(main())
    except ImportError:
        print("❌ boto3 is required for S3 storage")
        print("   Install with: pip install ctxzippy[s3]")