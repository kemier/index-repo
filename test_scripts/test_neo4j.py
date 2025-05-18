"""
Test script to verify Neo4j connection and basic functionality.
"""
import sys
import os
import time

# Add the current directory to the path to make imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.neo4j_service import Neo4jService

# Give Neo4j more time to start up
print("Waiting for Neo4j to start up (30 seconds)...")
# time.sleep(30)

# Connect to Neo4j
print("Testing Neo4j connection...")
neo4j = Neo4jService(
    uri="bolt://localhost:7688",
    username="neo4j",
    password="password"
)

# Test connection
connected = neo4j.test_connection()
print(f"Connection test: {'SUCCESS' if connected else 'FAILED'}")

if connected:
    # Clear database
    print("Clearing database...")
    neo4j.clear_database()
    
    # Create a simple test graph
    print("Creating test graph...")
    with neo4j.driver.session() as session:
        # Create some test functions
        session.run("""
        CREATE (main:Function {name: 'main', project: 'test', file_path: 'test.c', line_number: 1})
        CREATE (foo:Function {name: 'foo', project: 'test', file_path: 'test.c', line_number: 10})
        CREATE (bar:Function {name: 'bar', project: 'test', file_path: 'test.c', line_number: 20})
        CREATE (baz:Function {name: 'baz', project: 'test', file_path: 'test.c', line_number: 30})
        CREATE (qux:Function {name: 'qux', project: 'test', file_path: 'test.c', line_number: 40, is_defined: false})
        
        CREATE (main)-[:CALLS]->(foo)
        CREATE (main)-[:CALLS]->(bar)
        CREATE (foo)-[:CALLS]->(baz)
        CREATE (bar)-[:CALLS]->(baz)
        CREATE (baz)-[:CALLS]->(qux)
        """)
    
    # Test queries
    print("\nTesting queries...")
    
    # Function info
    func = neo4j.find_function("main", "test")
    print(f"Function 'main': {func is not None}")
    
    # Callers
    callers = neo4j.find_callers("baz", "test")
    print(f"Functions that call 'baz': {len(callers)}")
    for caller in callers:
        print(f"  - {caller.get('name')} in {caller.get('file_path')}:{caller.get('line_number')}")
    
    # Callees
    callees = neo4j.find_callees("main", "test")
    print(f"Functions called by 'main': {len(callees)}")
    for callee in callees:
        print(f"  - {callee.get('name')} in {callee.get('file_path')}:{callee.get('line_number')}")
    
    # Missing functions
    missing = neo4j.find_missing_functions("test")
    print(f"Missing functions: {missing}")
    
    print("\nNeo4j integration test completed successfully!")
else:
    print("\nNeo4j connection failed. Please check that Neo4j is running and accessible.")

# Close connection
neo4j.close() 