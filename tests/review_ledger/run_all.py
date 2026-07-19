import unittest
import os
import sys

def run_all_tests():
    # Discover and run all tests in this directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add scripts to sys.path so they import cleanly
    scripts_dir = os.path.abspath(os.path.join(test_dir, "../../plugins/gin-workflow/src/scripts"))
    sys.path.insert(0, scripts_dir)
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=test_dir, pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
