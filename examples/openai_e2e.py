#!/usr/bin/env python3
"""
End-to-end example using OpenAI Chat Completions API with ctx-zip for tool result compaction.

Requirements:
    pip install openai ctxzip
    export OPENAI_API_KEY="your-key-here"
"""

import os
import json
import asyncio
from typing import List, Dict, Any
from openai import OpenAI

# Import ctx-zip
from ctxzip import compact_messages, CompactOptions
from ctxzip.tools import read_file, grep_and_search_file

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Define dummy tools that return large data
def get_sales_data(year: int, region: str) -> Dict[str, Any]:
    """Dummy tool that returns large sales data."""
    # Simulate large dataset
    data = {
        "year": year,
        "region": region,
        "summary": {
            "total_revenue": 5432100.50,
            "total_transactions": 8934,
            "avg_transaction": 608.23,
        },
        "monthly_breakdown": [
            {
                "month": f"2024-{i:02d}",
                "revenue": 450000 + (i * 12000),
                "transactions": 750 + (i * 23),
                "products": [
                    {
                        "id": f"PROD-{j:04d}",
                        "name": f"Product {j}",
                        "sales": 100 + (j * 10),
                        "revenue": 5000 + (j * 500),
                    }
                    for j in range(1, 51)  # 50 products per month
                ],
            }
            for i in range(1, 13)  # 12 months
        ],
        "customer_segments": {
            "enterprise": {"count": 234, "revenue": 2500000},
            "mid_market": {"count": 1456, "revenue": 1800000},
            "small_business": {"count": 7244, "revenue": 1132100.50},
        },
        "top_customers": [
            {
                "id": f"CUST-{i:05d}",
                "name": f"Customer {i}",
                "total_spent": 50000 - (i * 1000),
                "transactions": 45 - i,
                "metadata": {
                    "industry": ["tech", "finance", "retail", "healthcare"][i % 4],
                    "size": ["large", "medium", "small"][i % 3],
                    "notes": f"Important notes about customer {i}" * 10,
                },
            }
            for i in range(100)  # 100 top customers
        ],
    }
    return data


def analyze_customer_behavior(customer_id: str) -> Dict[str, Any]:
    """Dummy tool that returns customer behavior analysis."""
    return {
        "customer_id": customer_id,
        "analysis": {
            "purchase_patterns": {
                "frequency": "weekly",
                "avg_basket_size": 125.50,
                "preferred_categories": ["electronics", "software", "services"] * 20,
                "time_preferences": {
                    "day_of_week": ["Monday", "Wednesday", "Friday"],
                    "time_of_day": "morning",
                },
            },
            "engagement_metrics": {
                "email_open_rate": 0.65,
                "click_through_rate": 0.12,
                "campaign_responses": [
                    {"campaign_id": f"CAMP-{i}", "responded": i % 2 == 0, "converted": i % 3 == 0}
                    for i in range(500)  # 500 campaigns
                ],
            },
            "predictive_scores": {
                "churn_risk": 0.23,
                "upsell_probability": 0.78,
                "lifetime_value": 125000,
            },
            "interaction_history": [
                {
                    "date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                    "type": ["purchase", "support", "inquiry"][i % 3],
                    "details": f"Detailed interaction log entry {i}" * 5,
                }
                for i in range(1000)  # 1000 interactions
            ],
        },
    }


# Tool definitions for OpenAI
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_data",
            "description": "Get detailed sales data for a specific year and region",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "The year to get sales data for"},
                    "region": {
                        "type": "string",
                        "description": "The region (e.g., 'North America', 'Europe', 'Asia')",
                    },
                },
                "required": ["year", "region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_customer_behavior",
            "description": "Analyze customer behavior patterns and engagement",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer ID to analyze"}
                },
                "required": ["customer_id"],
            },
        },
    },
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a tool by name with given arguments."""
    tools = {
        "get_sales_data": get_sales_data,
        "analyze_customer_behavior": analyze_customer_behavior,
    }

    if tool_name in tools:
        return tools[tool_name](**arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def format_messages_for_openai(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert ctx-zip format messages to OpenAI format."""
    formatted = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role in ["system", "user"]:
            # Simple text messages
            formatted.append({"role": role, "content": content})

        elif role == "assistant":
            # Assistant messages might have tool_calls
            assistant_msg = {"role": role, "content": content}
            if "tool_calls" in msg:
                assistant_msg["tool_calls"] = msg["tool_calls"]
            formatted.append(assistant_msg)

        elif role == "tool":
            # Tool messages need special handling
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "tool-result":
                        tool_call_id = item.get("toolCallId", "default-id")
                        output = item.get("output", {})

                        # Extract the actual content
                        if isinstance(output, dict):
                            if output.get("type") == "text":
                                content_str = output.get("value", "")
                            elif output.get("type") == "json":
                                content_str = json.dumps(output.get("value", {}))
                            else:
                                content_str = str(output)
                        else:
                            content_str = str(output)

                        formatted.append(
                            {"role": "tool", "tool_call_id": tool_call_id, "content": content_str}
                        )

    return formatted


