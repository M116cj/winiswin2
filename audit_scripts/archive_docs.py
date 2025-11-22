#!/usr/bin/env python3
"""
📚 Documentation Archivist - Archive all markdown reports to versioned history
Creates docs/version_history/ and organizes all audit/architecture docs chronologically
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

class DocArchivist:
    def __init__(self):
        self.docs_dir = Path("docs/version_history")
        self.archived_files = []
        self.skipped_files = []
        
    def create_archive_dir(self):
        """Create docs/version_history directory"""
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created archive directory: {self.docs_dir}")
    
    def extract_date_and_version(self, filepath: str) -> Tuple[str, str]:
        """Extract date and version from markdown file"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2000)  # Read first 2000 chars
            
            # Try to find date: YYYY-MM-DD
            date_match = re.search(r'Date[:\s]*(\d{4}-\d{2}-\d{2})', content)
            if date_match:
                date_str = date_match.group(1).replace('-', '')
                return date_str, None
            
            # Try to find version: X.X or vX.X
            version_match = re.search(r'[vV](?:ersion)?[:\s]*(\d+\.\d+\.\d+|\d+\.\d+)', content)
            if version_match:
                return None, version_match.group(1)
            
            # Try to find "Report Generated"
            generated_match = re.search(r'Generated[:\s]*(\d{4}-\d{2}-\d{2})', content)
            if generated_match:
                date_str = generated_match.group(1).replace('-', '')
                return date_str, None
            
            # Use file modification time as fallback
            mtime = os.path.getmtime(filepath)
            date_str = datetime.fromtimestamp(mtime).strftime('%Y%m%d')
            return date_str, None
        
        except Exception as e:
            print(f"⚠️ Could not parse {filepath}: {e}")
            return None, None
    
    def get_topic_from_filename(self, filename: str) -> str:
        """Extract topic from filename"""
        name = filename.replace('.md', '').replace('_', ' ').title()
        # Limit to reasonable length
        if len(name) > 40:
            name = name[:40]
        return name.replace(' ', '_')
    
    def archive_markdown_files(self):
        """Find, sort, and archive all markdown files"""
        # Skip these files
        skip_list = {'README.md', 'ARCHITECTURE.md', 'replit.md'}
        
        # Find all .md files
        md_files = []
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.md') and file not in skip_list:
                    filepath = os.path.join(root, file)
                    date_str, version = self.extract_date_and_version(filepath)
                    
                    if date_str:
                        md_files.append((filepath, date_str, version, file))
                    else:
                        self.skipped_files.append((filepath, "Could not extract date"))
        
        # Sort by date
        md_files.sort(key=lambda x: x[1], reverse=True)
        
        # Archive with sequential numbering
        for idx, (filepath, date_str, version, original_name) in enumerate(md_files, 1):
            topic = self.get_topic_from_filename(original_name)
            new_name = f"v{idx:02d}_{date_str}_{topic}.md"
            dest_path = self.docs_dir / new_name
            
            try:
                shutil.copy2(filepath, dest_path)
                self.archived_files.append((filepath, new_name))
                print(f"✅ v{idx:02d}: {original_name} → {new_name}")
            except Exception as e:
                print(f"❌ Failed to archive {filepath}: {e}")
    
    def print_report(self):
        """Print archival report"""
        print("\n" + "="*80)
        print("📚 DOCUMENTATION ARCHIVAL REPORT")
        print("="*80)
        
        print(f"\n✅ ARCHIVED ({len(self.archived_files)} files):")
        for original, archived in self.archived_files:
            print(f"   {archived}")
        
        if self.skipped_files:
            print(f"\n⚠️ SKIPPED ({len(self.skipped_files)} files):")
            for filepath, reason in self.skipped_files:
                print(f"   {filepath}: {reason}")
        
        print(f"\n📁 Archive Location: {self.docs_dir}")
        print("="*80)

if __name__ == "__main__":
    archivist = DocArchivist()
    archivist.create_archive_dir()
    archivist.archive_markdown_files()
    archivist.print_report()
