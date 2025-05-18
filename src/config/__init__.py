"""
Configuration package for application settings
""" 

# Path to tools and configuration

import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Tool paths
CFLOW_PATH = os.environ.get('CFLOW_PATH', 'D:/project/cflow-mingw/cflow-1.6/src/cflow.exe')
DOXYGEN_PATH = os.environ.get('DOXYGEN_PATH', 'doxygen')
GRAPHVIZ_PATH = os.environ.get('GRAPHVIZ_PATH', 'dot')

# Neo4j configuration
NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'password')

# Output paths
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'output')
ANALYSIS_DIR = os.path.join(OUTPUT_DIR, 'analysis')
STUBS_DIR = os.path.join(OUTPUT_DIR, 'stubs')

# Ensure output directories exist
os.makedirs(ANALYSIS_DIR, exist_ok=True)
os.makedirs(STUBS_DIR, exist_ok=True) 