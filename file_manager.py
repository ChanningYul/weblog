#!/usr/bin/env python3
"""
File Manager Module
Handles file operations with version control and change tracking
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

class FileManager:
    """Manages file operations with version control"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path.resolve()
        self.version = 0
        self.last_modified = None
        self.content_hash = None
        
        # Ensure file exists
        self.ensure_file_exists()
        self.load_metadata()
    
    def ensure_file_exists(self):
        """Ensure the file and its directory exist"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")
    
    def load_metadata(self):
        """Load file metadata"""
        try:
            stat = self.file_path.stat()
            self.last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Calculate content hash
            content = self.file_path.read_text(encoding="utf-8")
            self.content_hash = hashlib.md5(content.encode()).hexdigest()
        except Exception as e:
            print(f"Error loading metadata: {e}")
            self.last_modified = datetime.now()
            self.content_hash = ""
    
    def increment_version(self):
        """Increment version number"""
        self.version += 1
    
    def validate_version(self, expected_version: int) -> bool:
        """Validate if the current version matches the expected version"""
        return self.version == expected_version
    
    def get_content(self) -> str:
        """Get current file content"""
        try:
            return self.file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading file: {e}")
            return ""
    
    def get_version(self) -> int:
        """Get current version number"""
        return self.version
    
    def update_full_content(self, content: str) -> bool:
        """Update file with full content"""
        try:
            # Write content
            self.file_path.write_text(content, encoding="utf-8")
            
            # Update metadata
            self.load_metadata()
            
            # Increment version after successful update
            self.increment_version()
            
            return True
        except Exception as e:
            print(f"Error updating full content: {e}")
            return False
    
    def apply_changes(self, changes: List[Dict], expected_version: Optional[int] = None) -> tuple[bool, str]:
        """Apply incremental changes to file
        
        Args:
            changes: List of change operations
            expected_version: Expected version before applying changes
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate version if provided
            if expected_version is not None and not self.validate_version(expected_version):
                return False, "version_mismatch"
            
            # Read current content
            content = self.get_content()
            
            # Apply changes in reverse order to maintain positions
            for change in reversed(changes):
                if change['type'] == 'replace':
                    position = change['position']
                    length = change.get('length', 0)
                    new_content = change['content']
                    
                    # Validate position
                    if position < 0 or position > len(content):
                        print(f"Invalid position: {position}")
                        return False, "invalid_position"
                    
                    # Apply replace operation
                    content = (
                        content[:position] + 
                        new_content + 
                        content[position + length:]
                    )
            
            # Write updated content
            success = self.update_full_content(content)
            if success:
                return True, "success"
            else:
                return False, "write_failed"
            
        except Exception as e:
            print(f"Error applying changes: {e}")
            return False, str(e)
    
    def calculate_diff(self, old_content: str, new_content: str) -> List[Dict]:
        """Calculate differences between two contents"""
        changes = []
        
        # Handle empty contents
        if not old_content and new_content:
            return [{
                'type': 'replace',
                'position': 0,
                'content': new_content,
                'length': 0
            }]
        
        if old_content and not new_content:
            return [{
                'type': 'replace',
                'position': 0,
                'content': '',
                'length': len(old_content)
            }]
        
        # Find common prefix
        prefix_len = 0
        while (prefix_len < len(old_content) and 
               prefix_len < len(new_content) and 
               old_content[prefix_len] == new_content[prefix_len]):
            prefix_len += 1
        
        # Find common suffix
        suffix_len = 0
        max_suffix = min(len(old_content) - prefix_len, len(new_content) - prefix_len)
        while (suffix_len < max_suffix and 
               old_content[len(old_content) - 1 - suffix_len] == 
               new_content[len(new_content) - 1 - suffix_len]):
            suffix_len += 1
        
        # Extract differing parts
        old_middle = old_content[prefix_len:len(old_content) - suffix_len]
        new_middle = new_content[prefix_len:len(new_content) - suffix_len]
        
        # Create replace operation
        if old_middle != new_middle:
            changes.append({
                'type': 'replace',
                'position': prefix_len,
                'content': new_middle,
                'length': len(old_middle)
            })
        
        return changes
    
    def get_file_info(self) -> Dict:
        """Get file information"""
        try:
            stat = self.file_path.stat()
            return {
                'path': str(self.file_path),
                'size': stat.st_size,
                'modified': self.last_modified.isoformat() if self.last_modified else None,
                'version': self.version,
                'hash': self.content_hash
            }
        except Exception as e:
            print(f"Error getting file info: {e}")
            return {
                'path': str(self.file_path),
                'size': 0,
                'modified': None,
                'version': self.version,
                'hash': self.content_hash
            }

class FileManagerPool:
    """Manages multiple file managers"""
    
    def __init__(self):
        self.managers: Dict[str, FileManager] = {}
    
    def get_manager(self, file_path: str) -> FileManager:
        """Get or create a file manager for the given path"""
        if file_path not in self.managers:
            self.managers[file_path] = FileManager(Path(file_path))
        return self.managers[file_path]
    
    def remove_manager(self, file_path: str):
        """Remove a file manager"""
        if file_path in self.managers:
            del self.managers[file_path]
    
    def list_managers(self) -> List[str]:
        """List all managed file paths"""
        return list(self.managers.keys())

# Example usage
if __name__ == "__main__":
    # Create file manager
    file_manager = FileManager(Path("test.txt"))
    
    # Test operations
    print("Initial content:", file_manager.get_content())
    print("Version:", file_manager.get_version())
    print("File info:", file_manager.get_file_info())
    
    # Test incremental changes
    old_content = "Hello World"
    new_content = "Hello Beautiful World"
    changes = file_manager.calculate_diff(old_content, new_content)
    print("Changes:", changes)
    
    # Apply changes
    file_manager.update_full_content(old_content)
    print("After update:", file_manager.get_content())
    
    # Apply incremental changes
    success = file_manager.apply_changes(changes)
    print("Apply changes success:", success)
    print("After incremental update:", file_manager.get_content())