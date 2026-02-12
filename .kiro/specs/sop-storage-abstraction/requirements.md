# Requirements Document

## Introduction

The SOP MCP Server currently stores SOP files in a bundled `src/sops/` directory, which is resolved relative to the package source. When the server is installed via `uvx`, this directory lives inside an ephemeral cache and any writes (publish, feedback) are lost on cache refresh. This feature introduces a storage abstraction layer that decouples SOP read/write operations from the physical storage location, supports configurable storage directories, warns users about ephemeral storage, and is designed to accommodate future backends such as S3.

## Glossary

- **Storage_Backend**: An abstract interface defining the operations required to read, write, list, and manage SOP files regardless of the underlying storage mechanism.
- **Local_Filesystem_Backend**: A concrete implementation of Storage_Backend that stores SOP files on the local filesystem at a configurable directory path.
- **Bundled_Directory**: The `src/sops/` directory shipped inside the Python package, which contains default/seed SOP files. This directory is ephemeral when the package is installed via `uvx`.
- **Persistent_Directory**: A durable directory on the local filesystem (defaulting to a platform-appropriate user data directory via `platformdirs`) where SOP files are stored across sessions.
- **Ephemeral_Storage**: Storage that may be lost when the package cache is refreshed, specifically the Bundled_Directory when running via `uvx`.
- **Storage_Configuration**: The set of options that determine which Storage_Backend is used and how it is configured (e.g., directory path, backend type).
- **Seeding**: The process of copying default SOP files from the Bundled_Directory into the Persistent_Directory on first run or when the Persistent_Directory is empty.

## Requirements

### Requirement 1: Storage Backend Interface

**User Story:** As a developer, I want a well-defined storage interface, so that SOP operations are decoupled from the underlying storage mechanism and new backends can be added in the future.

#### Acceptance Criteria

1. THE Storage_Backend SHALL define abstract methods for reading an SOP file by name and version
2. THE Storage_Backend SHALL define abstract methods for writing an SOP file with content, name, and version
3. THE Storage_Backend SHALL define an abstract method for listing all available SOP names
4. THE Storage_Backend SHALL define an abstract method for listing all versions of a given SOP
5. THE Storage_Backend SHALL define an abstract method for checking whether a specific SOP version exists
6. THE Storage_Backend SHALL define a property or method that indicates whether the backend storage is ephemeral

### Requirement 2: Local Filesystem Backend

**User Story:** As a user, I want SOP files stored on my local filesystem in a durable location, so that published SOPs and feedback persist across server restarts and package updates.

#### Acceptance Criteria

1. THE Local_Filesystem_Backend SHALL implement all methods defined by the Storage_Backend interface
2. WHEN no storage path is configured, THE Local_Filesystem_Backend SHALL default to a platform-appropriate user data directory determined by `platformdirs`
3. WHEN a storage path is explicitly configured, THE Local_Filesystem_Backend SHALL use the configured path for all SOP file operations
4. THE Local_Filesystem_Backend SHALL create the storage directory if the directory does not exist when the backend is initialized
5. WHEN reading an SOP file, THE Local_Filesystem_Backend SHALL return the file content as a string
6. WHEN writing an SOP file, THE Local_Filesystem_Backend SHALL write the content to a versioned file within the SOP's subdirectory
7. WHEN listing SOP names, THE Local_Filesystem_Backend SHALL return the names of all subdirectories containing versioned SOP files

### Requirement 3: Bundled Directory Seeding

**User Story:** As a user, I want the default SOPs shipped with the package to be available in my persistent storage on first run, so that I have a working set of SOPs without manual setup.

#### Acceptance Criteria

1. WHEN the Persistent_Directory contains no SOP subdirectories, THE Local_Filesystem_Backend SHALL copy all SOP files from the Bundled_Directory into the Persistent_Directory
2. WHEN the Bundled_Directory does not exist or is empty, THE Local_Filesystem_Backend SHALL skip seeding and operate with an empty storage
3. WHEN seeding completes, THE Local_Filesystem_Backend SHALL make all seeded SOPs available through the standard listing and reading methods

### Requirement 4: Ephemeral Storage Warning

**User Story:** As a user, I want to be warned when publishing SOPs to ephemeral storage, so that I understand my changes may be lost.

#### Acceptance Criteria

1. WHEN the active Storage_Backend reports that storage is ephemeral, THE publish_sop tool SHALL include a warning in its response indicating that the published SOP is stored in ephemeral storage and may be lost
2. WHEN the active Storage_Backend reports that storage is ephemeral, THE submit_sop_feedback tool SHALL include a warning in its response indicating that the feedback is stored in ephemeral storage and may be lost
3. WHEN the active Storage_Backend reports that storage is not ephemeral, THE publish_sop tool SHALL omit the ephemeral warning from its response
4. WHEN the active Storage_Backend reports that storage is not ephemeral, THE submit_sop_feedback tool SHALL omit the ephemeral warning from its response

### Requirement 5: Storage Configuration

**User Story:** As a user, I want to configure where my SOPs are stored, so that I can choose a location that fits my workflow and infrastructure.

#### Acceptance Criteria

1. WHEN the `SOP_STORAGE_DIR` environment variable is set, THE Storage_Configuration SHALL use its value as the storage directory path for the Local_Filesystem_Backend
2. WHEN neither the `SOP_STORAGE_DIR` environment variable nor any other configuration is provided, THE Storage_Configuration SHALL default to the `platformdirs` user data directory
3. WHEN the `SOP_STORAGE_BACKEND` environment variable is set to "bundled", THE Storage_Configuration SHALL use the Bundled_Directory directly as the storage location and mark storage as ephemeral
4. THE Storage_Configuration SHALL validate that the configured storage directory path is a valid filesystem path

### Requirement 6: Server Integration

**User Story:** As a developer, I want the storage abstraction integrated into the existing MCP server, so that all SOP tools use the configured storage backend transparently.

#### Acceptance Criteria

1. WHEN the server starts, THE server SHALL initialize the Storage_Backend based on the active Storage_Configuration
2. THE server SHALL pass the initialized Storage_Backend to all SOP tool handlers that perform read or write operations
3. WHEN the Storage_Backend is changed in configuration, THE SOP tool handlers SHALL use the new backend without code changes to the tool handlers themselves
4. THE server SHALL use the Storage_Backend for dynamic tool registration, reading SOP metadata from the configured storage location

### Requirement 7: Backward Compatibility

**User Story:** As an existing user, I want the server to work without any configuration changes, so that upgrading does not break my current workflow.

#### Acceptance Criteria

1. WHEN no storage configuration is provided, THE server SHALL operate using the Local_Filesystem_Backend with the default `platformdirs` directory and seed from the Bundled_Directory
2. WHEN the `SOP_STORAGE_BACKEND` environment variable is set to "bundled", THE server SHALL behave identically to the current implementation by reading and writing directly to the Bundled_Directory