async def main():
    """Main example demonstrating ctx-zip with OpenAI."""
    print("🚀 Starting OpenAI + ctx-zip example\n")

    # Initialize conversation with a system message
    messages = [
        {
            "role": "system",
            "content": "You are a helpful business analyst. Use the available tools to gather data and provide insights.",
        },
        {
            "role": "user",
            "content": "Can you analyze our 2024 sales data for North America and also look at customer CUST-00001's behavior?",
        },
    ]

    print("📝 Initial request sent to OpenAI...")

    # Call OpenAI with tools
    response = client.chat.completions.create(
        model="gpt-4o", messages=messages, tools=TOOL_DEFINITIONS, tool_choice="auto"
    )

    assistant_message = response.choices[0].message

    # Add assistant's response to messages (must include tool_calls for OpenAI)
    assistant_msg_dict = {"role": "assistant", "content": assistant_message.content or ""}

    # Preserve tool_calls in the message
    if assistant_message.tool_calls:
        assistant_msg_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in assistant_message.tool_calls
        ]

    messages.append(assistant_msg_dict)

    # Process tool calls if any
    if assistant_message.tool_calls:
        print(f"\n🔧 Assistant requested {len(assistant_message.tool_calls)} tool calls:")

        for tool_call in assistant_message.tool_calls:
            print(f"  - {tool_call.function.name}")

            # Execute the tool
            arguments = json.loads(tool_call.function.arguments)
            result = execute_tool(tool_call.function.name, arguments)

            # Add tool result to messages (in ctx-zip format)
            messages.append(
                {
                    "role": "tool",
                    "content": [
                        {
                            "type": "tool-result",
                            "toolCallId": tool_call.id,
                            "toolName": tool_call.function.name,
                            "output": {"type": "json", "value": result},
                        }
                    ],
                }
            )

        # Add a temporary assistant message to enable compaction
        # (ctx-zip requires ending with assistant text message)
        messages.append(
            {"role": "assistant", "content": "I've received the data. Let me analyze it for you."}
        )

        # Print size before compaction
        original_size = len(json.dumps(messages))
        print(f"\n📊 Message history size BEFORE compaction: {original_size:,} bytes")

        # Apply ctx-zip compaction
        print("\n🗜️ Applying ctx-zip compaction...")
        compact_options = CompactOptions(
            storage="file:///tmp/openai-ctx-storage",
            boundary="entire-conversation",  # Compact all tool messages
            serialize_result=lambda v: json.dumps(v, indent=2),
        )

        messages = await compact_messages(messages, compact_options)

        # Print size after compaction
        compacted_size = len(json.dumps(messages))
        reduction_pct = ((original_size - compacted_size) / original_size) * 100
        print(f"📊 Message history size AFTER compaction: {compacted_size:,} bytes")
        print(f"✨ Size reduction: {reduction_pct:.1f}%")

        # Show what the tool results look like now
        print("\n📝 Compacted tool results:")
        for msg in messages:
            if msg.get("role") == "tool":
                for item in msg.get("content", []):
                    if item.get("type") == "tool-result":
                        output = item.get("output", {})
                        if output.get("type") == "text":
                            print(f"  - {output.get('value', '')[:100]}...")

        # Get final response from OpenAI with compacted messages
        print("\n🤖 Getting final response from OpenAI with compacted history...")

        # Convert messages to OpenAI format (the last assistant message is already there)
        openai_messages = format_messages_for_openai(messages)

        final_response = client.chat.completions.create(model="gpt-4o", messages=openai_messages)

        print("\n✅ Final assistant response:")
        print(final_response.choices[0].message.content)

        # Demonstrate reading back the stored data
        print("\n" + "=" * 60)
        print("📚 BONUS: Reading stored data back using ctx-zip tools")
        print("=" * 60)

        # Extract a storage key from the compacted messages
        storage_key = None
        for msg in messages:
            if msg.get("role") == "tool":
                for item in msg.get("content", []):
                    output = item.get("output", {})
                    if output.get("type") == "text" and "Key:" in output.get("value", ""):
                        # Extract key from "Key: xxx.txt" pattern
                        value = output.get("value", "")
                        key_start = value.find("Key:") + 4
                        # Find the end of the key (could be .txt, .json, or end with period/space)
                        remaining = value[key_start:].strip()
                        # Take everything up to the next period followed by space, or end of string
                        import re

                        key_match = re.match(r"([^\s]+\.txt|[^\s]+\.json|[^\s\.]+)", remaining)
                        if key_match:
                            storage_key = key_match.group(1)
                            print(f"  - Extracted key: {storage_key}")
                            break
                if storage_key:
                    break

        if storage_key:
            print(f"\n🔍 Found stored key: {storage_key}")

            # First, we need to register this key as known
            from ctxzip.storage import register_known_key

            register_known_key("file:///tmp/openai-ctx-storage", storage_key)

            # Read the file back
            from ctxzip.tools import ReadFileOptions

            read_options = ReadFileOptions(storage="file:///tmp/openai-ctx-storage")
            file_content = read_file(storage_key, read_options)

            print(f"\n📄 First 500 chars of stored content:")
            print(file_content["content"][:500] + "...")

            # Search for specific patterns
            from ctxzip.tools import GrepAndSearchFileOptions

            grep_options = GrepAndSearchFileOptions(storage="file:///tmp/openai-ctx-storage")
            search_results = grep_and_search_file(
                storage_key, pattern=r'"revenue":\s*\d+', options=grep_options
            )

            # Check if search was successful
            if "matches" in search_results:
                print(f"\n🔎 Found {len(search_results['matches'])} revenue entries:")
                for match in search_results["matches"][:3]:
                    print(f"  Line {match['line_number']}: {match['content'].strip()}")
            else:
                print(
                    f"\n⚠️ Could not search file: {search_results.get('content', 'Unknown error')}"
                )

    print("\n✨ Example complete!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
