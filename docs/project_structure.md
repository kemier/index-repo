# Project Structure and Organization

## Directory Structure

This document explains the organization of the repository and how to use the modular architecture.

### Root Directory

- **bin/**: Executable scripts, batch files and runtime configurations
  - **manage_venv.bat**: Helper script for managing virtual environments with UV
  - **analysis_tool.bat**: Tool for code analysis operations
  - **cleanup_tool.bat**: Tool for cleanup operations
  - **setup_env.bat**: Environment setup script
- **docs/**: Documentation files
  - **folly_analysis_comprehensive.md**: Testing and implementation details
  - **visualization_guide.md**: Guide to using visualization tools
  - **build_tools_guide.md**: Setup guide for build tools
  - **project_structure.md**: Directory organization overview
  - **clang_analyzer_guide.md**: Guide to using the Clang analyzer
- **scripts/**: Consolidated Python scripts
  - **clang_utils.py**: Consolidated Clang utilities
- **src/**: Modular Python package with clean architecture
  - **models/**: Data models and structures
  - **services/**: Business logic services
  - **controllers/**: Input handling and coordination
  - **utils/**: Utility functions
  - **config/**: Configuration settings
- **test_scripts/**: Test and analysis scripts
  - **visualization_tools.py**: Consolidated visualization functionality
  - **indexing_tools.py**: Consolidated indexing functionality
  - **README.md**: Test scripts documentation
  - Various test and analysis scripts
- **.venv/**: Python virtual environment (created by UV)
- **neo4j/**: Neo4j database files when using Docker
  - **data/**: Database data files
  - **logs/**: Database logs
  - **import/**: Import directory
  - **plugins/**: Neo4j plugins
- **output/**: Generated analysis output
  - **analysis/**: Analysis results
  - **stubs/**: Generated function stubs

## Source Code Organization

The codebase follows a clean modular architecture:

### Models Layer

Data structures and entities:
- `Function` - Represents a function with its metadata
- `CallGraph` - Represents relationships between functions

### Services Layer

Core business logic:
- `ClangAnalyzerService` - Clang-based analyzer service
- `SearchService` - Function search service
- `Neo4jService` - Neo4j database service
- `CompileCommandsService` - Compile commands processing service

### Controllers Layer

Coordinates operations between services:
- `AnalysisController` - Manages analysis workflow

### Utils Layer

Helper utilities:
- `file_utils` - File handling utilities
- `parse_utils` - Parse code and output
- `compile_commands` - Process compilation database

### Config Layer

Configuration settings:
- `neo4j_config` - Neo4j connection settings
- `libclang_config` - Clang configuration settings

## How to Use the System

### Command Line Interface

The modular command line interface supports various operations:

```bash
# Index a codebase
python -m src index path/to/code --project my_project --clear --use-clang --parallel

# Search for functions
python -m src search "functionName1" --project my_project

# Find neighbors in the call graph
python -m src neighbors "functionName" --project my_project --direction both --depth 2

# Query using natural language
python -m src nlquery "find string manipulation functions" --project my_project --language en
```

### Consolidated Tools

#### Visualization Tools

The visualization tools have been consolidated into `visualization_tools.py`:

```bash
python test_scripts/visualization_tools.py --type <visualization_type> [options]
```

Available visualization types include:
- `logger_functions`: Visualize Logger-related functions
- `logger_callgraph`: Visualize Logger call graphs
- `hash64_callgraph`: Visualize Hash64 call graphs
- `initimpl_callgraph`: Visualize InitImpl call graphs
- `folly_callgraph`: Generate comprehensive call graphs
- `specific_component`: Visualize specific components
- `main_callgraph`: Visualize main function call graphs
- `folly_graph_viewer`: View specific function relationships

#### Indexing Tools

The indexing tools have been consolidated into `indexing_tools.py`:

```bash
python test_scripts/indexing_tools.py <command> [options]
```

Available commands include:
- `index`: Index a file or directory
- `index-incremental`: Incrementally index a directory
- `index-folly`: Index the Folly codebase
- `clear`: Clear project data from Neo4j

### Programmatic Interface

The modular codebase provides programmatic interfaces for integration:

```python
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.search_service import SearchService
from src.services.neo4j_service import Neo4jService

# Analyze a codebase
analyzer = ClangAnalyzerService()
call_graph = analyzer.analyze_directory(
    "path/to/code",
    use_parallel=True,
    max_workers=4
)

# Search for functions
search = SearchService(neo4j_service)
results = search.search_functions("functionName", "my_project")

# Index in Neo4j
neo4j = Neo4jService()
neo4j.index_call_graph(call_graph, "my_project", clear=True)
```

## Virtual Environment Management

We use UV for fast and efficient virtual environment management:

1. Create a new virtual environment:
   ```
   uv venv .venv
   ```

2. Install dependencies:
   ```
   uv pip install -r requirements.txt
   ```

3. Add a specific package:
   ```
   uv pip install package_name
   ```

4. Activate the environment:
   ```
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/macOS
   ```

## Test Scripts

The test scripts directory contains various tools and tests:

### Analysis Tools

- `visualization_tools.py` - Consolidated visualization functionality
- `indexing_tools.py` - Consolidated indexing functionality
- `debug_neo4j_data.py` - Debug Neo4j database data
- `debug_query.py` - Debug Cypher queries
- `generate_folly_callgraph.py` - Generate Folly call graph using external visualizer

### Function Discovery

- `find_entry_points.py` - Find entry points in the Folly codebase
- `find_main_functions.py` - Find main functions in the Folly codebase
- `find_sfinae_functions.py` - Find SFINAE functions

### Testing Scripts

- `test_concepts_analysis.py` - Tests concept analysis
- `test_compile_commands.py` - Tests compile commands processing
- `test_operator_analysis.py` - Tests operator analysis
- `test_class_hierarchy.py` - Tests class hierarchy analysis
- `test_template_analyzer.py` - Tests template metaprogramming analysis
- `test_basic_analyzer.py` - Tests basic analyzer functionality
- `test_cypher_query.py` - Tests Cypher query functionality
- `test_clang_analyzer_v2.py` - Tests enhanced Clang analyzer
- `test_clang_analyzer.py` - Tests Clang analyzer functionality
- `test_neo4j.py` - Tests Neo4j integration

## Benefits of the Architecture

This modular approach provides:
- Clear separation of concerns
- Improved testability
- Easier extension and maintenance
- Better code organization
- Simplified component dependencies
- Consolidated tools for cleaner workflow 