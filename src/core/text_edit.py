"""
Custom text editing components for Search Glossary App.

This module provides custom text editing widgets with enhanced functionality.
"""

from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QTextDocument, QFont
from PySide6.QtCore import Qt, QMimeData
import re

class FormattedTextEdit(QTextEdit):
    """
    A custom QTextEdit that normalizes text formatting when content is pasted,
    while preserving certain formatting elements like bullet points, bold, italic, etc.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Default font size - can be adjusted as needed
        self.default_font_size = 10
        # Default font family
        self.default_font_family = "Segoe UI"
        # Default text color will be set based on theme
        self.is_dark_mode = False
        
    def set_dark_mode(self, is_dark):
        """Update the dark mode setting to determine text color"""
        self.is_dark_mode = is_dark
        
        # Update the color of existing content when theme changes
        self.refresh_formatting()
        
    def refresh_formatting(self):
        """Refresh the formatting of all content in the editor"""
        # Save the current cursor position
        current_position = self.textCursor().position()
        
        # Select all text
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        
        # Apply formatting
        fmt = QTextCharFormat()
        fmt.setFontPointSize(self.default_font_size)
        fmt.setFontFamily(self.default_font_family)
        
        # Set text color based on theme
        if self.is_dark_mode:
            fmt.setForeground(QColor("#e0e0e0"))  # Light color for dark theme
        else:
            fmt.setForeground(QColor("#333333"))  # Dark color for light theme
            
        cursor.mergeCharFormat(fmt)
        
        # Restore cursor position
        cursor.setPosition(current_position)
        self.setTextCursor(cursor)
        
    def processHtml(self, html):
        """
        Process HTML content to keep desired formatting while standardizing fonts and colors.
        
        Args:
            html: The HTML content to process
            
        Returns:
            Processed HTML content
        """
        # Remove image tags
        html = re.sub(r'<img[^>]*>', '', html)
        
        # Set the default font and size throughout the document
        html = re.sub(r'font-family:[^;]+;', f'font-family: {self.default_font_family};', html)
        html = re.sub(r'font-size:[^;]+;', f'font-size: {self.default_font_size}pt;', html)
        
        # Set text color based on theme
        if self.is_dark_mode:
            color_value = "#e0e0e0"  # Light color for dark theme
        else:
            color_value = "#333333"  # Dark color for light theme
        
        # Handle inline style attributes that set color
        # This regex finds style attributes and replaces color properties within them
        html = re.sub(r'(style=["\'][^"\']*?)color\s*:\s*[^;]+;([^"\']*?["\'])', 
                    r'\1color: ' + color_value + r';\2', html)
        
        # For span tags with class="special-text" or similar that might have custom colors
        html = re.sub(r'(<span[^>]*style=["\'][^"\']*?)(color\s*:\s*[^;]+;)([^"\']*?["\'])', 
                    r'\1color: ' + color_value + r';\3', html)
        
        # Replace color CSS properties in any remaining inline styles
        html = re.sub(r'(style=["\'][^"\']*?)color\s*:\s*[^;]+;([^"\']*?["\'])', 
                    r'\1color: ' + color_value + r';\2', html)
        
        # Add default color style to the body if it exists
        html = re.sub(r'(<body[^>]*style=["\'][^"\']*)(["\']*>)', 
                    r'\1; color: ' + color_value + r'\2', html)
        
        # If no style attribute exists in body, add one
        html = re.sub(r'(<body[^>]*)(>)', 
                    r'\1 style="color: ' + color_value + r'"\2', html)
        
        # Handle special span tags with class attributes that typically define colors
        for color_class in ['special-text', 'highlight', 'custom-font']:
            html = re.sub(f'class=["\'][^"\']*?{color_class}[^"\']*?["\']', '', html)
        
        return html
        
    def insertFromMimeData(self, source):
        """
        Override the default paste behavior to sanitize and unify formatting.
        
        Args:
            source: QMimeData containing the clipboard content
        """
        # Skip images but keep text/html
        mime_data = QMimeData()
        
        # Check if there's HTML content (formatted text)
        if source.hasHtml():
            # Process the HTML to standardize formatting while keeping desired elements
            processed_html = self.processHtml(source.html())
            mime_data.setHtml(processed_html)
            
            # Also set plain text as fallback
            if source.hasText():
                mime_data.setText(source.text())
                
            # Call the parent implementation with our processed mime data
            super().insertFromMimeData(mime_data)
        elif source.hasText():
            # If it's plain text without HTML, use that
            mime_data.setText(source.text())
            super().insertFromMimeData(mime_data)
            
            # Apply our formatting to the newly inserted text
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            
            # Get the position where the paste started
            start_position = cursor.position() - len(source.text())
            
            # Select the pasted text
            cursor.setPosition(start_position)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            
            # Apply standard formatting
            fmt = QTextCharFormat()
            fmt.setFontPointSize(self.default_font_size)
            fmt.setFontFamily(self.default_font_family)
            
            if self.is_dark_mode:
                fmt.setForeground(QColor("#e0e0e0"))  # Light color for dark theme
            else:
                fmt.setForeground(QColor("#333333"))  # Dark color for light theme
                
            cursor.mergeCharFormat(fmt)
        else:
            # Fall back to default behavior for other mime types
            # (except images, which won't be included in our mime_data)
            super().insertFromMimeData(source)