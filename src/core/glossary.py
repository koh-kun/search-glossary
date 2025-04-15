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
    
    def load_glossary(self, file_path, language_code):
        """
        Load glossary data from a CSV file for a specific language.
        
        Args:
            file_path: Path to the glossary CSV file
            language_code: Two-letter language code (ja, ko, zh)
            
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
                    header = [h.strip().lower() for h in header]
                    
                    # Check if required columns exist
                    if 'term' in header and 'translation' in header:
                        # Get column indices
                        term_idx = header.index('term')
                        translation_idx = header.index('translation')
                        notes_idx = header.index('notes') if 'notes' in header else None
                        
                        # Mark as valid file
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
            # For English, we want to ensure we match whole words only
            # First, tokenize the text into words
            import re
            # This regex splits on word boundaries and keeps punctuation separate
            words = re.findall(r'\b\w+\b', text_lower)
            
            # Check each word against the glossary
            for word in words:
                if word in glossary_data and word not in found_terms:
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