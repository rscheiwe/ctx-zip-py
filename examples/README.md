# ctx-zip Examples

This directory contains examples demonstrating how to use ctx-zip with various LLM frameworks.

## Setup

Install the requirements for running examples:

```bash
cd examples
pip install -r requirements.txt
```

## Examples

### OpenAI End-to-End (`openai_e2e.py`)

A comprehensive example showing ctx-zip integration with OpenAI's Chat Completions API including tool calls.

**Features demonstrated:**
- Tool calling with large responses
- Message compaction (99%+ size reduction)
- Reading stored data back
- Searching stored content with grep

**Run it:**
```bash
export OPENAI_API_KEY="your-key-here"
python openai_e2e.py
```

### More Examples Coming Soon

- Anthropic Claude integration
- LangChain integration
- Streaming responses
- Custom storage adapters
- Batch processing