"""
Auto-update system for SearchGlossary
Handles checking and downloading app and CSV updates from GitHub
"""

import os
import json
import requests
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class UpdateManager:
    """Manages checking for and applying updates."""
    
    def _version_to_tuple(self, version: str) -> tuple:
        """Convert version string to tuple for comparison (e.g., '1.0.0' -> (1, 0, 0))"""
        try:
            return tuple(map(int, version.split('.')))
        except:
            return (0, 0, 0)  # Fallback for invalid versions

    def check_for_app_update(self) -> Tuple[bool, Optional[Dict]]:
        """Check if a new app version is available."""
        try:
            response = requests.get(self.app_update_url, timeout=10)
            response.raise_for_status()
            
            latest_info = response.json()
            latest_version = latest_info.get("version")
            
            # Semantic version comparison - only update if newer
            current_tuple = self._version_to_tuple(self.current_version)
            latest_tuple = self._version_to_tuple(latest_version)
            
            update_available = latest_tuple > current_tuple
            
            return update_available, latest_info if update_available else None
            
        except Exception as e:
            logger.error(f"Failed to check for app updates: {str(e)}")
            return False, None
    
    def check_for_csv_updates(self) -> Dict[str, Dict]:
        """
        Check which CSV files have updates available.
        
        Returns:
            Dictionary of CSV files that need updating
        """
        try:
            # Get the latest CSV version info from GitHub
            response = requests.get(self.csv_update_url, timeout=10)
            response.raise_for_status()
            
            remote_versions = response.json()
            updates_needed = {}

            installed_versions = self._get_installed_versions()
            
            # Check each CSV file
            for csv_file, remote_info in remote_versions.items():
                local_path = self.user_glossaries_dir / csv_file
                
                # If file doesn't exist locally, we need it
                if not local_path.exists():
                    updates_needed[csv_file] = remote_info
                    continue
                
                local_version = installed_versions.get(csv_file, "0.0.0")
                remote_version = remote_info.get("version", "1.0.0")               
                
                # Check if remote version is newer
                local_tuple = self._version_to_tuple(local_version)
                remote_tuple = self._version_to_tuple(remote_version)
                
                if remote_tuple > local_tuple:
                    updates_needed[csv_file] = remote_info
            
            return updates_needed
            
        except Exception as e:
            logger.error(f"Failed to check for CSV updates: {str(e)}")
            return {}
    
    def __init__(self, current_version: str):
        """
        Initialize the UpdateManager.
        
        Args:
            current_version: Current app version (e.g., "1.0.0")
        """
        self.current_version = current_version
        
        # GitHub URLs for update checking
        self.app_update_url = "https://raw.githubusercontent.com/koh-kun/search-glossary/main/releases/latest.json"
        self.csv_update_url = "https://raw.githubusercontent.com/koh-kun/search-glossary/main/glossaries/glossary-versions.json"
        
        # Set up user data directory for persistent CSV storage
        self.user_data_dir = self._get_user_data_dir()
        self.user_glossaries_dir = self.user_data_dir / "glossaries"
        self.installed_versions_file = self.user_data_dir / "installed-versions.json"

        # Create directories if they don't exist
        self.user_glossaries_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_installed_versions(self) -> Dict[str, str]:
        """Read our record of which CSV versions are currently installed.

        Returns a dict like {"Ja_En_Glossary.csv": "1.0.1"}.
        Returns an empty dict the very first time, before anything's downloaded.
        """
        try:
            with open(self.installed_versions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _record_installed_version(self, csv_file: str, version: str) -> None:
    
        installed = self._get_installed_versions()   # read what we have
        installed[csv_file] = version                # update this one entry
        with open(self.installed_versions_file, 'w', encoding='utf-8') as f:
            json.dump(installed, f, indent=2)        # write the whole thing back
    
    def _get_user_data_dir(self) -> Path:
        """Get platform-specific user data directory."""
        import platform
        
        system = platform.system()
        if system == "Windows":
            # Use AppData\Local\SearchGlossary
            app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(app_data) / "SearchGlossary"
        else:
            # Linux/Mac: Use ~/.local/share/SearchGlossary
            return Path.home() / ".local" / "share" / "SearchGlossary"
    def download_csv_updates(self, updates: Dict[str, Dict]) -> List[str]:
        """Download and install CSV updates to user data directory."""
        updated_files = []
               
        for csv_file, info in updates.items():
            download_url = info.get("download_url")
            if not download_url:
                logger.error(f"No download URL for {csv_file}")
                continue
            
            try:
                # Download the updated CSV
                response = requests.get(download_url, timeout=30)
                response.raise_for_status()
                
                # Save to user glossaries directory (persistent location)
                local_path = self.user_glossaries_dir / csv_file
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                updated_files.append(csv_file)
                version = info.get("version", "1.0.0")
                self._record_installed_version(csv_file, version)
                logger.info(f"Updated CSV: {csv_file} -> {local_path}")
                
            except Exception as e:
                logger.error(f"Failed to update {csv_file}: {str(e)}")
        
        return updated_files