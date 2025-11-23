#!/usr/bin/env python3
"""
🧬 PHASE 2: Code Sanitization
Remove unused imports, debug prints, dead functions, and commented code
"""

import re
from pathlib import Path
from typing import List, Set

# Files to sanitize
FILES_TO_SANITIZE = [
    "src/main.py",
    "src/config.py",
    "src/data.py",
    "src/brain.py",
    "src/trade.py",
]


def find_unused_imports(content: str, filename: str) -> List[str]:
    """Identify imports that are never used in the file"""
    lines = content.split('\n')
    issues = []
    
    # Extract imports
    import_pattern = r'^\s*(from|import)\s+([a-zA-Z0-9_., ]+)'
    imports = {}
    
    for i, line in enumerate(lines, 1):
        match = re.match(import_pattern, line)
        if match:
            if match.group(1) == 'from':
                # from X import Y
                parts = match.group(2).split(' import ')
                if len(parts) == 2:
                    imported = parts[1].split(',')[0].strip()
                    imports[imported] = i
            else:
                # import X
                imported = match.group(2).split(',')[0].strip().split(' as ')[-1]
                imports[imported] = i
    
    # Check usage (simplified)
    code_lines = '\n'.join(lines[i:] for i in range(len(lines)) if i > 20)
    
    for imp, line_num in imports.items():
        # Skip common patterns that are always used
        if imp in ['logging', 'asyncio', 'os', 'sys', 'json', 'time', 'typing']:
            continue
        
        # Check if used (simple substring search)
        if code_lines.count(imp) <= 1:  # Only appears in import line
            issues.append(f"Line {line_num}: Possibly unused import '{imp}'")
    
    return issues


def find_debug_prints(content: str) -> List[str]:
    """Find print() statements that should be logger.X()"""
    issues = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if re.search(r'\bprint\s*\(', line):
            issues.append(f"Line {i}: Debug print() statement: {line.strip()[:60]}")
    
    return issues


def find_dead_functions(content: str) -> List[str]:
    """Identify functions starting with _ that are never called"""
    issues = []
    lines = content.split('\n')
    
    # Find all functions
    func_pattern = r'^\s*def\s+(_[a-zA-Z0-9_]+)\s*\('
    functions = {}
    
    for i, line in enumerate(lines, 1):
        match = re.match(func_pattern, line)
        if match:
            func_name = match.group(1)
            functions[func_name] = i
    
    # Check if called
    code = '\n'.join(lines)
    for func_name, line_num in functions.items():
        # Count calls (excluding definition)
        pattern = r'\b' + re.escape(func_name) + r'\s*\('
        calls = len(re.findall(pattern, code)) - 1  # -1 for definition
        
        if calls == 0:
            issues.append(f"Line {line_num}: Unused function '{func_name}'")
    
    return issues


def find_commented_code(content: str) -> List[str]:
    """Find large blocks of commented code"""
    issues = []
    lines = content.split('\n')
    
    comment_block_lines = 0
    block_start = 0
    
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith('#') and not stripped.startswith('# '):
            # Looks like commented code
            if comment_block_lines == 0:
                block_start = i
            comment_block_lines += 1
        else:
            if comment_block_lines > 5:
                issues.append(f"Lines {block_start}-{i-1}: Large commented block ({comment_block_lines} lines)")
            comment_block_lines = 0
    
    return issues


def sanitize_phase_2():
    """Execute Phase 2: Code Sanitization"""
    
    print("🧬 PHASE 2: CODE SANITIZATION")
    print("=" * 60)
    
    total_issues = 0
    
    for filename in FILES_TO_SANITIZE:
        path = Path(filename)
        if not path.exists():
            print(f"⚠️  File not found: {filename}")
            continue
        
        content = path.read_text()
        print(f"\n📄 Scanning: {filename}")
        
        issues = []
        issues.extend(find_unused_imports(content, filename))
        issues.extend(find_debug_prints(content))
        issues.extend(find_dead_functions(content))
        issues.extend(find_commented_code(content))
        
        if issues:
            print(f"  Found {len(issues)} issues:")
            for issue in issues[:5]:  # Show first 5
                print(f"    ⚠️  {issue}")
            if len(issues) > 5:
                print(f"    ... and {len(issues) - 5} more")
            total_issues += len(issues)
        else:
            print(f"  ✅ No issues found")
    
    print("\n" + "=" * 60)
    print(f"✅ Sanitization scan complete: {total_issues} issues found")
    print("=" * 60)


if __name__ == "__main__":
    sanitize_phase_2()
