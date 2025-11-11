#!/usr/bin/env python3
"""
Script to check that all imported third-party packages are in requirements.txt
"""
import ast
import os
from pathlib import Path
from typing import Set, Dict
import re

# Mapping of import names to PyPI package names
# Some packages have different import names than their PyPI names
IMPORT_TO_PACKAGE = {
    'dotenv': 'python-dotenv',
    'helix': 'helix-py',
    'fastmcp': 'fastmcp',
    'openai': 'openai',
    'ollama': 'ollama',
    'cerebras': 'cerebras-cloud-sdk',
    'google': 'google-genai',  # google.genai
    'numpy': 'numpy',
    'black': 'black',
    'pytest': 'pytest',
}

# Standard library modules (don't need to be in requirements.txt)
STDLIB_MODULES = {
    'typing', 'subprocess', 'json', 'os', 'asyncio', 're', 'functools',
    'sys', 'pathlib', 'collections', 'itertools', 'datetime', 'time',
    'math', 'random', 'hashlib', 'base64', 'urllib', 'http', 'socket',
    'threading', 'multiprocessing', 'queue', 'logging', 'warnings',
    'abc', 'dataclasses', 'enum', 'contextlib', 'copy', 'pickle',
    'io', 'tempfile', 'shutil', 'glob', 'fnmatch', 'stat', 'errno',
}


def extract_imports(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports.add(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    imports.add(module_name)
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return imports


def get_requirements() -> Set[str]:
    """Read requirements.txt and return set of package names."""
    req_file = Path('requirements.txt')
    if not req_file.exists():
        return set()
    
    packages = set()
    with open(req_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Extract package name (before >=, ==, etc.)
            match = re.match(r'^([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)', line)
            if match:
                packages.add(match.group(1).lower())
    
    return packages


def scan_codebase() -> Dict[str, Set[str]]:
    """Scan all Python files in src/ and return imports by file."""
    src_dir = Path('src')
    if not src_dir.exists():
        return {}
    
    results = {}
    for py_file in src_dir.rglob('*.py'):
        imports = extract_imports(py_file)
        if imports:
            try:
                rel_path = str(py_file.relative_to(Path.cwd()))
            except ValueError:
                rel_path = str(py_file)
            results[rel_path] = imports
    
    return results


def main():
    print("Scanning codebase for imports...")
    file_imports = scan_codebase()
    
    print("\nReading requirements.txt...")
    requirements = get_requirements()
    
    # Collect all third-party imports (exclude local 'src' package)
    third_party_imports = set()
    for file_path, imports in file_imports.items():
        for imp in imports:
            if imp not in STDLIB_MODULES and imp != 'src':
                third_party_imports.add(imp)
    
    print(f"\nFound third-party imports: {sorted(third_party_imports)}")
    print(f"\nPackages in requirements.txt: {sorted(requirements)}")
    
    # Check which imports need packages
    missing_packages = set()
    found_packages = set()
    
    for imp in third_party_imports:
        # Check direct match
        if imp.lower() in requirements:
            found_packages.add(imp)
            continue
        
        # Check mapping
        package_name = IMPORT_TO_PACKAGE.get(imp, imp.lower())
        if package_name in requirements:
            found_packages.add(imp)
            continue
        
        # Check if it's a submodule (e.g., cerebras.cloud -> cerebras-cloud-sdk)
        for req in requirements:
            if imp.lower().replace('_', '-') in req or req.replace('-', '_') in imp.lower():
                found_packages.add(imp)
                break
        else:
            missing_packages.add(imp)
    
    print("\n" + "="*60)
    print("DEPENDENCY CHECK RESULTS")
    print("="*60)
    
    if missing_packages:
        print(f"\n[WARNING] MISSING PACKAGES ({len(missing_packages)}):")
        for imp in sorted(missing_packages):
            package_name = IMPORT_TO_PACKAGE.get(imp, imp.lower().replace('_', '-'))
            print(f"  - {imp} -> {package_name}")
    else:
        print("\n[OK] All imports have corresponding packages in requirements.txt!")
    
    print(f"\n[OK] Found packages ({len(found_packages)}):")
    for imp in sorted(found_packages):
        print(f"  - {imp}")
    
    # Show file-by-file breakdown
    print("\n" + "="*60)
    print("IMPORTS BY FILE:")
    print("="*60)
    for file_path, imports in sorted(file_imports.items()):
        third_party = [imp for imp in imports if imp not in STDLIB_MODULES]
        if third_party:
            print(f"\n{file_path}:")
            for imp in sorted(third_party):
                package = IMPORT_TO_PACKAGE.get(imp, imp.lower().replace('_', '-'))
                status = "[OK]" if package in requirements or any(
                    imp.lower().replace('_', '-') in req or req.replace('-', '_') in imp.lower()
                    for req in requirements
                ) else "[MISSING]"
                print(f"  {status} {imp} -> {package}")
    
    return len(missing_packages) == 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

