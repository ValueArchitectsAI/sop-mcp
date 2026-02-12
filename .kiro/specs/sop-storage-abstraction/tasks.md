# Implementation Plan: SOP Storage Abstraction

## Overview

Introduce a storage abstraction layer for the SOP MCP Server. The implementation proceeds incrementally: define the protocol, implement the local filesystem backend with seeding, wire it into the server, add ephemeral warnings, update configuration, and update the README.

## Tasks

- [x] 1. Define the StorageBackend protocol
  - [x] 1.1 Create `src/utils/storage_backend.py` with the `StorageBackend` Protocol class
    - Define all abstract methods: `read_sop`, `write_sop`, `list_sops`, `list_versions`, `sop_exists`, `read_feedback`, `write_feedback`, `append_feedback`
    - Define the `is_ephemeral` property
    - Export from `src/utils/__init__.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [-] 2. Implement LocalFilesystemBackend
  - [x] 2.1 Create `src/utils/storage_local.py` with the `LocalFilesystemBackend` class
    - Implement `__init__` with `base_dir`, `is_ephemeral`, and `seed_dir` parameters
    - Implement all StorageBackend methods using `pathlib.Path` operations
    - Implement seeding logic: copy SOP files from `seed_dir` to `base_dir` when `base_dir` has no SOP subdirectories
    - Reuse `_parse_semver` and `_resolve_latest_path` logic from `sop_parser.py` for version sorting
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3_

  - [x] 2.2 Write property test: write-read round trip
    - **Property 1: Write-read round trip**
    - **Validates: Requirements 2.5, 2.6**

  - [x] 2.3 Write property test: listing reflects written SOPs
    - **Property 2: Listing reflects written SOPs**
    - **Validates: Requirements 2.3, 2.7**

  - [ ]* 2.4 Write property test: seeding copies all bundled SOPs
    - **Property 3: Seeding copies all bundled SOPs**
    - **Validates: Requirements 3.1, 3.3**

  - [x] 2.5 Write unit tests for LocalFilesystemBackend edge cases
    - Test: empty seed directory skips seeding (Requirement 3.2)
    - Test: missing seed directory skips seeding (Requirement 3.2)
    - Test: directory creation on init (Requirement 2.4)
    - Test: `sop_exists` returns correct boolean
    - Test: `read_sop` raises `FileNotFoundError` for missing SOP
    - Test: feedback read/write/append operations
    - _Requirements: 2.4, 3.2_

- [-] 3. Implement storage configuration and factory function
  - [x] 3.1 Add `get_storage_backend` factory function to `src/utils/storage_local.py`
    - Read `SOP_STORAGE_BACKEND` and `SOP_STORAGE_DIR` environment variables
    - Implement configuration resolution order: bundled → env var → platformdirs default
    - Validate configured path (reject empty strings, null bytes)
    - Define `BUNDLED_SOPS_DIR` constant pointing to `src/sops/`
    - Export from `src/utils/__init__.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 3.2 Write property test: path validation rejects invalid paths
    - **Property 5: Path validation rejects invalid paths**
    - **Validates: Requirements 5.4**

  - [x] 3.3 Write unit tests for configuration scenarios
    - Test: `SOP_STORAGE_DIR` env var sets the backend path (Requirement 5.1)
    - Test: no env vars defaults to platformdirs (Requirement 5.2)
    - Test: `SOP_STORAGE_BACKEND=bundled` uses bundled dir and marks ephemeral (Requirement 5.3)
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 4. Add `platformdirs` dependency
  - Add `platformdirs` to `[project.dependencies]` in `pyproject.toml`
  - Run `uv sync` to update lockfile
  - _Requirements: 2.2, 5.2_

- [x] 5. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate storage backend into the server
  - [x] 6.1 Refactor `src/utils/sop_parser.py` to accept an optional `base_dir` parameter
    - Add `base_dir: Path | None = None` to `SOP.__init__`; when provided, use it instead of `SOPS_DIR`
    - Keep `SOPS_DIR` as a fallback for backward compatibility
    - Keep all parsing logic unchanged
    - _Requirements: 6.2, 7.2_

  - [x] 6.2 Refactor `src/server.py` to use the storage backend
    - Import and call `get_storage_backend()` at module level
    - Replace all `SOPS_DIR` usage with backend method calls
    - Update `publish_sop` to use `backend.write_sop` and add ephemeral warning when `backend.is_ephemeral`
    - Update `submit_sop_feedback` to use `backend.append_feedback` and add ephemeral warning when `backend.is_ephemeral`
    - Update `explain_sop` to use `backend.list_sops`, `backend.list_versions`, and `backend.read_sop`
    - Update `register_sop_tools` to use the backend for SOP discovery
    - Update `_create_sop_handler` to use the backend for SOP resolution
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 6.3 Write property test: ephemeral warning iff ephemeral backend
    - **Property 4: Ephemeral warning if and only if ephemeral backend**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ]* 6.4 Write unit tests for server integration
    - Test: server tools use backend for reads and writes
    - Test: ephemeral warning present when backend is ephemeral
    - Test: ephemeral warning absent when backend is not ephemeral
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2_

- [x] 7. Update `src/utils/__init__.py` exports
  - Export `StorageBackend`, `LocalFilesystemBackend`, `get_storage_backend` from `src/utils/__init__.py`
  - Keep existing exports for backward compatibility
  - _Requirements: 7.1, 7.2_

- [x] 8. Update README documentation
  - Add "Storage Configuration" section after "Usage" covering:
    - Default behavior (platformdirs persistent directory, auto-seeding)
    - Environment variables table (`SOP_STORAGE_DIR`, `SOP_STORAGE_BACKEND`)
    - Example MCP client config with custom storage dir
    - Ephemeral storage note for `uvx` users
  - Update "How It Works" section to reflect configurable storage
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 9. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with minimum 100 iterations
- Unit tests use `pytest` with `tmp_path` for isolated filesystem operations
- All Python commands use `uv run` per project tooling requirements
