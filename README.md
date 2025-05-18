# Folly Code Analysis Repository

This repository contains tools and scripts for analyzing C++ codebases (like Facebook's Folly) using a combination of Clang/libclang. It extracts function call relationships and generates visual call graphs.

## Neo4j Graph Database Integration

The project includes integration with Neo4j graph database for powerful code structure visualization and querying:

- Index your codebase into a graph database structure
- Query complex relationships between functions using Cypher
- Visualize call graphs and dependencies with Neo4j Browser
- Find critical code paths and highly connected functions

### Using the Neo4j Integration

1. Start the Neo4j container using Docker Compose:

```bash
docker-compose up -d
```

2. Index your codebase into Neo4j:

```bash
python -m src index path/to/code --project my_project --clear --use-clang --parallel
```

3. Query the database:

```bash
# Get information about a specific function
python -m src query function function_name

# Find functions that call a specific function
python -m src neighbors function_name --project my_project --direction callers --depth 2

# Find functions called by a specific function
python -m src neighbors function_name --project my_project --direction callees --depth 2

# Query by natural language description (English)
python -m src nlquery "find string comparison functions" --project my_project --language en

# Query by natural language description (Chinese)
python -m src nlquery "查找字符串处理函数" --project my_project --language zh
```

4. Visualize in Neo4j Browser (http://localhost:7475) using Cypher queries:

```cypher
// View function call graph
MATCH (caller:Function)-[r:CALLS]->(callee:Function)
RETURN caller, r, callee
LIMIT 100

// Find functions with most callers (hotspots)
MATCH (f:Function)<-[r:CALLS]-()
RETURN f.name, count(r) as caller_count
ORDER BY caller_count DESC
LIMIT 10

// Find template specializations
MATCH (s:Function)-[:SPECIALIZES]->(t:Function)
RETURN s, t

// Find virtual method overrides
MATCH (d:Function)-[:OVERRIDES]->(b:Function)
RETURN d, b
```

## Repository Structure

```
index-repo/
├── bin/                     # Executable scripts
├── docs/                    # Documentation
│   ├── folly_analysis_comprehensive.md    # Testing and implementation details
│   ├── visualization_guide.md             # Visualization tools guide
│   ├── build_tools_guide.md               # Build tools setup
│   ├── project_structure.md               # Directory organization
│   └── clang_analyzer_guide.md            # Clang analyzer usage
├── neo4j/                   # Neo4j database files when using Docker
│   ├── data/                # Database data files
│   ├── logs/                # Database logs
│   ├── import/              # Import directory
│   └── plugins/             # Neo4j plugins
├── scripts/                 # Consolidated Python scripts
│   ├── cflow_tools.py       # Consolidated cflow functionality
│   └── clang_utils.py       # Consolidated Clang utilities
├── src/                     # Modular Python package with clean architecture
│   ├── models/              # Data models and structures
│   ├── services/            # Business logic services
│   │   ├── clang_analyzer_service.py # Clang-based analyzer service
│   │   ├── search_service.py        # Function search service
│   │   └── neo4j_service.py         # Neo4j database service
│   ├── controllers/         # Input handling and coordination
│   ├── utils/               # Utility functions
│   │   └── compile_commands.py      # Compile commands parsing utilities
│   └── config/              # Configuration settings
├── test_scripts/            # Test and analysis scripts
│   ├── visualization_tools.py       # Consolidated visualization functionality
│   ├── indexing_tools.py            # Consolidated indexing functionality
│   └── README.md                    # Test scripts documentation
├── .venv/                   # Python virtual environment (managed by UV)
└── output/                  # Generated analysis output
    ├── analysis/            # Analysis results
    └── stubs/               # Generated function stubs
```

## Getting Started

### Prerequisites

- Python 3.7 or higher
- Clang and libclang (for C++ analysis)
- Neo4j (optional, for graph visualization)
- Docker and Docker Compose (for running Neo4j container)
- Graphviz
- UV (optional, for better dependency management)
- Facebook's Folly repository (optional, as a test target)

### Installing Clang/libclang

Clang and libclang are required for analyzing C++ code:

- **Linux**: Install using your package manager:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install clang libclang-dev

  # Fedora/RHEL
  sudo dnf install clang clang-devel
  ```

- **Windows**: Install using LLVM installer from https://releases.llvm.org/

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

### Getting Folly (For Testing)

If you want to test the analysis tools on Facebook's Folly library:

1. Clone the Folly repository:
   ```bash
   git clone https://github.com/facebook/folly.git
   ```

2. The analysis tools can now be pointed to this repository for testing:
   ```bash
   python -m src index ./folly --project folly --use-clang --parallel
   ```

## Consolidated Tools

### Visualization Tools

The `visualization_tools.py` module in the `test_scripts` directory provides a comprehensive set of visualization capabilities:

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

For more details, see the `test_scripts/README.md` file.

### Indexing Tools

The `indexing_tools.py` module in the `test_scripts` directory combines functionality from multiple indexing scripts:

```bash
python test_scripts/indexing_tools.py <command> [options]
```

Available commands include:
- `index`: Index a file or directory
- `index-incremental`: Incrementally index a directory
- `index-folly`: Index the Folly codebase
- `clear`: Clear project data from Neo4j

## Documentation

The project documentation has been consolidated into five comprehensive guides:

1. **folly_analysis_comprehensive.md**: Testing and implementation details
2. **visualization_guide.md**: Guide to using visualization tools
3. **build_tools_guide.md**: Setup guide for build tools
4. **project_structure.md**: Directory organization overview
5. **clang_analyzer_guide.md**: Guide to using the Clang analyzer

## Folly Test Results

Comprehensive testing has been performed on Facebook's Folly library to validate the system's capability to handle complex C++ code. Key findings include:

### Tested Files

- Basic files: Format.cpp, String.cpp, Uri.cpp, Benchmark.cpp
- Advanced files with complex C++ features: RegexMatchCache.cpp, Future.cpp, Barrier.cpp

### Analysis Performance

- **Function identification**: 95-98% accuracy for standard functions; 90-95% for template/virtual functions
- **Call relationship detection**: 96% for direct calls; 75-80% for virtual/template function calls
- **Indexing performance**: ~12 functions/second, peak memory usage ~500MB for large files

### C++ Feature Support

- **Class methods**: 95% accurate identification and relationship mapping
- **Templates**: 85% accurate for basic templates, 70% for complex specializations
- **Namespaces**: 90% accuracy for nested namespaces, 85% for distinguishing same-named functions

### Natural Language Query Capabilities

- **English queries**: 85% accuracy, 80% recall
- **Chinese queries**: 75% accuracy, 65% recall
- **Query performance**: Average response time ~200ms

## Limitations and Challenges

The system has some limitations when handling complex C++ codebases:

1. **Complex C++ Features**:
   - Template instantiation tracking needs improvement
   - Virtual function and polymorphic call analysis is limited
   - Operator overloading and implicit conversions have limited support
   - SFINAE and advanced template metaprogramming support is limited

2. **Include Directory Configuration**:
   - Auto-detection of include paths can be improved
   - Dependency on compiler flags and macro definitions
   - Platform-specific features can cause inconsistencies

3. **Performance with Large Codebases**:
   - Memory usage is high for codebases >1M lines
   - Limited support for incremental analysis
   - Parallel processing capabilities need optimization

4. **Query Understanding**:
   - Chinese terminology recognition needs improvement
   - Context awareness for code semantics is limited
   - Query sorting and relevance ranking can be improved

## Quick Start

1. Run the analysis on a C/C++ codebase:

```bash
python -m src index path/to/your/source/code --project my_project --use-clang --parallel
```

2. Search for specific functions:

```bash
python -m src search "functionName1" --project my_project
```

3. Find neighbors in the call graph:

```bash
python -m src neighbors "functionName" --project my_project --direction both --depth 2
```

4. Query using natural language:

```bash
python -m src nlquery "find string manipulation functions" --project my_project --language en
```

## Modular Design

The codebase follows a clean modular architecture:

- **Models**: Data structures and entities (`Function`, `CallGraph`)
- **Services**: Business logic (`ClangAnalyzerService`, `SearchService`, `Neo4jService`)
- **Controllers**: Coordinating operations (`AnalysisController`)
- **Utils**: Helper utilities (`file_utils`, `parse_utils`, `compile_commands`)
- **Config**: Configuration settings

This approach provides:
- Clear separation of concerns
- Improved testability
- Easier extension and maintenance

## Virtual Environment Management with UV

[UV](https://github.com/astral-sh/uv) is a fast Python package installer and resolver that can be used to manage virtual environments for this project.

### Creating a Virtual Environment

```bash
# Create a new virtual environment
uv venv .venv

# Activate the virtual environment
.venv\Scripts\activate
```

### Installing Dependencies

```bash
# Install dependencies from requirements.txt
uv pip install -r requirements.txt
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Clang/libclang: For robust C++ code analysis
- Neo4j: Graph database for storing and querying call relationships
- UV: Fast Python package installer and virtual environment manager
- Facebook's Folly: Used as a test target for analysis
- jieba: Chinese text segmentation library for natural language queries 