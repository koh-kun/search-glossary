#!/usr/bin/env python3
"""
Search Glossary App

A cross-platform desktop application that identifies specialized terminology in pasted text,
displays translations from a glossary, and allows users to copy translations to the clipboard.
"""

import sys
import os
from pathlib import Path

# Use PySide6 for Qt functionality
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QTextEdit, QPushButton, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QCheckBox
)
from PySide6.QtGui import QFont, QClipboard, QColor
from PySide6.QtCore import Qt, QSize

# Import our custom text edit component
try:
    # Try relative import first (when run as a package)
    from core.text_edit import FormattedTextEdit
except ImportError:
    try:
        # Try absolute import (when run as project)
        from src.core.text_edit import FormattedTextEdit
    except ImportError:
        # Adjust path for direct script execution
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.text_edit import FormattedTextEdit

# Import our glossary manager
try:
    # Try relative import first (when run as a package)
    from core.glossary import GlossaryManager
except ImportError:
    try:
        # Try absolute import (when run from project root)
        from src.core.glossary import GlossaryManager
    except ImportError:
        # Adjust path for direct script execution
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.glossary import GlossaryManager

from PySide6.QtGui import QPalette
from PySide6.QtCore import Qt

def is_dark_theme(app):
    """Detect if the system is using a dark theme."""
    return app.palette().color(QPalette.Window).lightness() < 128

# Application version
APP_VERSION = "0.1.0"

def get_light_stylesheet():
    """Return stylesheet for light theme."""
    return """
    QMainWindow, QWidget {
        background-color: #f5f5f5;
        color: #333333;
    }
    QTextEdit, QTableWidget {
        background-color: white;
        border: 1px solid #cccccc;
    }
    QTableWidget::item:alternate {
        background-color: #f0f7ff;
    }
    QPushButton {
        background-color: #e0e0e0;
        border: 1px solid #bbbbbb;
        padding: 5px 10px;
        border-radius: 3px;
    }
    QPushButton:hover {
        background-color: #d0d0d0;
    }
    QHeaderView::section {
        background-color: #e0e0e0;
        padding: 4px;
        border: 1px solid #cccccc;
    }
    """

def get_dark_stylesheet():
    """Return stylesheet for dark theme."""
    return """
    QMainWindow, QWidget {
        background-color: #2e2e2e;
        color: #e0e0e0;
    }
    QTextEdit, QTableWidget {
        background-color: #3a3a3a;
        color: #e0e0e0;
        border: 1px solid #555555;
    }
    QTableWidget::item:alternate {
        background-color: #404040;
    }
    QTableWidget::item {
        color: #e0e0e0;
    }
    QPushButton {
        background-color: #505050;
        color: #e0e0e0;
        border: 1px solid #666666;
        padding: 5px 10px;
        border-radius: 3px;
    }
    QPushButton:hover {
        background-color: #606060;
    }
    QHeaderView::section {
        background-color: #404040;
        color: #e0e0e0;
        padding: 4px;
        border: 1px solid #555555;
    }
    QLabel, QComboBox {
        color: #e0e0e0;
    }
    QComboBox {
        background-color: #3a3a3a;
        border: 1px solid #555555;
    }
    QComboBox QAbstractItemView {
        background-color: #3a3a3a;
        color: #e0e0e0;
    }
    QStatusBar {
        color: #e0e0e0;
    }
    """

