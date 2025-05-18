"""
Application settings and configuration.

This module contains all the settings and configuration variables used
throughout the application.
"""
import os
from typing import List, Optional

# Default file patterns for C/C++ code
DEFAULT_FILE_PATTERNS: str = "*.c,*.cpp,*.h,*.hpp"

# Output directories
OUTPUT_DIR: str = os.path.join(os.getcwd(), "output")
ANALYSIS_DIR: str = os.path.join(OUTPUT_DIR, "analysis")
STUBS_DIR: str = os.path.join(OUTPUT_DIR, "stubs")

# Ensure directories exist at import time
for directory in [OUTPUT_DIR, ANALYSIS_DIR, STUBS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        
# Neo4j configuration
NEO4J_URI: str = "bolt://localhost:7688"
NEO4J_USER: str = "neo4j" 
NEO4J_PASSWORD: str = "password"
NEO4J_DEFAULT_PROJECT: str = "default"
