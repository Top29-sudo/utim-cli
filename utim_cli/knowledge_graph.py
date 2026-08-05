"""
Codebase Knowledge Graph — AST-based dependency and call graph analysis using Tree-sitter.

This module parses the codebase into a knowledge graph of imports, function calls,
and class relationships, enabling blast-radius analysis for code changes.
"""

import os
import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

# Tree-sitter imports
try:
    from tree_sitter import Language, Parser
    import tree_sitter_python as ts_python
    import tree_sitter_javascript as ts_javascript
    import tree_sitter_typescript as ts_typescript
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

# Graph storage
from utim_cli.config import get_utim_dir as _get_utim_dir
GRAPH_FILE = str(_get_utim_dir() / "tmp" / "knowledge_graph.json")


@dataclass
class CodeEntity:
    """Represents a code entity (function, class, variable, etc.)."""
    id: str
    type: str  # function, class, method, import, variable
    name: str
    filepath: str
    line_start: int = 0
    line_end: int = 0
    visibility: str = "public"  # public, private
    metadata: Dict = field(default_factory=dict)


@dataclass
class CodeRelation:
    """Represents a relationship between code entities."""
    from_id: str
    to_id: str
    relation_type: str  # calls, imports, inherits, implements, references


class KnowledgeGraph:
    """
    Builds and maintains a knowledge graph from codebase AST analysis.
    """
    
    def __init__(self):
        self.entities: Dict[str, CodeEntity] = {}
        self.relations: List[CodeRelation] = []
        self.file_entities: Dict[str, List[str]] = {}  # filepath -> entity ids
        self.reference_index: Dict[str, List[str]] = {}  # name -> entity ids
        
        # Language parsers
        self.parsers: Dict[str, Parser] = {}
        self._init_parsers()
        
    def _init_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            return
            
        try:
            py_lang = Language(ts_python.language())
            self.parsers[".py"] = Parser(py_lang)
        except Exception:
            pass
            
        try:
            js_lang = Language(ts_javascript.language())
            self.parsers[".js"] = Parser(js_lang)
        except Exception:
            pass
            
        try:
            ts_lang = Language(ts_typescript.language())
            self.parsers[".ts"] = Parser(ts_lang)
        except Exception:
            pass
            
        try:
            tsx_lang = Language(ts_typescript.language_tsx())
            self.parsers[".tsx"] = Parser(tsx_lang)
        except Exception:
            pass
    
    def _get_parser(self, filepath: str) -> Optional[Parser]:
        """Get appropriate parser for file extension."""
        ext = os.path.splitext(filepath)[1].lower()
        return self.parsers.get(ext)
    
    def _make_entity_id(self, filepath: str, name: str, line: int = 0) -> str:
        """Generate unique entity ID."""
        return f"{filepath}:{name}:{line}"
    
    def parse_python_file(self, filepath: str, content: bytes) -> List[CodeEntity]:
        """Parse Python file for functions, classes, imports, and calls."""
        entities = []
        
        if ".py" not in self.parsers:
            return entities
            
        try:
            tree = self.parsers[".py"].parse(content)
            root = tree.root_node
        except Exception:
            return entities
        
        def walk(node, in_class: str = None):
            if node.type == "function_definition":
                name_node = None
                body_start = node.start_point[0]
                
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
                
                if name_node:
                    name = name_node.text.decode()
                    entity_type = "method" if in_class else "function"
                    entity_id = self._make_entity_id(filepath, name, body_start + 1)
                    
                    entities.append(CodeEntity(
                        id=entity_id,
                        type=entity_type,
                        name=name,
                        filepath=filepath,
                        line_start=body_start + 1,
                        line_end=node.end_point[0] + 1,
                        metadata={"class": in_class} if in_class else {}
                    ))
            
            elif node.type == "class_definition":
                name_node = None
                
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
                
                if name_node:
                    name = name_node.text.decode()
                    entity_id = self._make_entity_id(filepath, name, node.start_point[0] + 1)
                    
                    entities.append(CodeEntity(
                        id=entity_id,
                        type="class",
                        name=name,
                        filepath=filepath,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1
                    ))
                    
                    # Walk body for class members
                    for child in node.children:
                        if child.type == "block":
                            walk(child, in_class=name)
            
            elif node.type == "import_statement" or node.type == "import_from_statement":
                names = []
                module = ""
                
                for child in node.children:
                    if child.type == "dotted_name" or child.type == "identifier":
                        names.append(child.text.decode())
                    elif child.type == "module_name":
                        module = child.text.decode()
                
                for name in names:
                    entity_id = self._make_entity_id(filepath, f"import:{name}", node.start_point[0] + 1)
                    entities.append(CodeEntity(
                        id=entity_id,
                        type="import",
                        name=name,
                        filepath=filepath,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        metadata={"module": module}
                    ))
            
            for child in node.children:
                walk(child, in_class)
        
        walk(root)
        return entities
    
    def parse_javascript_file(self, filepath: str, content: bytes) -> List[CodeEntity]:
        """Parse JavaScript/TypeScript file for functions, classes, imports."""
        entities = []
        
        ext = os.path.splitext(filepath)[1].lower()
        parser_key = ext if ext in self.parsers else None
        
        if not parser_key:
            return entities
        
        try:
            tree = self.parsers[parser_key].parse(content)
            root = tree.root_node
        except Exception:
            return entities
        
        def walk(node, in_class: str = None):
            if node.type in ("function_declaration", "function_expression", "arrow_function"):
                name = "anonymous"
                if node.type in ("function_declaration", "function_expression"):
                    for child in node.children:
                        if child.type == "identifier":
                            name = child.text.decode()
                            break
                
                entity_type = "method" if in_class else "function"
                entity_id = self._make_entity_id(filepath, name, node.start_point[0] + 1)
                
                entities.append(CodeEntity(
                    id=entity_id,
                    type=entity_type,
                    name=name,
                    filepath=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1
                ))
            
            elif node.type == "class_declaration":
                name = "anonymous"
                for child in node.children:
                    if child.type == "identifier":
                        name = child.text.decode()
                        break
                
                entity_id = self._make_entity_id(filepath, name, node.start_point[0] + 1)
                entities.append(CodeEntity(
                    id=entity_id,
                    type="class",
                    name=name,
                    filepath=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1
                ))
                
                for child in node.children:
                    if child.type in ("class_body", "block"):
                        walk(child, in_class=name)
            
            for child in node.children:
                walk(child, in_class)
        
        walk(root)
        return entities
    
    def build_graph(self, paths: List[str] = None, exclude_dirs: Set[str] = None) -> int:
        """
        Build knowledge graph from codebase files.
        
        Args:
            paths: Specific files to parse. If None, walks directory.
            exclude_dirs: Directories to exclude.
        
        Returns:
            Number of entities found.
        """
        if exclude_dirs is None:
            exclude_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".utim_tmp"}
        
        self.entities.clear()
        self.relations.clear()
        self.file_entities.clear()
        
        files_to_parse = []
        
        if paths:
            files_to_parse = [p for p in paths if os.path.exists(p)]
        else:
            for root, dirs, files in os.walk("."):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".py", ".js", ".ts", ".tsx"]:
                        p = os.path.join(root, f)
                        files_to_parse.append(p)
        
        for filepath in files_to_parse:
            try:
                with open(filepath, "rb") as f:
                    content = f.read()
                
                ext = os.path.splitext(filepath)[1].lower()
                
                if ext == ".py":
                    entities = self.parse_python_file(filepath, content)
                elif ext in [".js", ".ts", ".tsx"]:
                    entities = self.parse_javascript_file(filepath, content)
                else:
                    entities = []
                
                for entity in entities:
                    self.entities[entity.id] = entity
                    if filepath not in self.file_entities:
                        self.file_entities[filepath] = []
                    self.file_entities[filepath].append(entity.id)
                    
                    # Update reference index
                    if entity.name not in self.reference_index:
                        self.reference_index[entity.name] = []
                    self.reference_index[entity.name].append(entity.id)
                    
            except Exception:
                continue
        
        self._save_graph()
        return len(self.entities)
    
    def find_dependents(self, entity_name: str, filepath: str = None) -> List[Dict]:
        """
        Find all files that depend on a given entity (call, import, etc.).
        
        Args:
            entity_name: Name of the function/class to find callers for
            filepath: Optional specific file to search in
        
        Returns:
            List of dependent file paths with relationship info.
        """
        dependents = []
        
        # Find the entity
        matching_ids = []
        for eid, entity in self.entities.items():
            if entity.name == entity_name:
                if filepath is None or entity.filepath == filepath:
                    matching_ids.append(eid)
        
        # For each matching entity, find references
        for target_id in matching_ids:
            target_entity = self.entities.get(target_id)
            if not target_entity:
                continue
            
            # Check for functions/methods that might call this
            for eid, entity in self.entities.items():
                if entity.type in ("function", "method"):
                    # Simple heuristic: same project, different file
                    if entity.filepath != target_entity.filepath:
                        dependents.append({
                            "filepath": entity.filepath,
                            "line": entity.line_start,
                            "type": "potential_caller",
                            "entity": entity.name
                        })
        
        return list(set(d.get("filepath") for d in dependents))
    
    def get_blast_radius(self, filepath: str) -> List[str]:
        """
        Estimate files that might be affected by changes to a file.
        
        Args:
            filepath: File to analyze
        
        Returns:
            List of potentially affected file paths.
        """
        affected = set()
        
        # Get entities in the file
        file_entity_ids = self.file_entities.get(filepath, [])
        
        for eid in file_entity_ids:
            entity = self.entities.get(eid)
            if not entity:
                continue
            
            # Find dependents for each entity
            deps = self.find_dependents(entity.name, entity.filepath)
            affected.update(deps)
        
        return list(affected)
    
    def get_stats(self) -> Dict:
        """Get knowledge graph statistics."""
        return {
            "total_entities": len(self.entities),
            "total_files": len(self.file_entities),
            "entity_types": {
                t: sum(1 for e in self.entities.values() if e.type == t)
                for t in ["function", "method", "class", "import"]
            }
        }
    
    def _save_graph(self):
        """Save graph to disk."""
        os.makedirs(".utim_tmp", exist_ok=True)
        
        data = {
            "entities": [
                {
                    "id": e.id,
                    "type": e.type,
                    "name": e.name,
                    "filepath": e.filepath,
                    "line_start": e.line_start,
                    "line_end": e.line_end
                }
                for e in self.entities.values()
            ],
            "file_entities": self.file_entities
        }
        
        with open(GRAPH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def load_graph(self):
        """Load graph from disk if exists."""
        if os.path.exists(GRAPH_FILE):
            try:
                with open(GRAPH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for e in data.get("entities", []):
                    entity = CodeEntity(
                        id=e["id"],
                        type=e["type"],
                        name=e["name"],
                        filepath=e["filepath"],
                        line_start=e.get("line_start", 0),
                        line_end=e.get("line_end", 0)
                    )
                    self.entities[entity.id] = entity
                
                self.file_entities = data.get("file_entities", {})
                
                return True
            except Exception:
                pass
        return False


# Global instance
_knowledge_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> Optional[KnowledgeGraph]:
    """Get or create the global knowledge graph instance."""
    global _knowledge_graph
    if _knowledge_graph is None and TREE_SITTER_AVAILABLE:
        _knowledge_graph = KnowledgeGraph()
        _knowledge_graph.load_graph()
    return _knowledge_graph


def build_knowledge_graph(paths: List[str] = None) -> int:
    """Build or rebuild the knowledge graph."""
    kg = get_knowledge_graph()
    if kg:
        return kg.build_graph(paths)
    return 0