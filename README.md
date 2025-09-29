# ctx-zip Python

A Python library for compacting large tool-call results in conversation histories by persisting them to storage and replacing with lightweight references.

This is a Python implementation of the [ctx-zip TypeScript library](https://github.com/karthikscale3/ctx-zip), providing the same functionality for Python-based AI applications.

## Features

- **Automatic Compaction**: Replace large tool outputs with storage references
- **Flexible Boundaries**: Control which messages get compacted
- **Storage Adapters**: Pluggable storage backends (filesystem, S3, etc.)
- **Reader Tools**: Built-in tools to retrieve and search persisted content
- **Type Safety**: Full type hints and Protocol definitions
- **Async Support**: Both sync and async APIs available

## Installation

```bash
pip install ctxzip
```

For development:
```bash
pip install ctxzip[dev]
```

For S3 support (coming soon):
```bash
pip install ctxzip[s3]
```

## Quick Start

### Basic Example

```python
import asyncio
from ctxzip import compact_messages, CompactOptions

messages = [
    {"role": "user", "content": "Analyze this data"},
    {
        "role": "tool",
        "content": [{
            "type": "tool-result",
            "toolName": "analyze",
            "output": {
                "type": "json",
                "value": {"data": "..." * 10000}  # Large payload
            }
        }]
    },
    {"role": "assistant", "content": "Analysis complete"}
]

# Compact the messages
options = CompactOptions(
    storage="file:///tmp/ctx-storage",  # Or use a StorageAdapter instance
    boundary="since-last-assistant-or-user-text"
)

compacted = await compact_messages(messages, options)

# The tool result is now replaced with a reference:
# "Written to file: file:///tmp/ctx-storage/abc123.txt. Key: abc123.txt. Use the read/search tools to inspect its contents."
```

### Real-World Example with OpenAI

```python
import json
import asyncio
from openai import OpenAI
from ctxzip import compact_messages, CompactOptions

client = OpenAI()

async def process_with_tools():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Analyze our sales data"}
    ]
    
    # Call OpenAI with tools
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        tools=[{
            "type": "function",
            "function": {
                "name": "get_sales_data",
                "description": "Get sales data",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
    )
    
    # Add assistant response with tool calls
    messages.append({
        "role": "assistant",
        "content": response.choices[0].message.content,
        "tool_calls": [...]  # Include tool_calls from response
    })
    
    # Add tool results (simulate large response)
    large_sales_data = {"revenue": [{"month": i, "amount": 50000 * i} for i in range(1, 1000)]}
    messages.append({
        "role": "tool",
        "content": [{
            "type": "tool-result",
            "toolCallId": "call_123",
            "output": {"type": "json", "value": large_sales_data}
        }]
    })
    
    # Add assistant message to enable compaction
    messages.append({
        "role": "assistant",
        "content": "I've analyzed the sales data."
    })
    
    # Compact before sending back to OpenAI
    compacted = await compact_messages(
        messages,
        CompactOptions(storage="file:///tmp/llm-storage")
    )
    
    # Size reduction: ~500KB → ~1KB (99%+ reduction)
    # Continue conversation with compacted messages
    return compacted

# Run the example
asyncio.run(process_with_tools())
```

### Synchronous Usage

For non-async contexts, use the synchronous wrapper:

```python
from ctxzip import compact_messages_sync

compacted = compact_messages_sync(messages, options)
```

## Boundary Strategies

Control which messages get compacted:

### Since Last Assistant or User Text (Default)
Compact only tool results since the last conversational message:

```python
options = CompactOptions(boundary="since-last-assistant-or-user-text")
```

### Entire Conversation
Compact all tool results in the entire history:

```python
options = CompactOptions(boundary="entire-conversation")
```

### Keep First N Messages
Preserve system prompts and initial context:

```python
options = CompactOptions(
    boundary={"type": "first-n-messages", "count": 3}
)
```

## Storage Adapters

### Filesystem Adapter

Store files locally:

```python
from ctxzip.adapters import FileStorageAdapter

adapter = FileStorageAdapter(
    base_dir="/path/to/storage",
    prefix="session-123"  # Optional subdirectory
)

options = CompactOptions(storage=adapter)
```

### Creating Custom Adapters

Implement the `StorageAdapter` protocol:

```python
from ctxzip.adapters import StorageAdapter, StorageWriteParams, StorageWriteResult

class MyCustomAdapter:
    def write(self, params: StorageWriteParams) -> StorageWriteResult:
        # Persist params.body with params.key
        return StorageWriteResult(key=params.key, url="custom://...")
    
    def read_text(self, params: StorageReadParams) -> str:
        # Retrieve and return content
        pass
    
    def resolve_key(self, name: str) -> str:
        # Apply any prefixing/namespacing
        return f"prefix/{name}"
    
    def __str__(self) -> str:
        return "custom://my-storage"
```

## Reader Tools

Retrieve and search persisted content:

### Read File Tool

```python
from ctxzip.tools import read_file

# Read a previously stored file
result = read_file(
    key="abc123.txt",  # The key from "Key: abc123.txt"
    options=ReadFileOptions(storage="file:///tmp/ctx-storage")
)
print(result["content"])
```

### Grep and Search Tool

```python
from ctxzip.tools import grep_and_search_file

# Search for patterns in stored content
result = grep_and_search_file(
    key="data.json",
    pattern=r'"status":\s*"error"',
    flags="i",  # Case-insensitive
    options=GrepAndSearchFileOptions(storage="file:///tmp/ctx-storage")
)

for match in result["matches"]:
    print(f"{match['line_number']}: {match['content']}")
```

## Advanced Configuration

### Custom Serialization

Control how objects are converted to strings:

```python
import json

def custom_serializer(value):
    if isinstance(value, set):
        value = list(value)
    return json.dumps(value, indent=2, sort_keys=True)

options = CompactOptions(
    serialize_result=custom_serializer
)
```

### Storage Reader Tool Names

Specify which tools are readers (won't be re-persisted):

```python
options = CompactOptions(
    storage_reader_tool_names=[
        "readFile",
        "grepAndSearchFile", 
        "myCustomReaderTool"
    ]
)
```

## API Reference

### Core Functions

#### `compact_messages(messages, options) -> List[Message]`
Compact tool results in a message list by persisting to storage.

#### `CompactOptions`
Configuration for the compaction process:
- `strategy`: Compaction strategy (default: "write-tool-results-to-storage")
- `storage`: Storage destination (URI string or adapter instance)
- `boundary`: Where to start compacting from
- `serialize_result`: Custom serialization function
- `storage_reader_tool_names`: Tool names that read from storage

### Storage Adapters

#### `StorageAdapter` Protocol
- `write(params)`: Persist content
- `read_text(params)`: Retrieve text content
- `open_read_stream(params)`: Open a readable stream
- `resolve_key(name)`: Apply namespacing to keys
- `__str__()`: Human-readable identifier

#### `FileStorageAdapter`
Filesystem-based storage implementation.

### Reader Tools

#### `read_file(key, options)`
Read a previously stored file.

#### `grep_and_search_file(key, pattern, flags, options)`
Search for patterns in stored content.

## Testing

Run the test suite:

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# With coverage
pytest --cov=ctxzip
```

## Architecture

The library follows a clean separation of concerns:

1. **Compaction Logic** (`compact.py`): Message scanning and replacement
2. **Storage Adapters** (`adapters/`): Pluggable persistence backends
3. **Strategies** (`strategies/`): Different compaction approaches
4. **Tools** (`tools/`): Reader/search utilities
5. **Storage Utilities** (`storage/`): Key tracking, resolution, grep

This design makes it easy to:
- Add new storage backends
- Implement custom compaction strategies
- Extend with new reader tools
- Integrate with different AI frameworks

## Comparison with TypeScript Version

This Python implementation maintains full feature parity with the TypeScript original:

| Feature | TypeScript | Python |
|---------|------------|--------|
| Message Compaction | ✅ | ✅ |
| Boundary Strategies | ✅ | ✅ |
| Filesystem Adapter | ✅ | ✅ |
| Reader Tools | ✅ | ✅ |
| Key Tracking | ✅ | ✅ |
| Custom Serialization | ✅ | ✅ |
| Type Safety | ✅ | ✅ (via type hints) |
| Async Support | ✅ | ✅ |

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass
2. Code is formatted with `black`
3. Type hints are provided
4. New features include tests

## License

MIT License - see LICENSE file for details.

## Acknowledgments

This is a Python port of the excellent [ctx-zip](https://github.com/karthikscale3/ctx-zip) TypeScript library. The architecture and design patterns follow the original implementation while adapting to Python idioms.