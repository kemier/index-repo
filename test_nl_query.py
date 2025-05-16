import unittest
import os
from src.main import CodeAnalysisSystem
import traceback # Make sure traceback is imported at the top

class TestNLQuery(unittest.TestCase):
    def test_code_analysis_system_initialization(self):
        print("Attempting to initialize CodeAnalysisSystem...")
        try:
            system = CodeAnalysisSystem()
            print("CodeAnalysisSystem initialized successfully!")
            # Add assertions here if needed, e.g.:
            # self.assertIsNotNone(system, "System should not be None after initialization")
        except Exception as e:
            print(f"Error during CodeAnalysisSystem initialization: {str(e)}")
            traceback.print_exc()
            self.fail(f"CodeAnalysisSystem initialization failed: {str(e)}")

if __name__ == '__main__':
    print("Starting unittest for test_nl_query.py...")
    unittest.main()
    print("Finished unittest for test_nl_query.py.") 