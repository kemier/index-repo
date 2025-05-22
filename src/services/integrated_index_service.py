from typing import List, Dict, Any
from src.utils.scanner import scan_files
from src.utils.parser import parse_code_blocks
from src.utils.embedder import CodeEmbedder
from src.services.helixdb_service import HelixDBService
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.models.function_model import Function, CallGraph
import numpy as np

class IntegratedIndexService:
    """Service to build both code embeddings and AST/call graph for Python files in a project directory."""

    def __init__(self, project_dir: str, helixdb_service: HelixDBService, model_name: str = 'microsoft/codebert-base') -> None:
        """
        Initialize the integrated index service.

        Args:
            project_dir: Path to the project directory.
            helixdb_service: Instance of HelixDBService for graph storage.
            model_name: Name of the embedding model to use.
        """
        self.project_dir = project_dir
        self.helixdb_service = helixdb_service
        self.embedder = CodeEmbedder(model_name)
        self.embeddings: List[np.ndarray] = []
        self.embedding_meta: List[Dict[str, Any]] = []

    def build_embeddings_and_ast_graph(self, project_name: str = "default") -> None:
        """
        Build code embeddings and store AST/call graph metadata in HelixDB for all Python files in the project directory.

        Args:
            project_name: Name of the project for HelixDB storage.
        """
        files = scan_files(self.project_dir, exts=(".py",))
        all_functions: List[Dict[str, Any]] = []
        for file in files:
            code_blocks = parse_code_blocks(file)
            for block in code_blocks:
                embedding = self.embedder.embed_code(block['code'])
                self.embeddings.append(embedding)
                self.embedding_meta.append({
                    'file': block['file'],
                    'name': block['name'],
                    'type': block['type'],
                    'start_line': block['start_line'],
                    'end_line': block['end_line']
                })
                # Prepare function metadata for HelixDB
                all_functions.append({
                    'name': block['name'],
                    'signature': '',  # Python signature extraction can be added
                    'file_path': block['file'],
                    'line_number': block['start_line'],
                    'end_line': block['end_line'],
                    'namespace': '',
                    'is_defined': True,
                    'return_type': '',
                    'description': '',
                    'is_virtual': False,
                    'is_template': False,
                    'calls': []
                })
        # Store function metadata in HelixDB
        self.helixdb_service.add_functions_manually(all_functions, project_name=project_name)

    def build_embeddings_and_ast_graph_cpp(
        self,
        project_name: str = "default",
        helixdb_service: HelixDBService = None,
        file_extensions: List[str] = None,
        include_dirs: List[str] = None,
        compiler_args: List[str] = None
    ) -> None:
        """
        Build code embeddings and store AST/call graph metadata in HelixDB for all C/C++ files in the project directory.

        Args:
            project_name: Name of the project for HelixDB storage.
            helixdb_service: HelixDBService instance for database interaction.
            file_extensions: List of file extensions to analyze.
            include_dirs: List of include directories.
            compiler_args: Additional compiler arguments.
        """
        if helixdb_service is None:
            helixdb_service = HelixDBService()
        if file_extensions is None:
            file_extensions = [".c", ".cpp", ".cxx", ".cc", ".h", ".hpp", ".hxx", ".hh"]

        files = scan_files(self.project_dir, exts=tuple(file_extensions))
        all_functions: List[Dict[str, Any]] = []

        for file in files:
            call_graph: CallGraph = clang_analyzer.analyze_file(
                file,
                include_dirs=include_dirs,
                compiler_args=compiler_args
            )
            for func in call_graph.functions.values():
                # Only embed if function body is available
                if func.body:
                    embedding = self.embedder.embed_code(func.body)
                    self.embeddings.append(embedding)
                    self.embedding_meta.append({
                        'file': func.file_path,
                        'name': func.name,
                        'signature': func.signature,
                        'start_line': func.line_number,
                        'end_line': getattr(func, 'end_line', None)
                    })
                # Prepare function metadata for HelixDB
                func_dict = {
                    'name': func.name,
                    'signature': func.signature,
                    'file_path': func.file_path,
                    'line_number': func.line_number,
                    'end_line': getattr(func, 'end_line', None),
                    'namespace': func.namespace,
                    'is_defined': func.is_defined,
                    'return_type': func.return_type,
                    'description': '',  # Optionally extract from comments
                    'is_virtual': func.is_virtual,
                    'is_template': func.is_template,
                    'calls': func.calls
                }
                all_functions.append(func_dict)
        # Store function metadata in HelixDB
        self.helixdb_service.add_functions_manually(all_functions, project_name=project_name) 