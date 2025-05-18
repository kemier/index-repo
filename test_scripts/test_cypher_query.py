"""
Test script to run direct Cypher queries against Neo4j.
"""
from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def main():
    # Connect to Neo4j
    neo4j = Neo4jService(
        uri=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD
    )
    
    # Test connection
    if not neo4j.test_connection():
        print("Error: Could not connect to Neo4j")
        return
        
    print("Connected to Neo4j successfully")
    
    # Run Cypher query to show all functions and relationships
    print("\nFunction call graph:")
    with neo4j.driver.session() as session:
        result = session.run("""
        MATCH (caller:Function)-[r:CALLS]->(callee:Function)
        WHERE caller.project = 'test_simple'
        RETURN caller.name AS caller, callee.name AS callee
        """)
        
        for record in result:
            print(f"  {record['caller']} -> {record['callee']}")
            
    # Show all functions in the project
    print("\nAll functions in project:")
    with neo4j.driver.session() as session:
        result = session.run("""
        MATCH (f:Function)
        WHERE f.project = 'test_simple'
        RETURN f.name AS name, f.file_path AS file, f.line_number AS line
        """)
        
        for record in result:
            print(f"  {record['name']} (in {record['file']}, line {record['line']})")

if __name__ == "__main__":
    main() 