"""
Glossary handling module for Search Glossary.

This module provides functionality to load, parse, and manage glossary data.
"""

import csv
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class GlossaryManager:
    """Manages multiple glossary files and term lookups."""
    
    def __init__(self):
        """Initialize the GlossaryManager with multiple language support."""
        # Dictionary to store glossaries for different languages
        self.glossaries = {
            "en": {"data": {}, "path": None, "info": {"total_terms": 0, "last_updated": None}},
            "ko": {"data": {}, "path": None, "info": {"total_terms": 0, "last_updated": None}},
            "zh": {"data": {}, "path": None, "info": {"total_terms": 0, "last_updated": None}}
        }
        self.current_language = "en"  # Default to Japanese
    
    def load_glossary(self, file_path, language_code="en"):
        """
        Load glossary data from a CSV file for a specific language.
        
        Args:
            file_path: Path to the glossary CSV file
            language_code: Two-letter language code (en, ko, zh)
            
        Returns:
            bool: True if loading was successful, False otherwise
        """
        try:
            # Clear existing data for this language
            self.glossaries[language_code]["data"] = {}
            
            # Track if this is a valid glossary file
            valid_file = False
            term_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as csv_file:
                # Create CSV reader
                csv_reader = csv.reader(csv_file)
                
                # Read header row
                try:
                    header = next(csv_reader)
                    
                    # Normalize header names
                    header = [h.strip() for h in header]
                    
                    # Store header information for display purposes
                    self.glossaries[language_code]["header"] = header
                    
                    # Define column indices based on language code
                    if language_code == "en":
                        # For English glossary with standard format
                        normalized_header = [h.lower() for h in header]
                        if "term" in normalized_header and "translation" in normalized_header:
                            term_idx = normalized_header.index("term")
                            translation_idx = normalized_header.index("translation")
                            notes_idx = normalized_header.index("notes") if "notes" in normalized_header else None
                            valid_file = True
                            
                            # Process data rows
                            for row in csv_reader:
                                if len(row) > max(term_idx, translation_idx):
                                    term = row[term_idx].strip().lower()
                                    translation = row[translation_idx].strip()
                                    notes = row[notes_idx].strip() if notes_idx is not None and len(row) > notes_idx else ""
                                    
                                    if term and translation:  # Ensure non-empty values
                                        self.glossaries[language_code]["data"][term] = {
                                            "translation": translation,
                                            "notes": notes
                                        }
                                        term_count += 1
                    
                    elif language_code == "ko":
                        # For Korean glossary
                        if "ハングル" in header and "日本語" in header:
                            term_idx = header.index("ハングル")
                            translation_idx = header.index("日本語")
                            valid_file = True
                            
                            # Process data rows
                            for row in csv_reader:
                                if len(row) > max(term_idx, translation_idx):
                                    term = row[term_idx].strip().lower()
                                    translation = row[translation_idx].strip()
                                    
                                    # Store all columns
                                    column_data = {}
                                    for i, col_name in enumerate(header):
                                        if i < len(row):
                                            column_data[col_name] = row[i].strip()
                                        else:
                                            column_data[col_name] = ""
                                    
                                    if term and translation:  # Ensure non-empty values
                                        self.glossaries[language_code]["data"][term] = column_data
                                        term_count += 1
                                        
                    elif language_code == "zh":
                        # For Chinese glossary
                        if "中文" in header and "日本語" in header:
                            term_idx = header.index("中文")
                            translation_idx = header.index("日本語")
                            valid_file = True
                            
                            # Process data rows
                            for row in csv_reader:
                                if len(row) > max(term_idx, translation_idx):
                                    term = row[term_idx].strip().lower()
                                    translation = row[translation_idx].strip()
                                    
                                    # Store all columns
                                    column_data = {}
                                    for i, col_name in enumerate(header):
                                        if i < len(row):
                                            column_data[col_name] = row[i].strip()
                                        else:
                                            column_data[col_name] = ""
                                    
                                    if term and translation:  # Ensure non-empty values
                                        self.glossaries[language_code]["data"][term] = column_data
                                        term_count += 1
                                    
                except StopIteration:
                    logger.error("CSV file is empty or malformed")
                    return False
            
            if valid_file:
                # Update glossary info
                self.glossaries[language_code]["info"]["total_terms"] = term_count
                self.glossaries[language_code]["info"]["last_updated"] = datetime.now().isoformat()
                self.glossaries[language_code]["path"] = file_path
                
                logger.info(f"Successfully loaded {term_count} terms from {file_path}")
                return True
            else:
                logger.error(f"Invalid glossary format in {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading glossary file {file_path}: {str(e)}")
            return False

    def _get_column_mapping(self, language_code, header):
        """
        Get column mapping based on language code and header.
        
        Args:
            language_code: Two-letter language code
            header: List of column headers
        
        Returns:
            Dictionary mapping standard field names to column indices
        """
        mapping = {}
        
        if language_code == "en":
            # For English glossary with standard format
            if "term" in [h.lower() for h in header] and "translation" in [h.lower() for h in header]:
                mapping["term"] = [h.lower() for h in header].index("term")
                mapping["translation"] = [h.lower() for h in header].index("translation")
                if "notes" in [h.lower() for h in header]:
                    mapping["notes"] = [h.lower() for h in header].index("notes")
        
        elif language_code == "ko":
            # For Korean glossary
            if "ハングル" in header and "日本語" in header:
                mapping["term"] = header.index("ハングル")
                mapping["translation"] = header.index("日本語")
                # Map additional fields
                for i, field in enumerate(header):
                    if field not in ["ハングル", "日本語"]:
                        mapping[field] = i
                # Use 英語 as notes if available
                if "英語（ある場合）" in header:
                    mapping["notes"] = header.index("英語（ある場合）")
                elif "メモ" in header:
                    mapping["notes"] = header.index("メモ")
        
        elif language_code == "zh":
            # For Chinese glossary
            if "中文" in header and "日本語" in header:
                mapping["term"] = header.index("中文")
                mapping["translation"] = header.index("日本語")
                # Map additional fields
                for i, field in enumerate(header):
                    if field not in ["中文", "日本語"]:
                        mapping[field] = i
                # Use 英語 as notes if available
                if "英語（ある場合）" in header:
                    mapping["notes"] = header.index("英語（ある場合）")
                elif "メモ" in header:
                    mapping["notes"] = header.index("メモ")
        
        return mapping
    
    def set_current_language(self, language_code):
        """Set the current language for term lookups."""
        if language_code in self.glossaries:
            self.current_language = language_code
            return True
        return False
    
    def get_term(self, term):
        """Look up a term in the current language glossary."""
        return self.glossaries[self.current_language]["data"].get(term.strip().lower())
    
    def get_all_terms(self):
        """Get all terms in the current language glossary."""
        return self.glossaries[self.current_language]["data"]
    
    def get_glossary_info(self):
        """Get information about the loaded glossary."""
        return self.glossaries[self.current_language]["info"]
    
    def find_terms_in_text(self, text):
        """Find all glossary terms in the given text."""
        glossary_data = self.glossaries[self.current_language]["data"]
        if not text or not glossary_data:
            return []
        
        # Convert text to lowercase for case-insensitive matching
        text_lower = text.lower()
        found_terms = set()
        results = []
        
        if self.current_language == "en":
            # Define terms that require exact case matching
            case_sensitive_terms = ["AND", "WHO"]
            
            # For English, we want to ensure we match whole words only
            import re
            # This regex splits on word boundaries and keeps punctuation separate
            words = re.findall(r'\b\w+\b', text_lower)
            
            # Check each word against the glossary
            for word in words:
                if word in glossary_data and word not in found_terms:
                    # Skip if this is a lowercase version of a case-sensitive term
                    if word.upper() in case_sensitive_terms:
                        continue
                    
                    found_terms.add(word)
                    results.append({
                        "term": word,
                        "translation": glossary_data[word]["translation"],
                        "notes": glossary_data[word]["notes"]
                    })
                    
            # Also check for multi-word terms
            for term in glossary_data:
                # Skip single words as we've already checked them
                if " " in term and term in text_lower and term not in found_terms:
                    found_terms.add(term)
                    results.append({
                        "term": term,
                        "translation": glossary_data[term]["translation"],
                        "notes": glossary_data[term]["notes"]
                    })
            
            # Check for exact case-sensitive matches for special terms
            for special_term in case_sensitive_terms:
                # Convert to lowercase for dictionary lookup
                term_lower = special_term.lower()
                # Only proceed if the term exists in our glossary
                if term_lower in glossary_data:
                    # Find exact case matches in the original text
                    exact_matches = re.findall(r'\b' + re.escape(special_term) + r'\b', text)
                    if exact_matches and term_lower not in found_terms:
                        found_terms.add(term_lower)
                        results.append({
                            "term": special_term,  # Use the uppercase version for display
                            "translation": glossary_data[term_lower]["translation"],
                            "notes": glossary_data[term_lower]["notes"]
                        })
        
        elif self.current_language == "ko":
            # For Korean, use both word boundary and direct matching
            words = text_lower.split()
            clean_words = [word.strip(".,!?:;\"'()[]{}<>") for word in words]
            
            # Check individual words
            for word in clean_words:
                if word in glossary_data and word not in found_terms:
                    found_terms.add(word)
                    results.append({
                        "term": word,
                        "translation": glossary_data[word]["translation"],
                        "notes": glossary_data[word]["notes"]
                    })
            
            # Also check all terms directly for multi-word or non-spaced terms
            for term in glossary_data:
                if term in text_lower and term not in found_terms:
                    found_terms.add(term)
                    results.append({
                        "term": term,
                        "translation": glossary_data[term]["translation"],
                        "notes": glossary_data[term]["notes"]
                    })
        
        else:  # Chinese or other non-space-delimited languages
            # For Chinese, check each term in the glossary against the text
            for term in glossary_data:
                if term in text_lower and term not in found_terms:
                    found_terms.add(term)
                    results.append({
                        "term": term,
                        "translation": glossary_data[term]["translation"],
                        "notes": glossary_data[term]["notes"]
                    })
        
        return results
# Basic test function if the module is run directly
if __name__ == "__main__":
    # This will only run if the file is executed directly, not when imported
    print("Glossary Manager Test")
    
    # Create a glossary manager
    manager = GlossaryManager()
    
    # Test with a sample file if provided as argument
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        file_path = sys.argv[1]
        print(f"Loading glossary from: {file_path}")
        if manager.load_glossary(file_path):
            print(f"Loaded {manager.glossary_info['total_terms']} terms")
            # Print first 5 terms as a sample
            for i, (term, data) in enumerate(list(manager.glossary_data.items())[:5]):
                print(f"{i+1}. {term}: {data['translation']} - {data['notes']}")
        else:
            print("Failed to load glossary")
    else:
        print("Usage: python glossary.py <path-to-csv-file>")
        print("No file provided or file not found. Exiting.")