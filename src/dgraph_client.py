from typing import Dict, List
import os
import pydgraph
from dotenv import load_dotenv
from pydantic import BaseModel
import json
import traceback

class DgraphManager:
    def __init__(self, host=None, port=None):
        load_dotenv()
        host = host or os.getenv("DGRAPH_HOST", "localhost")
        port = port or os.getenv("DGRAPH_PORT", "9080")
        
        # Create a client stub
        self.client_stub = pydgraph.DgraphClientStub(f"{host}:{port}")
        # Create a Dgraph client
        self.client = pydgraph.DgraphClient(self.client_stub)
        print(f"DgraphManager initialized, connected to {host}:{port}")
        self._setup_schema()

    def _setup_schema(self):
        """Set up the Dgraph schema for storing code analysis results."""
        schema_string = """
        # Predicate definitions
        name: string @index(term, trigram) .
        file_path: string @index(term) .
        line_number: int .
        is_callback: bool @index(bool) .
        callback_type: string .
        calls: [uid] @reverse .
        called_by: [uid] .
        in_branch: [uid] @reverse .

        branch_node_type: string @index(term) . # Renamed from 'type' to avoid keyword clash
        condition: string .
        contains: [uid] @reverse .

        # Type definitions
        type Function {
            name
            file_path
            line_number
            is_callback
            callback_type
            calls
            called_by
            in_branch
        }

        type Branch {
            branch_node_type # Use the new predicate name
            condition
            file_path
            line_number
            contains
        }
        """
        # Create an Operation object and pass it to alter
        op = pydgraph.Operation(schema=schema_string)
        self.client.alter(op)

    def store_analysis_results(self, results: Dict) -> Dict:
        """Store the code analysis results in Dgraph. Returns UIDs of created nodes."""
        mutation_data = self._prepare_mutation(results)
        response_uids = {} # To store UIDs from different parts of the mutation
        
        txn = self.client.txn()
        try:
            if mutation_data.get("set"):
                response = txn.mutate(set_obj=mutation_data["set"], commit_now=True)
                if response and response.uids:
                    response_uids.update(response.uids)
                print(f"Analysis results stored. UIDs from set_obj: {response.uids if response else 'None'}")
            else:
                print("No data to store from _prepare_mutation.")
            # If you have nquads:
            # if mutation_data.get("nquads"):
            #     mu = pydgraph.Mutation(set_nquads=mutation_data["nquads"], commit_now=False)
            #     response_nquads = txn.mutate(mu)
            #     txn.commit() 
            #     if response_nquads and response_nquads.uids:
            #         response_uids.update(response_nquads.uids)
            #     print(f"Analysis results stored via nquads. UIDs: {response_nquads.uids if response_nquads else 'None'}")

        except pydgraph.AbortedError as e:
            print(f"Transaction aborted while storing analysis results: {e}")
            raise
        except Exception as e:
            print(f"An error occurred during storing analysis results: {e}")
            traceback.print_exc()
            raise
        finally:
            txn.discard()
        return response_uids

    def _prepare_mutation(self, results: Dict) -> Dict:
        """Convert analysis results to Dgraph mutation format."""
        mutation_set = [] # Changed to list for clarity

        # Create unique blank node names for functions first to resolve dependencies
        func_uids = {func.name: f"_:func_{func.name}_{func.file_path.replace('/', '_').replace('.', '_')}_{func.line_number}" for func in results['functions']}

        # Add function nodes
        for func in results['functions']:
            uid = func_uids[func.name]
            func_node = {
                "uid": uid,
                "dgraph.type": "Function",
                "name": func.name,
                "file_path": func.file_path,
                "line_number": func.line_number,
                "is_callback": func.is_callback,
            }
            if func.callback_type: # Only add if it exists
                func_node["callback_type"] = func.callback_type
            mutation_set.append(func_node)

        # Add branch nodes
        branch_uids = {}
        for i, branch_item in enumerate(results.get('branches', [])):
            # Create a more unique UID for branches based on file, line, and type
            branch_uid = f"_:branch_{branch_item.file_path.replace('/', '_').replace('.', '_')}_{branch_item.line_number}_{branch_item.branch_node_type}_{i}"
            branch_uids[i] = branch_uid # Store for potential linking later
            branch_node = {
                "uid": branch_uid,
                "dgraph.type": "Branch",
                "branch_node_type": branch_item.branch_node_type,
                "file_path": branch_item.file_path,
                "line_number": branch_item.line_number,
            }
            if branch_item.condition: # Only add if it exists
                branch_node["condition"] = branch_item.condition
            mutation_set.append(branch_node)
            # TODO: Add logic to link functions to this branch via 'contains' if CodeAnalyzer provides it.

        # Add call relations (Function.calls -> Function)
        for relation in results.get('call_relations', []):
            caller_uid = func_uids.get(relation.caller.name)
            callee_uid = func_uids.get(relation.callee.name)
            if caller_uid and callee_uid:
                # Link caller to callee
                mutation_set.append({
                    "uid": caller_uid,
                    "calls": [{"uid": callee_uid}]
                })
                # Reverse link (callee called_by caller) is handled by @reverse in schema
            else:
                print(f"Warning: Could not find UID for caller {relation.caller.name} or callee {relation.callee.name} for call relation.")

        # TODO: Add logic for Function.in_branch linking if CodeAnalyzer provides it.
        # This would iterate through functions and link them to the appropriate branch_uid.

        return {"set": mutation_set} if mutation_set else {}

    def query_functions(self, query: str) -> List[Dict]:
        """Execute a GraphQL query on the stored data."""
        result = self.client.query(query)
        return result.json

    def close(self):
        if self.client_stub:
            self.client_stub.close()
            print("Dgraph client stub closed.")

    def set_schema(self, schema):
        op = pydgraph.Operation(schema=schema)
        return self.client.alter(op)

    def store_data(self, data):
        txn = self.client.txn()
        try:
            # Assuming data is a list of dicts or a single dict
            response = txn.mutate(set_obj=data, commit_now=True)
            print(f"Data stored: {response.uids}")
            return response
        except pydgraph.AbortedError as e:
            print(f"Transaction aborted: {e}")
            return None
        finally:
            txn.discard()

    def query_data(self, query, variables=None):
        txn = self.client.txn(read_only=True)
        try:
            if variables:
                res = txn.query(query, variables=variables)
            else:
                res = txn.query(query)
            return json.loads(res.json) # Assuming res.json is bytes or string
        finally:
            txn.discard()

    def ensure_schema_exists(self, schema_str):
        # A more robust way might be to query existing schema and compare,
        # but for simplicity, we'll just try to apply it.
        # This might fail if the schema is incompatible with existing data or schema parts.
        print(f"Attempting to set schema: {schema_str}")
        try:
            self.set_schema(schema_str)
            print("Schema alteration attempted.")
        except Exception as e:
            print(f"Error setting schema: {e}")
            # Depending on the error, you might want to handle it differently
            # For now, we'll just print it. If it's a 'schema already exists' type error,
            # that might be acceptable for an 'ensure' operation.
            pass # Or raise an error if schema setting is critical and must succeed 