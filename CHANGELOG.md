# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-XX

### Added

- Initial Python implementation of ctx-zip
- Core message compaction functionality
- Filesystem storage adapter
- Read and grep tools for retrieving persisted content
- Support for multiple boundary strategies:
  - `since-last-assistant-or-user-text` (default)
  - `entire-conversation`
  - `first-n-messages`
- Known keys tracking for security
- Both async and sync APIs
- Comprehensive test suite
- Full type hints and Protocol definitions
- Custom serialization support

### Architecture

- Clean separation between compaction logic, storage adapters, and tools
- Protocol-based adapter interface for easy extensibility
- Faithful translation of TypeScript patterns to Python idioms

### Coming Soon

- S3 storage adapter
- Blob storage adapters (Azure, GCS)
- Streaming support for large files
- Additional compaction strategies