"""
Simple test script to test function call detection.
"""
import os
import sys
import logging

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.clang_analyzer_service import ClangAnalyzerService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Path to the test file
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "test_files", "test_calls.cpp")
    
    # Initialize analyzer
    logger.info(f"Initializing analyzer for file: {test_file}")
    analyzer = ClangAnalyzerService()
    
    # Analyze the file
    logger.info("Analyzing file...")
    call_graph = analyzer.analyze_file(test_file, analyze_templates=True, track_virtual_methods=True)
    
    # Report results
    logger.info(f"Found {len(call_graph.functions)} functions")
    
    # Print the functions and their calls
    for name, func in call_graph.functions.items():
        logger.info(f"Function: {name}")
        if func.calls:
            logger.info(f"  Calls: {', '.join(func.calls)}")
        if func.called_by:
            logger.info(f"  Called by: {', '.join(func.called_by)}")
        logger.info("---")
    
    # Print call relationships
    call_count = sum(len(func.calls) for func in call_graph.functions.values())
    logger.info(f"Total call relationships: {call_count}")
    
if __name__ == "__main__":
    main() 