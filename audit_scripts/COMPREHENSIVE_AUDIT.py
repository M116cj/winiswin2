#!/usr/bin/env python3
"""
🔍 Complete Repository Carpet Audit - Comprehensive Classification & Organization Check
"""

import os
import json
from pathlib import Path
from collections import defaultdict

class ComprehensiveAudit:
    def __init__(self):
        self.files_by_category = defaultdict(list)
        self.orphaned_files = []
        self.misclassified = []
        self.duplicate_content = []
        self.report = {}
        
    def scan_repository(self):
        """Scan entire repository"""
        print("\n" + "="*80)
        print("🔍 COMPREHENSIVE REPOSITORY AUDIT")
        print("="*80 + "\n")
        
        # Categories and their expected locations
        categories = {
            'source_code': ('src/**/*.py', 'src/'),
            'audit_scripts': ('audit_scripts/**/*.py', 'audit_scripts/'),
            'tests': ('tests/**/*.py', 'tests/'),
            'scripts': ('scripts/**/*.py', 'scripts/'),
            'diagnostics': ('diagnostics/**/*.py', 'diagnostics/'),
            'examples': ('examples/**/*.py', 'examples/'),
            'documentation': ('*.md', 'docs/**/*.md', './'),
            'config': ('*.toml', '*.json', 'requirements.txt', './'),
            'data': ('data/**/*', 'data/'),
            'models': ('models/**/*', 'models/'),
        }
        
        # Scan all Python files
        for root, dirs, files in os.walk('.'):
            # Skip system directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', '.cache', '.local', '.pythonlibs',
                '.upm', 'node_modules', '.pytest_cache'
            ]]
            
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = filepath.lstrip('./')
                
                # Classify file
                if file.endswith('.py'):
                    self._classify_python_file(rel_path, filepath)
                elif file.endswith('.md'):
                    self._classify_markdown_file(rel_path, filepath)
                elif file in ['requirements.txt', 'nixpacks.toml', 'railway.toml', 'railway.json', 'pyproject.toml']:
                    self.files_by_category['config'].append(rel_path)
                else:
                    if not any(x in rel_path for x in ['.cache', '.git', '.local', '.upm', '__pycache__']):
                        self.files_by_category['other'].append(rel_path)
    
    def _classify_python_file(self, rel_path, filepath):
        """Classify Python files"""
        if 'src/' in rel_path:
            self.files_by_category['source_code'].append(rel_path)
        elif 'audit_scripts/' in rel_path:
            self.files_by_category['audit_scripts'].append(rel_path)
        elif 'tests/' in rel_path:
            self.files_by_category['tests'].append(rel_path)
        elif 'scripts/' in rel_path:
            self.files_by_category['scripts'].append(rel_path)
        elif 'diagnostics/' in rel_path:
            self.files_by_category['diagnostics'].append(rel_path)
        elif 'examples/' in rel_path:
            self.files_by_category['examples'].append(rel_path)
        else:
            self.orphaned_files.append(rel_path)
    
    def _classify_markdown_file(self, rel_path, filepath):
        """Classify Markdown files"""
        if rel_path in ['README.md', 'replit.md']:
            self.files_by_category['root_docs'].append(rel_path)
        elif 'docs/' in rel_path:
            self.files_by_category['documentation'].append(rel_path)
        elif rel_path.startswith('AUDIT') or rel_path.startswith('SYSTEM') or rel_path.startswith('REPOSITORY'):
            self.files_by_category['root_docs'].append(rel_path)
        else:
            self.orphaned_files.append(rel_path)
    
    def print_audit_report(self):
        """Print comprehensive audit report"""
        print("\n" + "="*80)
        print("📊 FILE CLASSIFICATION REPORT")
        print("="*80)
        
        for category, files in sorted(self.files_by_category.items()):
            if files:
                print(f"\n✅ {category.upper()} ({len(files)} files):")
                if len(files) <= 10:
                    for f in sorted(files):
                        print(f"   - {f}")
                else:
                    for f in sorted(files)[:5]:
                        print(f"   - {f}")
                    print(f"   ... and {len(files)-5} more")
        
        if self.orphaned_files:
            print(f"\n⚠️ ORPHANED FILES ({len(self.orphaned_files)}):")
            for f in sorted(self.orphaned_files)[:10]:
                print(f"   - {f}")
            if len(self.orphaned_files) > 10:
                print(f"   ... and {len(self.orphaned_files)-10} more")
        
        # Check for issues
        print("\n" + "="*80)
        print("🔍 CLASSIFICATION CHECK")
        print("="*80)
        
        issues = []
        
        # Check if diagnostics should be moved to audit_scripts
        if self.files_by_category['diagnostics']:
            issues.append(f"⚠️ Found {len(self.files_by_category['diagnostics'])} files in diagnostics/ → should move to audit_scripts/")
        
        # Check if there are orphaned Python files
        orphaned_py = [f for f in self.orphaned_files if f.endswith('.py')]
        if orphaned_py:
            issues.append(f"⚠️ Found {len(orphaned_py)} orphaned .py files in root")
        
        # Check docs organization
        if self.files_by_category['documentation']:
            old_docs = [f for f in self.files_by_category['documentation'] 
                       if 'version_updates' not in f and 'version_history' not in f]
            if old_docs:
                issues.append(f"⚠️ Found {len(old_docs)} .md files in docs/ (not in version folders)")
        
        if issues:
            print("\nIssues Found:")
            for issue in issues:
                print(issue)
        else:
            print("\n✅ All files properly classified!")
        
        # Summary
        print("\n" + "="*80)
        print("📈 SUMMARY")
        print("="*80)
        total_files = sum(len(v) for v in self.files_by_category.values()) + len(self.orphaned_files)
        print(f"\nTotal files scanned: {total_files}")
        print(f"Categories found: {len(self.files_by_category)}")
        print(f"Orphaned files: {len(self.orphaned_files)}")
        
        print("\n" + "="*80)
        print("AUDIT COMPLETE")
        print("="*80 + "\n")

if __name__ == "__main__":
    audit = ComprehensiveAudit()
    audit.scan_repository()
    audit.print_audit_report()
