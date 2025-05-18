# Folly Code Visualization Guide

## Overview

This guide provides information about visualizing and exploring the Facebook Folly library's code structure using the consolidated tools provided in this repository.

## Prerequisites

- Python 3.7+
- Neo4j graph database (running on localhost:7688)
- GraphViz (for rendering visualizations)
- Python packages: networkx, py2neo

## Installation

1. Ensure Neo4j is running and accessible:
   ```bash
   # Example using Docker
   docker run -p 7688:7687 -p 7475:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest
   ```

   Alternatively, you can use the included Docker Compose configuration:
   ```bash
   docker-compose up -d
   ```

2. Install required Python packages:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Install GraphViz:
   - Windows: Download from https://graphviz.org/download/
   - macOS: `brew install graphviz`
   - Linux: `sudo apt-get install graphviz`

## Consolidated Visualization Tools

All visualization functionality has been consolidated into a single module: `visualization_tools.py` in the `test_scripts` directory. This provides a unified interface for all visualization needs.

### Basic Usage

```bash
python test_scripts/visualization_tools.py --type <visualization_type> [options]
```

### Available Visualization Types

- `logger_functions`: Visualize Logger-related functions in Folly
- `logger_callgraph`: Visualize the call graph for Logger-related functions
- `hash64_callgraph`: Visualize the call graph for Hash64-related functions
- `initimpl_callgraph`: Visualize the call graph for InitImpl-related functions
- `folly_callgraph`: Generate comprehensive Folly call graph visualizations
- `specific_component`: Visualize a specific component in Folly
- `main_callgraph`: Visualize call graphs starting from main functions
- `folly_graph_viewer`: Simple viewer for specific function relationships

### Common Options

- `--depth INT`: Maximum call depth to visualize (default: 2)
- `--limit INT`: Maximum number of functions to include (default: 150)
- `--focus STRING`: Component/function to focus on
- `--component STRING`: Component to visualize (for specific_component, default: Future)
- `--include-tests`: Include test files in the visualization
- `--multiple`: Generate multiple visualizations (one for each major component)
- `--output-dir STRING`: Output directory for visualization files (default: output)

### Examples

Visualize Logger functions:
```bash
python test_scripts/visualization_tools.py --type logger_functions
```

Visualize the Future component with a call depth of 3:
```bash
python test_scripts/visualization_tools.py --type specific_component --component Future --depth 3
```

Visualize main call graphs including test files:
```bash
python test_scripts/visualization_tools.py --type main_callgraph --include-tests
```

Visualize relationships for a specific function:
```bash
python test_scripts/visualization_tools.py --type folly_graph_viewer --focus BufferedRandomDevice
```

## Database Explorer Tools

### Debug Neo4j Data

Use `debug_neo4j_data.py` to explore the content of the Neo4j database:

```bash
python test_scripts/debug_neo4j_data.py
```

This will show:
- Available projects and function counts
- Node and relationship statistics
- Sample functions and relationships

### Query Debugger

Use `debug_query.py` to test specific Neo4j queries:

```bash
python test_scripts/debug_query.py
```

## Visualization Legend

The generated visualizations include the following elements:

- **Nodes**: Functions or methods
  - **Red boxes**: Special functions (LoggerDB, Hash64, InitImpl, main, etc.)
  - **Colored ellipses**: Regular functions, colored by namespace/file
- **Edges**: Function call relationships
  - **Solid lines**: Direct function calls (thicker lines for direct calls)
  - **Dashed lines**: File-to-function relationships
- **Node colors**: Colored by namespace or file path

## Neo4j Browser Visualization

You can also visualize the code structure directly in Neo4j Browser (http://localhost:7475) using Cypher queries:

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

## Function Visualization Types

### Logger Functions

```bash
python test_scripts/visualization_tools.py --type logger_functions
```

This generates a visualization of all Logger-related functions in the Folly codebase, grouped by file.

### Logger Call Graph

```bash
python test_scripts/visualization_tools.py --type logger_callgraph --depth 3 --limit 200
```

This generates a call graph starting from important Logger-related functions, showing their relationships.

### Specific Component Visualization

```bash
python test_scripts/visualization_tools.py --type specific_component --component Future
```

This focuses on a specific component in the Folly codebase, showing related functions and their call relationships.

### Hash64 Call Graph

```bash
python test_scripts/visualization_tools.py --type hash64_callgraph
```

This generates a call graph focused on Hash64-related functions, useful for understanding hashing implementation.

### Main Call Graph

```bash
python test_scripts/visualization_tools.py --type main_callgraph --include-tests
```

This generates a call graph starting from main functions, showing program entry points and execution flow.

## Troubleshooting

1. **Memory issues**: When analyzing large codebases, you may encounter memory issues. Try:
   - Reducing the `--limit` value
   - Reducing the `--depth` value
   - Using the `--focus` parameter to analyze specific parts

2. **Empty graph**: If you get an empty graph, check:
   - Neo4j connection parameters
   - Whether the focus parameter matches any functions
   - If analysis completed successfully (check logs)

3. **GraphViz errors**: Ensure GraphViz is installed and in your PATH

4. **No function relationships found**:
   - Verify Neo4j connection settings
   - Check that the focus parameter matches function names in the database
   - Run `debug_neo4j_data.py` to confirm data is available

5. **Connection issues with Neo4j**:
   - Verify Neo4j is running on the expected port (default: 7688)
   - Check credentials in scripts (default: neo4j/password)

## Architecture Overview

The visualization tools have been designed with a modular architecture:

1. **Database Query Functions**: Extract relevant data from Neo4j
2. **Visualization Functions**: Transform data into network graphs
3. **Rendering Functions**: Generate visual representations using GraphViz
4. **Command-line Interfaces**: Provide user-friendly access to functionality

This modular design allows for easy extension and maintenance of the visualization capabilities. 