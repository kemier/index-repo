"""
Utility functions for parsing cflow and other output formats.

This module re-exports parsers from specific parser modules to provide
a unified interface for parsing various file formats used in code analysis.
"""
from typing import TYPE_CHECKING, Dict, List, Set, Optional, Tuple, Any

from src.utils.cflow_parser import parse_cflow_output
from src.utils.dot_parser import parse_dot_file

# Re-export all parsers for backward compatibility
__all__ = ['parse_cflow_output', 'parse_dot_file'] 