class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
    
        # Set window properties
        self.setWindowTitle(f"辞書検索ツール v{APP_VERSION}")
        self.setMinimumSize(800, 600)
        
        # Detect if we're using a dark theme
        self.is_dark = is_dark_theme(QApplication.instance())
        
        # Apply appropriate stylesheet
        if self.is_dark:
            self.setStyleSheet(get_dark_stylesheet())
        else:
            self.setStyleSheet(get_light_stylesheet())
        
        # Initialize UI components
        self.init_ui()

        # Set initial dark mode state for the text editor
        self.input_text.set_dark_mode(self.is_dark)
        
        # Initialize glossary manager
        self.glossary_manager = GlossaryManager()
        self.matches = []   # Will hold matched terms

        # Load all language glossaries
        self.load_all_glossaries()

    def init_ui(self):
        """Initialize the user interface components."""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Input text area
        input_label = QLabel("入力テキスト:")
        self.input_text = FormattedTextEdit()
        self.input_text.setPlaceholderText("ここに原文テキストを貼り付けてください...")
        
        # Language selection area
        glossary_layout = QHBoxLayout()
        glossary_label = QLabel("言語:")
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")  # English in English
        self.language_combo.addItem("한국어", "ko")     # Korean in Korean
        self.language_combo.addItem("中文", "zh")      # Chinese in Chinese
        self.language_combo.setMinimumContentsLength(10)  # Set minimum width to fit content
        self.language_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)  # Adjust size to content
        self.language_combo.currentIndexChanged.connect(self.change_language)
        
        find_terms_btn = QPushButton("用語を検索")
        find_terms_btn.clicked.connect(self.find_terms)
        
        glossary_layout.addWidget(glossary_label)
        glossary_layout.addWidget(self.language_combo)
        glossary_layout.addStretch()
        glossary_layout.addWidget(find_terms_btn)
        
        # Results table
        results_label = QLabel("検索結果:")
        self.results_table = QTableWidget(0, 3)  # 0 rows, 3 columns
        self.results_table.setHorizontalHeaderLabels(["用語", "翻訳", "注釈"])
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.doubleClicked.connect(self.copy_translation)
        
        # Status bar
        self.statusBar().showMessage("準備完了")
        
        # Add widgets to main layout
        main_layout.addWidget(input_label)
        main_layout.addWidget(self.input_text)
        main_layout.addLayout(glossary_layout)
        main_layout.addWidget(results_label)
        main_layout.addWidget(self.results_table)
        
        # Set up menu
        self.create_menus()

        # Add theme toggle switch in top-right
        theme_layout = QHBoxLayout()
        theme_layout.addStretch()
        self.theme_switch = QCheckBox("ナイトモード")
        self.theme_switch.setChecked(self.is_dark)
        self.theme_switch.stateChanged.connect(self.toggle_theme)
        theme_layout.addWidget(self.theme_switch)
        
        # Add to main layout
        main_layout.addLayout(theme_layout)

    def change_language(self, index):
        """Change the current glossary language."""
        language_code = self.language_combo.itemData(index)
        if self.glossary_manager.set_current_language(language_code):
            info = self.glossary_manager.glossaries[language_code]["info"]
            self.statusBar().showMessage(f"{self.language_combo.currentText()}: {info['total_terms']}用語")
        else:
            self.statusBar().showMessage("言語の変更に失敗しました")

    def load_all_glossaries(self):
        """Load all language glossaries."""
        # Define possible locations for glossary files
        base_paths = [
            "",  # Current directory
            "resources/",
            os.path.join(os.path.dirname(__file__), "resources/"),
            os.path.join(os.path.dirname(__file__), "../resources/")
        ]
        
        # Language-specific glossary files
        language_files = {
            "en": "Ja_En_Glossary.csv",
            "ko": "Ja_Ko_Glossary.csv",
            "zh": "Ja_Zh_Glossary.csv"
        }
        
        # Keep track of loaded glossaries
        loaded_glossaries = []
        
        # Try to load each glossary
        for lang_code, filename in language_files.items():
            loaded = False
            
            for base_path in base_paths:
                file_path = os.path.join(base_path, filename)
                if os.path.exists(file_path):
                    if self.glossary_manager.load_glossary(file_path, lang_code):
                        loaded = True
                        loaded_glossaries.append(lang_code)
                        break
            
            # Clear the status bar after loading all glossaries
            if loaded_glossaries:
                self.statusBar().showMessage("準備完了")
            else:
                self.statusBar().showMessage("辞書が見つかりませんでした")

    def toggle_theme(self, state=None):
        """Switch between light and dark themes."""
        if state is not None:
            self.is_dark = bool(state)
        else:
            self.is_dark = not self.is_dark
            
        if self.is_dark:
            self.setStyleSheet(get_dark_stylesheet())
            self.input_text.set_dark_mode(True)  # Update text edit theme
        else:
            self.setStyleSheet(get_light_stylesheet())
            self.input_text.set_dark_mode(False)  # Update text edit theme

    def create_menus(self):
        """Create application menus."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")
        
        open_action = file_menu.addAction("&Open Text File...")
        open_action.triggered.connect(self.open_text_file)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("&Exit")
        exit_action.triggered.connect(self.close)
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self.show_about_dialog)
    

    
    def open_text_file(self):
        """Open a text file and load its contents into the input text area."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
                    self.input_text.setText(text)
                self.statusBar().showMessage(f"読み込んだファイル： {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイルが開けませんでした： {str(e)}")
    
    def find_terms(self):
        """Find glossary terms in the input text."""
        # Get the text from the input area
        text = self.input_text.toPlainText()
        
        if not text:
            self.statusBar().showMessage("検索するテキストを貼り付けてください。")
            return
        
        # Use the glossary manager to find terms
        self.matches = self.glossary_manager.find_terms_in_text(text)
        
        # Update the results table
        self.update_results_table()
        
        # Update status bar
        term_count = len(self.matches)
        self.statusBar().showMessage(f"{term_count} 個の単語が検出されました。")
    
    def update_results_table(self):
        """Update the results table with matched terms."""
        # Get current language
        language_code = self.language_combo.itemData(self.language_combo.currentIndex())
        
        # Get header information if available
        header = self.glossary_manager.glossaries[language_code].get("header", [])
        
        # Set the number of rows based on matches
        self.results_table.setRowCount(len(self.matches))
        
        # Adjust table based on language
        if language_code == "en":
            # Standard 3-column format for English
            self.results_table.setColumnCount(3)
            self.results_table.setHorizontalHeaderLabels(["用語", "翻訳", "注釈"])
            
            # Fill the table with data
            for row, match in enumerate(self.matches):
                # Term
                term_item = QTableWidgetItem(match["term"])
                term_item.setFlags(term_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
                self.results_table.setItem(row, 0, term_item)
                
                # Translation
                translation_item = QTableWidgetItem(match["translation"])
                translation_item.setFlags(translation_item.flags() & ~Qt.ItemIsEditable)
                self.results_table.setItem(row, 1, translation_item)
                
                # Notes
                notes_item = QTableWidgetItem(match["notes"])
                notes_item.setFlags(notes_item.flags() & ~Qt.ItemIsEditable)
                self.results_table.setItem(row, 2, notes_item)
        
        elif language_code in ["ko", "zh"]:
            # Multi-column format for Korean/Chinese
            if header:
                # Set columns based on the header
                self.results_table.setColumnCount(len(header))
                self.results_table.setHorizontalHeaderLabels(header)
                
                # Fill the table with data
                for row, match in enumerate(self.matches):
                    for col, column_name in enumerate(header):
                        if column_name in match:
                            item = QTableWidgetItem(match[column_name])
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make read-only
                            self.results_table.setItem(row, col, item)
            else:
                # Fallback to simpler display if no header info
                self.results_table.setColumnCount(3)
                self.results_table.setHorizontalHeaderLabels(["用語", "翻訳", "注釈"])
                
                # Just display basic info
                for row, match in enumerate(self.matches):
                    # For Korean glossary
                    if language_code == "ko":
                        term = match.get("ハングル", "")
                        translation = match.get("日本語", "")
                        notes = match.get("メモ", "")
                    # For Chinese glossary
                    else:
                        term = match.get("中文", "")
                        translation = match.get("日本語", "")
                        notes = match.get("メモ", "")
                    
                    # Set table items
                    self.results_table.setItem(row, 0, QTableWidgetItem(term))
                    self.results_table.setItem(row, 1, QTableWidgetItem(translation))
                    self.results_table.setItem(row, 2, QTableWidgetItem(notes))
        
        # Resize columns to fit content
        for i in range(self.results_table.columnCount() - 1):
            self.results_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        # Make the last column stretch
        self.results_table.horizontalHeader().setSectionResizeMode(
            self.results_table.columnCount() - 1, QHeaderView.Stretch)
    def copy_translation(self, index):
        """Copy the translation to clipboard when a row is double-clicked."""
        row = index.row()
        column = index.column()
        
        # Get current language
        language_code = self.language_combo.itemData(self.language_combo.currentIndex())
        
        # Get the text from the cell
        item = self.results_table.item(row, column)
        if item:
            text = item.text()
            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            
            # Show brief status message
            self.statusBar().showMessage(f"クリップボードに保存しました： {text}", 3000)        
    
    def show_about_dialog(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "辞書検索ツールについて",
            f"<h2>辞書検索ツール</h2>"
            f"<p>Version {APP_VERSION}</p>"
            "<p>特定の和訳が登録された業界用語をテキストから検索するツールです。</p>"
            "<p>© 2025 Kohei Takara</p>"
        )


def main():
    """Application entry point."""
    # Create the application
    app = QApplication(sys.argv)
    
    # Set application-wide font (optional)
    app.setFont(QFont("Segoe UI", 10))
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()