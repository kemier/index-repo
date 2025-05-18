# Build Tools Guide

## Overview

This document provides information about the build and development tools used in this project, focusing on environment setup and dependency management.

## Development Environment Setup

### Prerequisites

The following tools are required for development:

- **Python 3.7+** - For running analysis scripts
- **Clang/LLVM** - For C++ code analysis
- **Neo4j** - For storing and querying code relationships
- **Graphviz** - For rendering visualizations
- **Docker** (optional) - For running Neo4j in a container

### Installing Clang/LLVM

Clang and libclang are required for analyzing C++ code:

- **Linux**: Install using your package manager:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install clang libclang-dev

  # Fedora/RHEL
  sudo dnf install clang clang-devel
  ```

- **Windows**: Install using LLVM installer from https://releases.llvm.org/
  1. Download the latest stable release
  2. Run the installer and follow the instructions
  3. Make sure to add LLVM to your system PATH

- **macOS**: Install using Homebrew:
  ```bash
  brew install llvm
  ```

The Python bindings for libclang will be installed via pip when installing the dependencies.

### Setting up Neo4j

For graph visualizations and advanced queries:

1. The easiest way is to use the included Docker Compose configuration:
   ```bash
   docker-compose up -d
   ```
   This starts Neo4j with these settings:
   - Web interface: http://localhost:7475
   - Bolt connection: bolt://localhost:7688
   - Default credentials: neo4j/password

2. Alternatively, you can install Neo4j Desktop from https://neo4j.com/download/ and set environment variables:
   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

### Installing Graphviz

Graphviz is required for visualization functionality:

- **Windows**: Download from https://graphviz.org/download/
  - Add the bin directory to your PATH environment variable

- **macOS**:
  ```bash
  brew install graphviz
  ```

- **Linux**:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install graphviz

  # Fedora/RHEL
  sudo dnf install graphviz
  ```

## Virtual Environment Management with UV

[UV](https://github.com/astral-sh/uv) is a fast Python package installer and resolver that is recommended for managing virtual environments.

### Installing UV

```bash
# On Windows
pip install uv

# On macOS/Linux
pip install --user uv
```

### Creating a Virtual Environment

```bash
# Create a new virtual environment
uv venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### Installing Dependencies

```bash
# Install dependencies from requirements.txt
uv pip install -r requirements.txt
```

### Adding New Dependencies

```bash
# Add a new dependency
uv pip install package_name
```

## Consolidated Tools

### Batch Files

The `bin` directory contains consolidated batch files for common operations:

- `analysis_tool.bat` - Handles code analysis operations
- `cleanup_tool.bat` - Manages cleanup tasks
- `setup_env.bat` - Sets up the development environment
- `manage_venv.bat` - Manages the Python virtual environment

### Python Scripts

The `scripts` directory contains consolidated Python scripts:

- `clang_utils.py` - Consolidated Clang utilities

### Test and Analysis Scripts

The `test_scripts` directory contains various tools and tests:

- `visualization_tools.py` - Consolidated visualization functionality
- `indexing_tools.py` - Consolidated indexing functionality

## Using the Consolidated Tools

### Visualization Tools

The visualization tools have been consolidated into a single module:

```bash
python test_scripts/visualization_tools.py --type <visualization_type> [options]
```

Available visualization types:
- `logger_functions` - Visualize Logger-related functions
- `logger_callgraph` - Visualize Logger call graphs
- `hash64_callgraph` - Visualize Hash64 call graphs
- And more...

For more details, see `visualization_guide.md`.

### Indexing Tools

The indexing tools have been consolidated into a single module:

```bash
python test_scripts/indexing_tools.py <command> [options]
```

Available commands:
- `index` - Index a file or directory
- `index-incremental` - Incrementally index a directory
- `index-folly` - Index the Folly codebase
- `clear` - Clear project data from Neo4j

## Docker-based Development Environment

Docker Compose is provided for simplified setup of the development environment:

```bash
# Start Neo4j container
docker-compose up -d
```

This will create:
- A Neo4j database container with the appropriate ports exposed
- Persistent storage for the database in the `neo4j` directory

To stop the containers:

```bash
docker-compose down
```

## Troubleshooting

### Missing libclang

If you encounter errors related to missing libclang:

1. Make sure Clang/LLVM is installed correctly
2. Find the path to libclang.dll, libclang.so, or libclang.dylib
3. Set the LIBCLANG_PATH environment variable:
   ```bash
   # Windows
   set LIBCLANG_PATH=C:\Program Files\LLVM\bin

   # macOS/Linux
   export LIBCLANG_PATH=/usr/lib/llvm/lib
   ```

### Neo4j Connection Issues

If you can't connect to Neo4j:

1. Check that the Docker container is running: `docker-compose ps`
2. Verify ports are correctly exposed: `docker-compose logs neo4j`
3. Check the Neo4j configuration in your scripts

### Graphviz Errors

If visualization fails due to Graphviz errors:

1. Ensure Graphviz is correctly installed
2. Verify the `dot` command is in your PATH: `which dot` or `where dot`
3. Check that output directories exist and are writable

## References

- [Clang/LLVM Documentation](https://clang.llvm.org/docs/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Graphviz Documentation](https://graphviz.org/documentation/)
- [Docker Documentation](https://docs.docker.com/)
- [UV Documentation](https://github.com/astral-sh/uv) 