# Test Scripts

This directory contains various testing and analysis scripts for working with the Folly codebase.

## Visualization Tools

The visualization tools have been consolidated into a single module: `visualization_tools.py`. This module provides a comprehensive set of visualization capabilities for the Folly codebase.

### Usage

```bash
python visualization_tools.py --type <visualization_type> [options]
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
python visualization_tools.py --type logger_functions
```

Visualize the Future component with a call depth of 3:
```bash
python visualization_tools.py --type specific_component --component Future --depth 3
```

Visualize main call graphs including test files:
```bash
python visualization_tools.py --type main_callgraph --include-tests
```

Visualize relationships for a specific function:
```bash
python visualization_tools.py --type folly_graph_viewer --focus BufferedRandomDevice
```

## Other Scripts

- `indexing_tools.py`: Tools for indexing Folly code
- `clear_and_reindex_folly.py`: Clear and reindex the Folly codebase
- `exclude_test_search.py`: Search for code excluding test files
- `find_entry_points.py`: Find entry points in the Folly codebase
- `find_main_functions.py`: Find main functions in the Folly codebase
- `debug_neo4j_data.py`: Debug Neo4j database data
- `debug_query.py`: Debug Cypher queries
- `generate_folly_callgraph.py`: Generate Folly call graph using external visualizer
- Various test scripts for analyzing different aspects of the codebase 