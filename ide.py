import sys
import os
import subprocess
import webbrowser
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QTreeView, QTabWidget, QToolBar,
    QSplitter, QTextEdit, QMessageBox, QFileDialog, QLabel,
    QPushButton, QInputDialog, QMenu, QSizePolicy, QListWidget, QListWidgetItem,
    QLineEdit, QStatusBar, QDockWidget, QToolButton
)
from PyQt6.QtCore import (
    Qt, QRect, QSize, QDir, QSettings, pyqtSignal, QProcess, QFileInfo,
    QCoreApplication, QFileSystemWatcher, QProcessEnvironment, QTimer,
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QPainter, QTextFormat,
    QSyntaxHighlighter, QTextCharFormat, QPalette,
    QFileSystemModel
)

import re
import git
import shlex
import time

# Global constant to signal restart
RESTART_ID = 1000

# Global map for file extension to language name
LANGUAGE_MAP = {
    '.py': 'Python', '.c': 'C', '.cpp': 'C++', '.java': 'Java', '.html': 'HTML',
    '.htm': 'HTML', '.css': 'CSS', '.js': 'Javascript', '.txt': 'Text'
}

# Define the standard indent size (4 spaces)
INDENT_SPACES = "    "

# --- IPC Constants (Only directory remains global) ---
IPC_DIR = Path(os.path.expanduser("~")) / ".venom_ipc"


# ============================================================================
# SYNTAX HIGHLIGHTER (STABLE VERSION)
# ============================================================================
class SyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for multiple programming languages"""

    multi_line_comment_state = 1
    c_comment_start = re.compile(r'/\*', re.DOTALL)
    c_comment_end = re.compile(r'\*/', re.DOTALL)
    python_string_start = re.compile(r'"""', re.DOTALL)
    python_string_end = re.compile(r'"""', re.DOTALL)

    def __init__(self, parent=None, language="python"):
        super().__init__(parent)
        self.language = language.lower()
        self.highlighting_rules = []
        self.formats = {}

        # Initialize patterns as attributes, even if None
        self.comment_start_pattern = None
        self.comment_end_pattern = None
        self.string_start_pattern = None
        self.string_end_pattern = None

        self.setup_rules()

    def setup_rules(self):
        """Setup syntax highlighting rules based on language"""
        self.formats['keyword'] = QTextCharFormat()
        self.formats['keyword'].setForeground(QColor("#569CD6"))
        self.formats['keyword'].setFontWeight(QFont.Weight.Bold)
        self.formats['string'] = QTextCharFormat()
        self.formats['string'].setForeground(QColor("#CE9178"))
        self.formats['comment'] = QTextCharFormat()
        self.formats['comment'].setForeground(QColor("#6A9955"))
        self.formats['comment'].setFontItalic(True)
        self.formats['number'] = QTextCharFormat()
        self.formats['number'].setForeground(QColor("#B5CEA8"))
        self.formats['function'] = QTextCharFormat()
        self.formats['function'].setForeground(QColor("#DCDCAA"))
        self.formats['class'] = QTextCharFormat()
        self.formats['class'].setForeground(QColor("#4EC9B0"))
        self.formats['css_property'] = QTextCharFormat()
        self.formats['css_property'].setForeground(QColor("#C586C0"))
        self.formats['js_constant'] = QTextCharFormat()
        self.formats['js_constant'].setForeground(QColor("#00BFFF"))

        keyword_format = self.formats['keyword']

        keywords = {
            "python": ["and", "as", "assert", "break", "class", "continue", "def", "del", "elif", "else", "except",
                       "False", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "None",
                       "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while", "with", "yield",
                       "async", "await"],
            "c": ["auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum",
                  "extern", "float", "for", "goto", "if", "int", "long", "register", "return", "short", "signed",
                  "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while"],
            "c++": ["alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor", "bool", "break", "case",
                    "catch", "char", "class", "compl", "const", "constexpr", "const_cast", "continue", "decltype",
                    "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit", "export", "extern",
                    "false", "float", "for", "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace",
                    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected",
                    "public", "register", "reinterpret_cast", "return", "short", "signed", "sizeof", "static",
                    "static_assert", "static_cast", "struct", "switch", "template", "this", "thread_local", "throw",
                    "true", "try", "typedef", "typeid", "typename", "union", "unsigned", "using", "virtual", "void",
                    "volatile", "wchar_t", "while", "xor"],
            "java": ["abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
                     "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float",
                     "for", "goto", "if", "implements", "instanceof", "int", "interface", "long", "native", "new",
                     "package", "private", "protected", "public", "return", "short", "static", "strictfp", "super",
                     "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile",
                     "while"],
            "html": ["html", "head", "body", "title", "meta", "link", "script", "style", "div", "span", "p", "a", "img",
                     "ul", "ol", "li", "table", "tr", "td", "th", "form", "input", "button", "select", "option"],
            "javascript": ["var", "let", "const", "if", "else", "for", "while", "function", "return", "class", "this",
                           "new", "import", "export", "try", "catch", "finally", "switch", "case", "break", "default",
                           "await", "async", "of", "in", "null", "undefined", "true", "false"],
            "css": ["@media", "@keyframes", "!important", "all", "auto", "inherit", "initial", "unset"],
            "text": []
        }
        css_properties = ["color", "background-color", "font-size", "width", "height", "margin", "padding", "border",
                          "display", "position", "float"]
        lang_keywords = keywords.get(self.language, keywords["python"])

        for word in lang_keywords:
            pattern = f"\\b{word}\\b"
            if self.language == "javascript" and word in ["null", "undefined", "true", "false", "var", "let", "const"]:
                self.highlighting_rules.append((re.compile(pattern, re.UNICODE), self.formats['js_constant']))
            else:
                self.highlighting_rules.append((re.compile(pattern, re.UNICODE), keyword_format))

        if self.language == "css":
            for prop in css_properties:
                pattern = f"\\b{prop}\\b"
                self.highlighting_rules.append((re.compile(pattern, re.UNICODE), self.formats['css_property']))

        if self.language in ["python", "java", "c++"]:
            self.highlighting_rules.append((re.compile(r'\bclass\s+(\w+)', re.UNICODE), self.formats['class']))
            self.highlighting_rules.append((re.compile(r'\bdef\s+(\w+)', re.UNICODE), self.formats['function']))
            self.highlighting_rules.append((re.compile(r'\b[A-Z][a-zA-Z0-9_]*\b', re.UNICODE), self.formats['class']))
        elif self.language == "javascript":
            self.highlighting_rules.append((re.compile(r'\b(function)\s+(\w+)', re.UNICODE), self.formats['function']))

        self.highlighting_rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"', re.UNICODE), self.formats['string']))
        self.highlighting_rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'", re.UNICODE), self.formats['string']))

        self.highlighting_rules.append((re.compile(r'\b\d+\.?\d*\b', re.UNICODE), self.formats['number']))

        if self.language == "python":
            self.highlighting_rules.append((re.compile(r'#[^\n]*', re.UNICODE), self.formats['comment']))
            self.comment_start_pattern = None  # Single line comments don't need multi-line check
            self.comment_end_pattern = None
            self.string_start_pattern = self.python_string_start
            self.string_end_pattern = self.python_string_end
        elif self.language in ["c", "c++", "java", "javascript", "css"]:
            self.highlighting_rules.append((re.compile(r'//[^\n]*', re.UNICODE), self.formats['comment']))
            self.comment_start_pattern = self.c_comment_start
            self.comment_end_pattern = self.c_comment_end
            self.string_start_pattern = None
            self.string_end_pattern = None
        else:
            self.comment_start_pattern = None
            self.comment_end_pattern = None
            self.string_start_pattern = None
            self.string_end_pattern = None

    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text, handling multi-line comments/strings"""

        if self.previousBlockState() != self.multi_line_comment_state:
            for pattern, fmt in self.highlighting_rules:
                for match in pattern.finditer(text):
                    self.setFormat(match.start(), match.end() - match.start(), fmt)

        self.setCurrentBlockState(0)

        # --- Multi-line Block Handler (Comments and Strings) ---

        # Determine patterns and format based on state/language
        start_pattern = None
        end_pattern = None
        fmt = None

        if self.language == "python":
            start_pattern = self.string_start_pattern
            end_pattern = self.string_end_pattern
            fmt = self.formats.get('string')
        elif self.comment_start_pattern and self.comment_end_pattern:
            start_pattern = self.comment_start_pattern
            end_pattern = self.comment_end_pattern
            fmt = self.formats.get('comment')

        if not start_pattern or not end_pattern:
            return

        start_index = 0
        is_in_block = (self.previousBlockState() == self.multi_line_comment_state)

        while start_index < len(text):

            if is_in_block:
                end_match = end_pattern.search(text, start_index)

                if end_match:
                    length = end_match.end() - start_index
                    self.setFormat(start_index, length, fmt)
                    start_index = end_match.end()
                    is_in_block = False
                    continue
                else:
                    self.setFormat(start_index, len(text) - start_index, fmt)
                    self.setCurrentBlockState(self.multi_line_comment_state)
                    break

            else:
                start_match = start_pattern.search(text, start_index)

                if start_match:
                    start_index = start_match.start()
                    is_in_block = True
                    continue
                else:
                    break

        if is_in_block:
            self.setCurrentBlockState(self.multi_line_comment_state)
        else:
            self.setCurrentBlockState(0)
        # --- End Multi-line Block Handler ---


# ============================================================================
# LINE NUMBER AREA
# ============================================================================
class LineNumberArea(QWidget):
    """Widget to display line numbers alongside the code editor"""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


# ============================================================================
# CODE EDITOR (MODIFIED FOR AI COMPLETION)
# ============================================================================
class CodeEditor(QPlainTextEdit):
    """Code editor with line numbers, syntax highlighting, and auto-indentation"""

    # Signal sent to IDEWindow to start the request
    request_ai_completion = pyqtSignal(str, str)  # (file_path, context)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.language = "python"
        self.highlighter = None
        self.file_path = None

        self.setup_editor()

        self.ai_suggestion = ""
        self.ai_label = QLabel(self)
        self.ai_label.hide()
        self.ai_label.setStyleSheet("color: #6A9955; font-style: italic; background-color: transparent;")
        self.ai_label.setFont(self.font())

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._text_changed_for_ai)

        self.update_line_number_area_width(0)

    def setup_editor(self):
        """Configure editor appearance and behavior"""
        # UNIFIED FONT: Use "Arial" or generic Monospace
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Set default text color based on theme
        main_window = self.parentWidget().parentWidget() if self.parentWidget() else None
        if main_window and hasattr(main_window, 'is_dark_mode'):
            palette = self.palette()
            if main_window.is_dark_mode:
                palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
            else:
                palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
            self.setPalette(palette)

    def set_language(self, language):
        """Change syntax highlighting language"""
        self.language = language
        if self.highlighter:
            self.highlighter.setDocument(None)
        self.highlighter = SyntaxHighlighter(self.document(), language)
        self.highlight_current_line()

    def line_number_area_width(self):
        """Calculate width needed for line numbers"""
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        """Update the width of line number area"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update line number area on scroll"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(),
                                         self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
        self._position_ai_label()

    def line_number_area_paint_event(self, event):
        """Paint line numbers"""
        painter = QPainter(self.line_number_area)

        main_window = self.parentWidget().parentWidget() if self.parentWidget() else None
        is_dark_mode = main_window and hasattr(main_window, 'is_dark_mode') and main_window.is_dark_mode

        if is_dark_mode:
            painter.fillRect(event.rect(), QColor("#1E1E1E"))
            text_color = QColor("#858585")
        else:
            painter.fillRect(event.rect(), QColor("#F0F0F0"))
            text_color = QColor("#666666")

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(text_color)
                painter.drawText(0, top, self.line_number_area.width() - 5,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        """Highlight the current line and ensure text remains readable."""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            main_window = self.parentWidget().parentWidget() if self.parentWidget() else None
            is_dark_mode = main_window and hasattr(main_window, 'is_dark_mode') and main_window.is_dark_mode

            if is_dark_mode:
                line_color = QColor("#2A323A")
                text_color = QColor("#FFFFFF")
            else:
                line_color = QColor("#E8F2FF")
                text_color = QColor("#000000")

            selection.format.setBackground(line_color)
            selection.format.setForeground(text_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    # --- NEW/MODIFIED: AI COMPLETION LOGIC ---
    def _text_changed_for_ai(self):
        """Triggers AI completion request after a brief delay."""
        self.ai_suggestion = ""
        self.ai_label.hide()

        # Use a short delay for smooth typing experience
        QTimer.singleShot(400, self._request_completion)

    def _request_completion(self):
        """Emits the signal to the IDEWindow to ask the VenomForge Assistant for a suggestion."""
        cursor = self.textCursor()

        # Pass the current editor instance (self) to the IDEWindow to get the IPC paths
        ide_window = self.parentWidget().parentWidget() if self.parentWidget() else None

        if cursor.atBlockEnd() and self.file_path and ide_window and hasattr(ide_window, 'completion_file'):

            # --- Check if completion file exists before writing ---
            if ide_window.completion_file.exists():
                return
            # ------------------------------------------------------------------

            current_line_text = cursor.block().text()

            # Only request if the current line looks like it needs completion (non-empty, ending in space/punctuation)
            if current_line_text and (
                    current_line_text[-1].isspace() or current_line_text[-1] in ['.', '(', '=', ':', '['] or len(
                current_line_text.strip()) > 3):

                context = ""
                block = cursor.block().previous()
                # Get up to 5 preceding lines for context
                for i in range(5):
                    if block.isValid():
                        context = block.text() + "\n" + context
                        block = block.previous()
                    else:
                        break
                context += current_line_text

                # Emit signal to IDEWindow to write the IPC request file
                self.request_ai_completion.emit(self.file_path, context)

    def display_ai_suggestion(self, suggestion):
        """Called by IDEWindow to show the AI suggestion (receives via IPC polling)."""
        # Ensure we only show suggestions if the cursor is at the right place and the editor is focused
        if not self.hasFocus():
            return

        # Check if the text has changed since the request was sent (i.e., user typed more)
        cursor = self.textCursor()
        current_line_text = cursor.block().text().strip()
        if not current_line_text:
            return

        self.ai_suggestion = suggestion.strip()

        if self.ai_suggestion and self.ai_suggestion not in ["# AI Error", "# Gemini not configured", " "]:
            # Only display the first line of code if it's not a filler/error
            display_text = self.ai_suggestion.split('\n')[0].strip()
            self.ai_label.setText(display_text)
            self.ai_label.show()
            self._position_ai_label()
        else:
            self.ai_suggestion = ""
            self.ai_label.hide()

    def _position_ai_label(self):
        """Positions the AI suggestion label at the cursor."""
        cursor = self.textCursor()
        rect = self.cursorRect(cursor)

        line_text = cursor.block().text()
        text_width = self.fontMetrics().horizontalAdvance(line_text)

        # Position label just after the typed text, relative to the viewport + line number area width
        # Adjust for horizontal scrolling
        x = rect.left() + text_width - self.horizontalScrollBar().value() + self.line_number_area_width()
        y = rect.top() - self.verticalScrollBar().value()

        self.ai_label.move(x, y)
        self.ai_label.adjustSize()

    def keyPressEvent(self, event):
        """Handle key press events for auto-indentation and AI acceptance."""

        # 1. ACCEPT AI COMPLETION (Tab key)
        if event.key() == Qt.Key.Key_Tab and self.ai_suggestion:
            event.accept()

            self.insertPlainText(self.ai_suggestion)

            self.ai_suggestion = ""
            self.ai_label.hide()
            return

        # 2. Discard AI suggestion on any other keypress
        if self.ai_suggestion and event.key() != Qt.Key.Key_Tab:
            self.ai_suggestion = ""
            self.ai_label.hide()

        cursor = self.textCursor()

        # --- 3. Auto-Pairing Logic ---
        key_text = event.text()

        pairings = {
            '(': ')',
            '{': '}',
            '[': ']',
            '"': '"',
            "'": "'",
        }

        if key_text in pairings:
            closing_char = pairings[key_text]

            if key_text in [')', '}', ']', '"', "'"]:
                cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, 1)
                next_char = cursor.selectedText()
                cursor.clearSelection()

                if next_char == key_text:
                    cursor.movePosition(cursor.MoveOperation.Right)
                    self.setTextCursor(cursor)
                    event.accept()
                    return

            if key_text in ['(', '{', '[', '"', "'"]:
                self.insertPlainText(key_text + closing_char)
                cursor.movePosition(cursor.MoveOperation.Left)
                self.setTextCursor(cursor)
                event.accept()
                return

        # --- 4. Tab Key Logic (If not accepting AI) ---
        elif event.key() == Qt.Key.Key_Tab:
            self.insertPlainText(INDENT_SPACES)
            event.accept()
            return

        # --- 5. Enter/Return Key Logic (Smart Indentation) ---
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            cursor.select(cursor.SelectionType.LineUnderCursor)
            line = cursor.selectedText()
            line_stripped = line.lstrip()
            current_indent_level = len(line) - len(line_stripped)

            super().keyPressEvent(event)
            cursor = self.textCursor()

            new_indentation = INDENT_SPACES * (current_indent_level // len(INDENT_SPACES))
            extra_indent = ""

            if self.language == "python" and line_stripped.endswith(":"):
                extra_indent = INDENT_SPACES
            elif line_stripped.endswith('{') or line_stripped.endswith('{ '):
                extra_indent = INDENT_SPACES

            self.insertPlainText(new_indentation + extra_indent)
            event.accept()
            return

        # --- 6. Default Handling ---
        super().keyPressEvent(event)


# ============================================================================
# INTERACTIVE CONSOLE
# ============================================================================
class InteractiveConsole(QTextEdit):
    """
    Custom QTextEdit that sends input to the parent process on Enter press.
    """
    input_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleWidget")  # For QSS targeting
        self.setReadOnly(True)
        self.input_start_pos = None
        self.setFont(QFont("Monospace", 10))
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        main_window = self.parentWidget().parentWidget() if self.parentWidget() else None

        # Initial color setup based on theme (will be updated by apply_theme)
        if main_window and hasattr(main_window, 'is_dark_mode') and main_window.is_dark_mode:
            self.setTextColor(QColor("#D4D4D4"))
        else:
            self.setTextColor(QColor("#000000"))

    def set_prompt(self, prompt=""):
        """Append a prompt and set the cursor position for user input."""
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)

        self.insertPlainText(prompt)
        self.input_start_pos = self.textCursor().position()
        self.setReadOnly(False)
        self.ensureCursorVisible()

    def append(self, text):
        """Append text and ensure the read-only section is preserved."""
        was_read_only = self.isReadOnly()
        self.setReadOnly(False)

        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.insertPlainText(text)

        if not was_read_only and self.input_start_pos is not None:
            self.setReadOnly(False)
            cursor.movePosition(cursor.MoveOperation.End)
            self.setTextCursor(cursor)
        else:
            self.setReadOnly(True)
            self.moveCursor(self.textCursor().MoveOperation.End)
            self.ensureCursorVisible()

    def keyPressEvent(self, event):
        """Handle key press to capture user input."""
        if self.isReadOnly():
            if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                parent_window = self.parentWidget()
                ide_window = None
                while parent_window:
                    if isinstance(parent_window, QMainWindow):
                        ide_window = parent_window
                        break
                    parent_window = parent_window.parentWidget()

                if ide_window and hasattr(ide_window, 'process'):
                    process = ide_window.process
                    if process.state() == QProcess.ProcessState.Running:
                        process.terminate()
                        self.append("\n[Process terminated by user (Ctrl+C)]\n")
                    return

            super().keyPressEvent(event)
            return

        cursor = self.textCursor()

        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            cursor.movePosition(cursor.MoveOperation.Start, cursor.MoveMode.MoveAnchor)
            cursor.movePosition(cursor.MoveOperation.NextCharacter, cursor.MoveMode.MoveAnchor, self.input_start_pos)
            cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)

            input_text = cursor.selectedText()

            self.insertPlainText('\n')

            self.setReadOnly(True)
            self.input_start_pos = None

            self.input_ready.emit(input_text + '\n')

            event.accept()
            return

        elif event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key.Key_Left:
            if cursor.position() <= self.input_start_pos:
                event.ignore()
                return

        super().keyPressEvent(event)


# ============================================================================
# START SCREEN
# ============================================================================
class StartScreen(QWidget):
    """Initial screen with project options."""

    open_folder_requested = pyqtSignal()
    new_project_requested = pyqtSignal()

    def __init__(self, initial_dark_mode=True):
        super().__init__()
        self.setWindowTitle("Welcome to VenomForge Lab")
        self.is_dark_mode = initial_dark_mode
        self.settings = QSettings("VENOM_FORGE_LAB", "Settings")  # Use settings to save state

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------------------------------------------
        # Floating Toggle Button setup
        # ----------------------------------------------------
        self.theme_btn = QPushButton("🌚", self)
        self.theme_btn.setObjectName("StartScreenThemeButton")
        self.theme_btn.setFixedSize(QSize(40, 40))
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Layout for central content
        content_container = QWidget()
        content_container.setFixedSize(550, 250)

        content_layout = QVBoxLayout(content_container)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(25)
        content_layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("VenomForge Lab")
        title_font = QFont("Arial", 28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("StartScreenTitle")
        content_layout.addWidget(title)

        h_layout = QHBoxLayout()
        h_layout.setSpacing(20)

        open_btn = QPushButton("📂 Open Existing Folder")
        open_btn.setFixedSize(220, 50)
        open_btn.setFont(QFont("Arial", 11))
        open_btn.setObjectName("StartButton")
        open_btn.clicked.connect(self.open_folder_requested.emit)
        h_layout.addWidget(open_btn)

        new_btn = QPushButton("✨ Start New Project")
        new_btn.setFixedSize(220, 50)
        new_btn.setFont(QFont("Arial", 11))
        new_btn.setObjectName("StartButton")
        new_btn.clicked.connect(self.new_project_requested.emit)
        h_layout.addWidget(new_btn)

        content_layout.addLayout(h_layout)

        main_layout.addWidget(content_container)

        # Apply initial theme
        self.apply_theme()
        QTimer.singleShot(50, self.position_toggle_button)

    def position_toggle_button(self):
        """Positions the floating button in the top-right corner."""
        button_size = self.theme_btn.width()
        right_margin = 20
        top_margin = 20  # Keep a safe margin from the window top

        new_x = self.width() - button_size - right_margin
        new_y = top_margin

        self.theme_btn.move(new_x, new_y)
        self.theme_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_toggle_button()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.settings.setValue("dark_mode", self.is_dark_mode)
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            # Dark Mode Colors (Matching IDE)
            PRIMARY_ACCENT = "#9B70FF"
            BACKGROUND_COLOR = "#12121e"  # Deep Dark Blue/Purple Background
            FOREGROUND_COLOR = "#EBE9F5"  # Light Text
            PANEL_COLOR = "#2D2D30"  # Central card color

            # Button Colors (Solid Dark Theme)
            BTN_BG = "#7F5EFA"
            BTN_HOVER_BG = PRIMARY_ACCENT

            self.theme_btn.setText("🌝")
        else:
            # Light Mode Colors (Matching IDE/Therapy App)
            PRIMARY_ACCENT = "#7F5EFA"  # Core Purple Accent
            BACKGROUND_COLOR = "#FFFFFF"
            FOREGROUND_COLOR = "#2F2F4F"
            PANEL_COLOR = "#FFFFFF"

            # 🔴 START SCREEN GRADIENT BUTTON THEME
            # Mint/Teal to Purple Gradient (Matching Therapy Session Button)
            BTN_START_COLOR = "#A7F8DC"
            BTN_END_COLOR = PRIMARY_ACCENT
            BTN_HOVER_BG = "#9B70FF"  # Lighter purple for hover

            self.theme_btn.setText("🌚")

        # --- QSS STYLING ---

        # Determine BUTTON BACKGROUND STYLE based on theme (Gradient in Light, Solid in Dark)
        button_style = ""
        if not self.is_dark_mode:
            # Light Mode Gradient (Teal/Mint to Purple)
            button_style = f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 {BTN_START_COLOR}, stop:1 {BTN_END_COLOR});
            """
        else:
            # Dark Mode (Solid Purple)
            button_style = f"background-color: {BTN_BG};"

        self.setStyleSheet(f"""
            /* Full screen background */
            StartScreen {{
                background-color: {BACKGROUND_COLOR};
            }}

            /* Central content panel styling */
            StartScreen > QWidget {{
                background-color: {PANEL_COLOR};
                border-radius: 10px;
                /* 🔴 FIX: Change border to primary purple accent */
                border: 1px solid {PRIMARY_ACCENT}; 
            }}

            /* Title styling */
            #StartScreenTitle {{
                color: {PRIMARY_ACCENT};
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 32px;
                font-weight: 900;
                letter-spacing: 2px;
                margin-bottom: 10px;
            }}

            /* Button styling - Matching Therapy Tab look */
            QPushButton#StartButton {{
                {button_style}
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }}
            /* Ensure hover is a lighter version of purple */
            QPushButton#StartButton:hover {{
                background-color: {BTN_HOVER_BG}; /* Use lighter purple hover for consistency */
                opacity: 0.9;
            }}

            /* Standard Labels */
            QLabel {{ color: {FOREGROUND_COLOR}; }}

            /* Toggle Button Styling */
            #StartScreenThemeButton {{
                background: {PRIMARY_ACCENT};
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 18px;
                font-weight: bold;
            }}
            #StartScreenThemeButton:hover {{
                background: {PRIMARY_ACCENT}CC;
            }}
        """)


# ============================================================================
# TERMINAL WIDGET (PLACEHOLDER)
# ============================================================================
class TerminalWidget(QTextEdit):
    input_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Monospace", 10))
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setText(
            "Terminal (Requires integration with external PTY libraries like pyte/pyte-ng to be fully interactive.)\n$ ")
        self.input_start_pos = len(self.toPlainText())

        self.setReadOnly(False)
        self.setTextCursor(self.textCursor())

        main_window = self.parentWidget().parentWidget() if self.parentWidget() else None
        if main_window and hasattr(main_window, 'is_dark_mode'):
            color = QColor("#D4D4D4") if main_window.is_dark_mode else QColor("#000000")
            self.setTextColor(color)

    def keyPressEvent(self, event):
        cursor = self.textCursor()

        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Note: This is a placeholder for actual terminal input handling
            command = self.toPlainText()[self.input_start_pos:]
            self.append_output('\n$ ')
            self.input_ready.emit(command.strip())  # Emitting to show functionality

            self.input_start_pos = len(self.toPlainText())
            self.setReadOnly(False)
            event.accept()
            return

        elif event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key.Key_Left:
            if cursor.position() <= self.input_start_pos:
                event.ignore()
                return

        super().keyPressEvent(event)

    def append_output(self, text):
        """Append text and ensure the read-only section is preserved."""
        self.setReadOnly(False)

        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.insertPlainText(text)

        self.setReadOnly(False)
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.ensureCursorVisible()


# ============================================================================
# DEBUGGER WIDGET (PLACEHOLDER)
# ============================================================================
class DebuggerWindow(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Debugger - Watch Window", parent)
        self.setWidget(QListWidget())
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.setVisible(False)

    def update_variables(self, variables):
        self.widget().clear()
        for name, value in variables.items():
            QListWidgetItem(f"{name}: {value}", self.widget())


# ============================================================================
# GIT PANEL WIDGET
# ============================================================================
class GitPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.repo = None

        layout = QVBoxLayout(self)

        # 1. Status Label
        self.status_label = QLabel("GIT: Not Loaded")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        # 2. Staged/Unstaged Files List
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

        # 3. Input/Action Bar
        action_bar = QHBoxLayout()
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("Enter commit message...")
        self.commit_btn = QPushButton("Commit All")
        self.commit_btn.clicked.connect(self.commit_changes)
        action_bar.addWidget(self.commit_message_input)
        action_bar.addWidget(self.commit_btn)
        layout.addLayout(action_bar)

        # 4. Pull/Push Buttons
        pull_push_bar = QHBoxLayout()
        self.pull_btn = QPushButton("Pull")
        self.pull_btn.clicked.connect(lambda: self.git_remote_action("pull"))
        self.push_btn = QPushButton("Push")
        self.push_btn.clicked.connect(lambda: self.git_remote_action("push"))
        pull_push_bar.addWidget(self.pull_btn)
        pull_push_bar.addWidget(self.push_btn)
        layout.addLayout(pull_push_bar)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)

    def load_repo(self, path):
        try:
            self.repo = git.Repo(path)
            self.update_status()
        except git.InvalidGitRepositoryError:
            self.repo = None
            self.status_label.setText("GIT: Not a Repository")
            self.file_list.clear()

    def update_status(self):
        if not self.repo:
            if hasattr(self.main_window, 'git_status_label'):
                self.main_window.git_status_label.setText("Git: No Project")
            return

        try:
            changed_files = []

            # Unstaged changes (working tree vs index)
            for diff in self.repo.index.diff(None):
                status_char = ''
                if diff.change_type == 'M':
                    status_char = 'M'
                elif diff.change_type == 'D':
                    status_char = 'D'
                elif diff.change_type == 'A':
                    status_char = 'A'

                if status_char:
                    changed_files.append(f"{status_char}: {diff.a_path or diff.b_path} (Unstaged)")

            # Staged changes (index vs HEAD)
            for diff in self.repo.index.diff('HEAD'):
                status_char = ''
                if diff.change_type == 'M':
                    status_char = 'M'
                elif diff.change_type == 'A':
                    status_char = 'A'
                elif diff.change_type == 'D':
                    status_char = 'D'

                if status_char:
                    changed_files.append(f"{status_char}: {diff.a_path or diff.b_path} (Staged)")

            for file in self.repo.untracked_files:
                changed_files.append(f"U: {file} (Untracked)")

            branch = self.repo.active_branch.name
            is_dirty = self.repo.is_dirty(untracked_files=True)
            status_text = f"Branch: {branch} ({'Uncommitted Changes' if is_dirty else 'Clean'})"
            self.status_label.setText(status_text)
            if hasattr(self.main_window, 'git_status_label'):
                # FIX APPLIED: Corrected conditional expression syntax
                self.main_window.git_status_label.setText(f"Git: {branch} | {'⚠' if is_dirty else '✓'}")

            self.file_list.clear()
            for file in changed_files:
                QListWidgetItem(file, self.file_list)

        except Exception as e:
            self.status_label.setText(f"GIT Error: {e.__class__.__name__}")
            if hasattr(self.main_window, 'console'):
                self.main_window.console.append(f"❌ Git Status Error: {e}\n")

    def commit_changes(self):
        if not self.repo: return
        msg = self.commit_message_input.text()
        if not msg:
            QMessageBox.warning(self, "Commit Failed", "Please enter a commit message.")
            return

        try:
            self.repo.index.add('-A')
            self.repo.index.commit(msg)
            if hasattr(self.main_window, 'console'):
                self.main_window.console.append(f"✓ Committed changes: {msg}\n")
            self.commit_message_input.clear()
            self.update_status()
        except Exception as e:
            if hasattr(self.main_window, 'console'):
                self.main_window.console.append(f"❌ Commit Failed: {e}\n")

    def git_remote_action(self, action):
        if not self.repo: return
        try:
            if action == "pull":
                if hasattr(self.main_window, 'console'):
                    self.main_window.console.append("◈ Pulling from remote...\n")
                origin = self.repo.remotes.origin
                origin.pull()
                if hasattr(self.main_window, 'console'):
                    self.main_window.console.append("✓ Pull successful.\n")
            elif action == "push":
                if hasattr(self.main_window, 'console'):
                    self.main_window.console.append("◈ Pushing to remote...\n")
                origin = self.repo.remotes.origin
                origin.push()
                if hasattr(self.main_window, 'console'):
                    self.main_window.console.append("✓ Push successful.\n")
            self.update_status()
        except Exception as e:
            if hasattr(self.main_window, 'console'):
                self.main_window.console.append(f"❌ Git {action.capitalize()} Failed: {e}\n")


# ============================================================================
# MAIN IDE WINDOW
# ============================================================================
class IDEWindow(QMainWindow):
    """Main IDE window with all components"""

    # Signals for AI features (to communicate via IPC)
    request_ai_refactor = pyqtSignal(str, str, str)
    request_ai_test_gen = pyqtSignal(str, str)

    def __init__(self, project_path=None):
        super().__init__()
        self.current_file = None
        # Default to dark mode for the IDE
        self.is_dark_mode = True
        self.settings = QSettings("VENOM_FORGE_LAB", "Settings")
        self.start_screen = None
        self.initial_project_path = project_path

        # --- Ensure IPC Directory Exists ---
        IPC_DIR.mkdir(parents=True, exist_ok=True)
        # -----------------------------------

        # --- IPC Instance Variables ---
        self.ipc_dir = IPC_DIR
        self.completion_file = self.ipc_dir / "completion_request.json"
        self.completion_response_file = self.ipc_dir / "completion_response.txt"
        self.request_file = self.ipc_dir / "agent_request.json"
        self.response_file = self.ipc_dir / "agent_response.json"
        # -------------------------------------------

        self.project_root_name = "Project"

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.handle_file_system_change)
        self.watcher.directoryChanged.connect(self.handle_file_system_change)
        self.open_file_paths = {}

        # Main QProcess for running the user's program
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_process_finished)

        # QProcess for running compilation asynchronously
        self.compile_process = QProcess(self)
        self.compile_process.readyReadStandardOutput.connect(self.handle_stdout)
        self.compile_process.readyReadStandardError.connect(self.handle_stderr)
        self.compile_process.finished.connect(self.handle_compilation_finished)
        self._pending_run_details = None

        self.debugger_dock = DebuggerWindow(self)
        self.git_panel = GitPanel(self)

        # Initialize floating theme button as None before init_ui
        self.theme_btn = None

        self.init_ui()
        self.apply_theme()

        # --- IPC Polling Timer Setup ---
        self._start_ipc_polling()
        # ------------------------------------

        self.status_bar.showMessage(f"IDE Initialized. Load Project or Start New.", 5000)
        self.hide()
        self.show_startup_logic()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Call the new general positioning helper
        self._position_global_elements()

    def _position_global_elements(self):
        """Position floating theme button (top-right) and console button (bottom-right)."""
        # --- Theme Button (Top-Right) ---
        if hasattr(self, 'theme_btn') and self.theme_btn:
            button_size = self.theme_btn.width()

            # The right margin should match the console button's margin
            right_margin = 20

            # Ensure the button is just inside the window border (5px from the top)
            top_margin = 5

            new_x = self.width() - button_size - right_margin
            new_y = top_margin

            self.theme_btn.move(new_x, new_y)
            self.theme_btn.raise_()

        # --- Console Button (Bottom-Right) ---
        if hasattr(self, 'console_floating_btn'):
            self._position_console_floating_button()

    def _position_console_floating_button(self):
        """Position floating console button relative to the window's bottom-right corner."""
        if not hasattr(self, 'console_floating_btn'):
            return
        margin = 20
        w = self.console_floating_btn.width()
        h = self.console_floating_btn.height()
        # fallback if width/height are 0 for some reason
        if w == 0 or h == 0:
            w, h = 110, 36
        x = max(10, self.width() - w - margin)
        y = max(10, self.height() - h - margin)
        self.console_floating_btn.move(x, y)
        self.console_floating_btn.raise_()

    def _start_ipc_polling(self):
        """Starts a persistent timer for checking AI responses."""
        # Completion polling should be faster than Agent polling
        self.completion_polling_timer = QTimer(self)
        self.completion_polling_timer.timeout.connect(self._handle_completion_response)
        self.completion_polling_timer.start(100)  # Check for completion response every 100ms

        self.agent_polling_timer = QTimer(self)
        self.agent_polling_timer.timeout.connect(self._handle_agent_response)
        self.agent_polling_timer.start(500)  # Check for agent response every 500ms
        self.console.append("✓ IPC polling started.\n")

    def _handle_completion_response(self):
        """
        Polls the IPC file for quick AI code completion responses
        and passes the result to the current CodeEditor.
        """
        if not self.completion_response_file.exists():
            return

        current_editor = self.editor_tabs.currentWidget()
        if not isinstance(current_editor, CodeEditor):
            return

        try:
            # 1. Read the response
            with open(self.completion_response_file, 'r', encoding='utf-8') as f:
                suggestion = f.read()

            # 2. Delete the response file to signal consumption
            self.completion_response_file.unlink()

            # 3. Pass the suggestion to the editor (which handles visibility)
            if suggestion:
                current_editor.display_ai_suggestion(suggestion)

        except FileNotFoundError:
            # File was read/deleted by another check in a tight loop, ignore.
            pass
        except Exception as e:
            self.console.append(f"❌ IPC Completion Read Error: {e}\n")
            if self.completion_response_file.exists():
                self.completion_response_file.unlink()  # Attempt to clear bad file

    def _handle_agent_response(self):
        """
        Polls the IPC file for long-running AI agentic responses (Refactor/Test Gen).
        """
        if not self.response_file.exists():
            return

        try:
            # 1. Read the response
            with open(self.response_file, 'r') as f:
                response_data = json.load(f)

            # 2. Delete the response file to signal consumption
            self.response_file.unlink()

            success = response_data.get('success', False)
            message = response_data.get('message', 'No message provided.')
            files = response_data.get('files', [])

            # 3. Display the result
            if success:
                self.console.append(f"✅ Agent Success: {message}\n")
                if files:
                    self.console.append("Files updated/created:\n")
                    for f in files:
                        self.console.append(f"  - {f}\n")

                # Force a file model refresh and Git status update
                self.file_model.setRootPath(self.file_model.rootPath())
                self.git_panel.update_status()

            else:
                self.console.append(f"❌ Agent Failed: {message}\n")

        except FileNotFoundError:
            # File was read/deleted by another check, ignore.
            pass
        except Exception as e:
            self.console.append(f"❌ IPC Agent Read Error: {e}\n")
            if self.response_file.exists():
                self.response_file.unlink()  # Attempt to clear bad file
        finally:
            # Reset input position regardless of success
            if hasattr(self, 'console') and self.console.input_start_pos is not None:
                self.console.input_start_pos = len(self.console.toPlainText())

    def toggle_console_visibility(self):
        """Opens or closes the console panel using the vertical splitter."""
        sizes = self.vertical_splitter.sizes()
        # ensure sizes always has at least two entries (Robustness fix)
        if len(sizes) < 2:
            total_height = self.vertical_splitter.height()
            restored_height = self.settings.value("console_height", 200, type=int)
            if restored_height > total_height * 0.8 or restored_height < 50: restored_height = int(total_height * 0.3)
            editor_size = total_height - restored_height
            console_size = restored_height
        else:
            editor_size = sizes[0]
            console_size = sizes[1]

        console_index = self.vertical_splitter.indexOf(self.console_tab_widget)
        if console_index == -1:
            return

        # Console is currently visible (size > 0)
        if console_size > 0:
            self.settings.setValue("console_height", console_size)
            self.vertical_splitter.setSizes([editor_size + console_size, 0])
            self.collapse_btn.setText("▲ Show Console")  # Change text to 'Show'
            self.collapse_btn.setStyleSheet(
                "padding: 2px 8px; border: none; color: #4EC9B0;")  # Accent color when hidden

            # --- FLOATING BUTTON UPDATE (Hidden state) ---
            if hasattr(self, 'console_floating_btn'):
                self.console_floating_btn.setText("Console ⬇")
                self.console_floating_btn.setObjectName("FloatingConsoleHidden")
                self.apply_theme()
            # ---------------------------------------------

        # Console is currently hidden (size is 0)
        else:
            restored_height = self.settings.value("console_height", 200, type=int)

            total_height = self.vertical_splitter.height()
            if restored_height > total_height * 0.8: restored_height = int(total_height * 0.3)
            if restored_height < 50: restored_height = 200

            new_editor_size = total_height - restored_height
            if new_editor_size < 100: new_editor_size = 100

            self.vertical_splitter.setSizes([new_editor_size, restored_height])
            self.collapse_btn.setText("▼ Hide Console")  # Change text back to 'Hide'
            self.collapse_btn.setStyleSheet(
                "padding: 2px 8px; border: none; font-weight: bold;")  # Default color when visible

            # --- FLOATING BUTTON UPDATE (Visible state) ---
            if hasattr(self, 'console_floating_btn'):
                self.console_floating_btn.setText("Console ⬆")
                self.console_floating_btn.setObjectName("FloatingConsoleVisible")
                self.apply_theme()
            # ----------------------------------------------

            current_widget_in_tab = self.console_tab_widget.currentWidget()
            if isinstance(current_widget_in_tab, InteractiveConsole):
                current_widget_in_tab.ensureCursorVisible()
            elif isinstance(current_widget_in_tab, TerminalWidget):
                current_widget_in_tab.setFocus()

    def create_file_explorer_pane(self):
        """Creates the File Explorer pane, including the project title, tree view."""

        file_pane = QWidget()
        layout = QVBoxLayout(file_pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.project_title_label = QLabel(self.project_root_name)
        self.project_title_label.setObjectName("ProjectTitleLabel")
        self.project_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.project_title_label.setTextFormat(Qt.TextFormat.RichText)

        self.project_title_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_title_label.customContextMenuRequested.connect(self.show_project_label_context_menu)
        layout.addWidget(self.project_title_label)

        self.file_explorer = QTreeView()
        self.file_model = QFileSystemModel()

        self.file_model.setRootPath(QDir.currentPath())

        self.file_explorer.setModel(self.file_model)
        self.file_explorer.setRootIndex(self.file_model.index(QDir.currentPath()))
        self.file_explorer.setColumnWidth(0, 200)
        self.file_explorer.setHeaderHidden(True)
        self.file_explorer.setStyleSheet("QTreeView { border: none; }")

        for i in range(1, 4):
            self.file_explorer.hideColumn(i)

        self.file_explorer.doubleClicked.connect(self.open_file_from_explorer)

        self.file_explorer.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_explorer.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.file_explorer)

        return file_pane

    def init_ui(self):
        self.setWindowTitle("VenomForge Lab")
        self.setGeometry(100, 100, 1400, 900)

        # Set unified font for the application
        app_font = QFont("Arial", 10)
        if "Arial" not in app_font.family():
            app_font = QFont(QApplication.font().family(), 10)

        self.setFont(app_font)

        # 1. Status Bar Setup (Removed "Made by Krish" label)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # -------------------------
        # Left Spacer (expands for alignment)
        # -------------------------
        left_spacer = QLabel("")
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_bar.addWidget(left_spacer)

        # -------------------------
        # Right Spacer (expands for alignment)
        # -------------------------
        right_spacer = QLabel("")
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_bar.addWidget(right_spacer)

        # -------------------------
        # Permanent widgets container (right side of status bar)
        # -------------------------
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        self.git_status_label = QLabel("Git: No Project")
        self.language_status_label = QLabel("Lang: Python")
        self.cursor_status_label = QLabel("Ln 1, Col 1")

        right_layout.addWidget(self.git_status_label)
        right_layout.addWidget(self.language_status_label)
        right_layout.addWidget(self.cursor_status_label)

        # Add right container as permanent widget
        self.status_bar.addPermanentWidget(right_container)

        # 2. Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.create_toolbar()

        # 3. Create main splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 4. Create Dock Widget and Git Panel (File Sidebar Tabs)
        self.file_explorer_pane = self.create_file_explorer_pane()

        self.file_sidebar_tabs = QTabWidget()
        self.file_sidebar_tabs.addTab(self.file_explorer_pane, QIcon(), "Files")
        self.file_sidebar_tabs.addTab(self.git_panel, QIcon(), "Git")
        self.file_sidebar_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.main_splitter.addWidget(self.file_sidebar_tabs)

        # 5. Create vertical splitter for editor and console
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)

        # 6. Create tab widget for editor
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_tab)
        self.editor_tabs.currentChanged.connect(self.on_tab_changed)
        self.vertical_splitter.addWidget(self.editor_tabs)

        # 7. Create console/output tab view
        self.create_console_view()
        self.vertical_splitter.addWidget(self.console_tab_widget)

        # Set splitter sizes
        self.vertical_splitter.setSizes([600, 200])

        self.main_splitter.addWidget(self.vertical_splitter)
        self.main_splitter.setSizes([250, 1150])

        main_layout.addWidget(self.main_splitter)

        # 8. Add Debugger Dock (Hidden by default)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.debugger_dock)

        # --- Floating Console Toggle Button (Bottom-Right) ---
        self.console_floating_btn = QPushButton("Console ⬆", self)
        self.console_floating_btn.setObjectName("FloatingConsoleVisible")
        self.console_floating_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.console_floating_btn.setFixedSize(110, 36)
        self.console_floating_btn.clicked.connect(self.toggle_console_visibility)
        self.console_floating_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.console_floating_btn.raise_()
        self.console_floating_btn.show()

        # --- FLOATING THEME TOGGLE BUTTON (TOP-RIGHT) ---
        self.theme_btn = QPushButton("🌚", self)
        self.theme_btn.setObjectName("themeButtonCircle")
        self.theme_btn.setFixedSize(QSize(40, 40))
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.theme_btn.raise_()
        self.theme_btn.show()
        # ------------------------------------------------

        # Position after the main window is shown (safe to use singleShot)
        QTimer.singleShot(0, lambda: self._position_global_elements())

        self.setup_shortcuts()

    def handle_file_system_change(self, path):
        if os.path.isdir(path):
            self.file_model.setRootPath(self.file_model.rootPath())
            if hasattr(self, 'console'):
                self.console.append(f"✓ Detected directory change in: {Path(path).name}\n")
            self.git_panel.update_status()
            return

        if path in self.open_file_paths:
            tab_index = self.open_file_paths[path]
            editor = self.editor_tabs.widget(tab_index)

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                if hasattr(self, 'console'):
                    self.console.append(
                        f"⚠️ Dynamic Reload Warning: File {Path(path).name} encoding error. Skipping live reload.\n")
                return
            except Exception as e:
                if hasattr(self, 'console'):
                    self.console.append(f"❌ Dynamic Reload Error on {Path(path).name}: {e}\n")
                return

            if editor.toPlainText() != content:
                cursor_pos = editor.textCursor().position()
                scroll_bar_pos = editor.verticalScrollBar().value()

                editor.setPlainText(content)

                cursor = editor.textCursor()
                cursor.setPosition(cursor_pos)
                editor.setTextCursor(cursor)
                editor.verticalScrollBar().setValue(scroll_bar_pos)

                if hasattr(self, 'console'):
                    self.console.append(f"🔄 Auto-reloaded: {Path(path).name}\n")
                editor.document().setModified(False)

                self.git_panel.update_status()

    def set_project_root(self, directory_path):
        """Sets the root directory for the file explorer and application."""
        directory_path = str(Path(directory_path).resolve())
        if os.path.isdir(directory_path):
            QDir.setCurrent(directory_path)

            self.file_model.setRootPath(directory_path)
            self.file_explorer.setRootIndex(self.file_model.index(directory_path))

            self.project_root_name = Path(directory_path).name
            self.project_title_label.setText(self.project_root_name)

            self.setWindowTitle(f"VenomForge Lab - [{self.project_root_name}]")
            self.settings.setValue("current_dir", directory_path)

            # FIX applied to ensure correct console access
            if hasattr(self, 'console'):
                self.console.append(f"Project opened: {directory_path}\n")

            # --- GIT INTEGRATION ---
            self.git_panel.load_repo(directory_path)

            # --- STATUS BAR ---
            self.status_bar.showMessage(f"Project: {self.project_root_name}", 5000)
            self.git_panel.update_status()
            # ---------------------------

            # --- DYNAMIC RELOAD: ADD PROJECT DIRECTORIES TO WATCHER ---
            old_paths = self.watcher.files() + self.watcher.directories()
            if old_paths:
                self.watcher.removePaths(old_paths)

            # Add all subdirectories and files to watcher recursively (up to a depth limit, implied by os.walk)
            for root, dirs, _ in os.walk(directory_path):
                self.watcher.addPath(root)
                for d in dirs:
                    self.watcher.addPath(os.path.join(root, d))
            if hasattr(self, 'console'):
                self.console.append("✓ File system watcher active.\n")
            # -----------------------------------------------------------

            self.show()
        else:
            if hasattr(self, 'console'):
                self.console.append("Warning: Could not set project directory.\n")

    def create_toolbar(self):
        """
        Create the toolbar with actions, following the new center/left/right organization.
        """
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # 1. LEFT CORNER (EXIT & DEBUG) - REORDERED AND SEPARATED

        exit_action = QAction(QIcon(), "🚪 Exit Project", self)
        exit_action.triggered.connect(self.exit_project)
        toolbar.addAction(exit_action)

        # 🔴 FIX APPLIED: Add vertical separator between Exit and Debug
        toolbar.addSeparator()

        debug_action = QAction(QIcon(), "🐛 Debug", self)
        debug_action.triggered.connect(self.toggle_debugger)
        toolbar.addAction(debug_action)

        toolbar.addSeparator()

        # 2. CENTER (TITLE)
        app_title = QLabel("VenomForge Lab")
        title_font = QFont("Arial", 12)
        title_font.setBold(True)
        app_title.setFont(title_font)
        app_title.setObjectName("AppTitleLabel")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the text visually

        # Spacer to push the title to the center
        empty_widget_left = QWidget()
        empty_widget_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(empty_widget_left)

        toolbar.addWidget(app_title)

        # Spacer to push the rest of the elements to the right
        empty_widget_right = QWidget()
        empty_widget_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(empty_widget_right)

        toolbar.addSeparator()

        # 3. RIGHT CORNER (RUN, AI ACTIONS)

        # Run Button
        run_action = QAction(QIcon(), "▶ Run", self)
        run_action.triggered.connect(self.run_code)
        toolbar.addAction(run_action)

        toolbar.addSeparator()

        # AI Actions Button
        ai_menu = QMenu(self)
        ai_refactor_action = QAction("⚡ Refactor/Optimize Code", self)
        ai_refactor_action.triggered.connect(self.prompt_ai_refactor)
        ai_menu.addAction(ai_refactor_action)

        ai_test_action = QAction("🧪 Generate Unit Tests", self)
        ai_test_action.triggered.connect(self.prompt_ai_test_generation)
        ai_menu.addAction(ai_test_action)

        ai_button = QToolButton(self)
        ai_button.setText("🧠 AI Actions")
        ai_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        ai_button.setMenu(ai_menu)
        toolbar.addWidget(ai_button)

        # 🔴 FIX APPLIED: Add a fixed spacer to create space for the floating theme toggle.
        fixed_spacer_right = QWidget()
        fixed_spacer_right.setFixedWidth(55)
        toolbar.addWidget(fixed_spacer_right)

        # Note: The Theme Toggle button remains a floating button positioned by _position_global_elements()

    def prompt_ai_refactor(self):
        current_editor = self.editor_tabs.currentWidget()
        if not current_editor or not hasattr(current_editor, 'file_path'):
            QMessageBox.warning(self, "AI Refactor", "Please open a file to refactor.")
            return
        if self.save_file() is None:
            self.console.append("❌ Refactor Aborted: Please save the current file.\n")
            return

        request, ok = QInputDialog.getText(
            self, "AI Refactor Request",
            "What specific refactoring/optimization should the AI perform?",
            text="Make this code more Pythonic and optimize the main loop."
        )

        if ok and request:
            self.console.append("◈ Agentic Refactoring Request Sent to VenomForge Assistant (via IPC)....\n")

            # Write trigger file
            try:
                with open(self.request_file, 'w') as f:
                    json.dump({"type": "refactor", "file_path": current_editor.file_path, "request": request}, f)
            except Exception as e:
                self.console.append(f"❌ Failed to write refactor request IPC file: {e}\n")

    def prompt_ai_test_generation(self):
        current_editor = self.editor_tabs.currentWidget()
        if not current_editor or not hasattr(current_editor, 'file_path'):
            QMessageBox.warning(self, "AI Test Generation", "Please open a file to generate tests for.")
            return
        if self.save_file() is None:
            self.console.append("❌ Test Gen Aborted: Please save the current file.\n")
            return

        self.console.append("◈ Agentic Unit Test Generation Request Sent to VenomForge Assistant (via IPC)....\n")

        # Write trigger file (using a placeholder request detail)
        try:
            with open(self.request_file, 'w') as f:
                json.dump({"type": "test_gen", "file_path": current_editor.file_path,
                           "request": "Generate comprehensive unit tests for all functions."}, f)
        except Exception as e:
            self.console.append(f"❌ Failed to write test generation request IPC file: {e}\n")

    def toggle_debugger(self):
        """Shows/hides the debugger dock."""
        self.debugger_dock.setVisible(not self.debugger_dock.isVisible())
        self.console.append(f"Debugger {'Enabled' if self.debugger_dock.isVisible() else 'Disabled'}.\n")

    def create_console_view(self):
        """Create the bottom tab widget for Console, Terminal, and Git Log."""

        self.console_tab_widget = QTabWidget()
        self.console_tab_widget.setObjectName("ConsoleTabWidget")

        # 1. Output Console (for run results)
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(5, 5, 5, 5)
        self.console = InteractiveConsole(self)
        self.console.input_ready.connect(self.write_to_process_stdin)
        output_layout.addWidget(self.console)
        self.console_tab_widget.addTab(output_widget, "Output")

        # 2. Terminal (for interactive shell)
        self.terminal = TerminalWidget(self)
        self.terminal.input_ready.connect(self.write_to_process_stdin)
        self.console_tab_widget.addTab(self.terminal, "Terminal")

        # 3. Git Log (for commit history)
        git_log_widget = QTextEdit()
        git_log_widget.setReadOnly(True)
        git_log_widget.setText("Git Commit History will appear here.")
        self.console_tab_widget.addTab(git_log_widget, "Git Log")

        # Collapse/Expand button (QToolButton for corner widget)
        button_wrapper = QWidget()
        h_layout = QHBoxLayout(button_wrapper)
        h_layout.setContentsMargins(0, 0, 10, 0)
        h_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.collapse_btn = QToolButton(self)
        self.collapse_btn.setObjectName("collapse_btn")
        # Initial state: visible, so button says "Hide Console"
        self.collapse_btn.setText("▼ Hide Console")
        # Base styling moved to apply_theme, keeping font bold here for clarity
        self.collapse_btn.setStyleSheet("font-weight: bold;")
        self.collapse_btn.clicked.connect(self.toggle_console_visibility)
        self.collapse_btn.setToolTip("Hide Output/Terminal")

        h_layout.addWidget(self.collapse_btn)
        button_wrapper.setLayout(h_layout)

        # Set the wrapper as the corner widget on the top right of the console tab widget
        self.console_tab_widget.setCornerWidget(button_wrapper, Qt.Corner.TopRightCorner)

    def show_project_label_context_menu(self, position):
        """Displays the context menu when right-clicking the project name label (root creation)."""

        menu = QMenu(self)

        target_dir = self.file_model.filePath(self.file_explorer.rootIndex())

        new_file_action = QAction("📄 New File...", self)
        new_file_action.triggered.connect(lambda: self.create_new_item(target_dir, is_folder=False))
        menu.addAction(new_file_action)

        new_folder_action = QAction("📁 New Folder...", self)
        new_folder_action.triggered.connect(lambda: self.create_new_item(target_dir, is_folder=True))
        menu.addAction(new_folder_action)

        file_path = target_dir

        if Path(file_path).parent != Path(file_path):
            menu.addSeparator()
            rename_action = QAction("✏️ Rename Project Folder", self)
            rename_action.triggered.connect(lambda: self.rename_file(file_path))
            menu.addAction(rename_action)

            delete_action = QAction("🗑️ Delete Project Folder", self)
            delete_action.triggered.connect(lambda: self.delete_file(file_path))
            menu.addAction(delete_action)

        menu.exec(self.project_title_label.mapToGlobal(position))

    def show_context_menu(self, position):
        index = self.file_explorer.indexAt(position)

        menu = QMenu(self)

        if not index.isValid():
            target_dir = self.file_model.filePath(self.file_explorer.rootIndex())
            is_directory = True
        else:
            file_path = self.file_model.filePath(index)
            file_info = QFileInfo(file_path)
            is_directory = file_info.isDir()

            target_dir = file_path if is_directory else str(Path(file_path).parent)

            is_root = file_path == self.file_model.filePath(self.file_explorer.rootIndex())

            if not is_root:
                rename_action = QAction("✏️ Rename", self)
                rename_action.triggered.connect(lambda: self.rename_file(file_path))
                menu.addAction(rename_action)

                delete_action = QAction("🗑️ Delete", self)
                delete_action.triggered.connect(lambda: self.delete_file(file_path))
                menu.addAction(delete_action)

                if is_directory:
                    menu.addSeparator()

            if is_directory or not index.isValid():
                new_file_action = QAction("📄 New File...", self)
                new_file_action.triggered.connect(lambda: self.create_new_item(target_dir, is_folder=False))
                menu.addAction(new_file_action)

                new_folder_action = QAction("📁 New Folder...", self)
                new_folder_action.triggered.connect(lambda: self.create_new_item(target_dir, is_folder=True))
                menu.addAction(new_folder_action)

        menu.exec(self.file_explorer.viewport().mapToGlobal(position))

    def create_new_item(self, target_dir, is_folder):
        if is_folder:
            prompt = "Enter new folder name:"
            default_text = "New Folder"
            item_type = "folder"
        else:
            supported_extensions = ", ".join(sorted(LANGUAGE_MAP.keys()))
            prompt = f'Enter new filename (must include extension: {supported_extensions}):'
            default_text = f"new_file.py"
            error_msg = f"The filename must include a supported extension: {supported_extensions}."
            item_type = "file"

        name, ok = QInputDialog.getText(
            self, f"Create New {item_type.capitalize()}", prompt, text=default_text
        )

        if not ok or not name:
            return

        new_item_path = Path(target_dir) / name

        if new_item_path.exists():
            QMessageBox.warning(self, "Item Exists", f"An item named '{name}' already exists in this location.")
            return

        if not is_folder and not new_item_path.suffix.lower() in LANGUAGE_MAP:
            QMessageBox.warning(self, "Invalid Name", error_msg)
            return

        try:
            if is_folder:
                os.makedirs(new_item_path)
                self.watcher.addPath(str(new_item_path))
            else:
                with open(new_item_path, 'w', encoding='utf-8') as f:
                    f.write('')

            self.console.append(f"✓ Created {item_type}: {name} in {Path(target_dir).name}")

            parent_index = self.file_model.index(target_dir)
            if parent_index.isValid():
                self.file_explorer.expand(parent_index)

            self.git_panel.update_status()

        except Exception as e:
            QMessageBox.critical(self, f"Create {item_type.capitalize()} Error", f"Could not create {item_type}:\n{e}")

    def rename_file(self, old_path):
        old_path_obj = Path(old_path)

        new_name, ok = QInputDialog.getText(
            self, "Rename Item",
            f"Enter new name for {old_path_obj.name}:",
            text=old_path_obj.name
        )

        if not ok or not new_name or new_name == old_path_obj.name:
            return

        new_path_obj = old_path_obj.parent / new_name
        new_path = str(new_path_obj)

        if os.path.exists(new_path):
            QMessageBox.warning(self, "Rename Failed", "A file or folder with that name already exists.")
            return

        if old_path_obj.is_file() and new_path_obj.suffix.lower() not in LANGUAGE_MAP:
            supported_extensions = ", ".join(sorted(LANGUAGE_MAP.keys()))
            QMessageBox.warning(self, "Invalid Name",
                                f"The new filename must include a supported extension: {supported_extensions}.")
            return

        try:
            os.rename(old_path, new_path)
            self.console.append(f"✓ Renamed: {old_path_obj.name} to {new_name}")

            # Update open tabs if the file/folder was renamed
            files_to_update = {}
            for file_path_key in list(self.open_file_paths.keys()):
                if file_path_key == old_path or file_path_key.startswith(old_path + os.sep):
                    i = self.open_file_paths[file_path_key]
                    editor = self.editor_tabs.widget(i)

                    self.watcher.removePath(file_path_key)

                    new_editor_path = file_path_key.replace(old_path, new_path, 1)
                    editor.file_path = new_editor_path
                    files_to_update[new_editor_path] = i

                    if file_path_key == old_path:
                        self.current_file = new_path
                        self.editor_tabs.setTabText(i, new_name)

                        ext = Path(new_path).suffix.lower()
                        language = LANGUAGE_MAP.get(ext, 'Text')
                        editor.set_language(language.lower())

                    del self.open_file_paths[file_path_key]

            self.open_file_paths.update(files_to_update)
            for path_key in files_to_update:
                self.watcher.addPath(path_key)

            if old_path_obj.is_dir():
                self.watcher.addPath(new_path)

            if old_path == self.file_model.filePath(self.file_explorer.rootIndex()):
                self.set_project_root(new_path)
            else:
                self.file_model.setRootPath(self.file_model.rootPath())

            self.git_panel.update_status()

        except Exception as e:
            QMessageBox.critical(self, "Rename Error", f"Could not rename file:\n{e}")

    def delete_file(self, file_path):
        file_path_obj = Path(file_path)
        is_dir = file_path_obj.is_dir()
        item_type = "folder" if is_dir else "file"

        reply = QMessageBox.question(
            self, f"Confirm Delete {item_type.capitalize()}",
            f"Are you sure you want to permanently delete the {item_type}: **{file_path_obj.name}**?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # --- Unwatch Paths ---
                if file_path in self.watcher.files():
                    self.watcher.removePath(file_path)
                elif file_path in self.watcher.directories():
                    old_paths = self.watcher.files() + self.watcher.directories()
                    paths_to_remove = [p for p in old_paths if p.startswith(file_path)]
                    if paths_to_remove:
                        self.watcher.removePaths(paths_to_remove)

                # --- Delete from Disk ---
                if is_dir:
                    # Recursive removal is often better for a full IDE but risky. Using os.rmdir for safety.
                    if not any(file_path_obj.iterdir()):
                        os.rmdir(file_path)
                    else:
                        QMessageBox.critical(self, "Delete Failed",
                                             "Folder is not empty. Cannot delete non-empty folders. Please remove contents first.")
                        return
                else:
                    os.remove(file_path)

                self.console.append(f"✓ Deleted {item_type}: {file_path_obj.name}")

                # --- Close Tabs ---
                tabs_to_close = []
                for i in range(self.editor_tabs.count()):
                    editor = self.editor_tabs.widget(i)
                    if hasattr(editor, 'file_path') and editor.file_path == file_path:
                        tabs_to_close.append(i)
                        break
                    # If deleting a folder, check for files inside it
                    if is_dir and hasattr(editor, 'file_path') and editor.file_path.startswith(file_path + os.sep):
                        tabs_to_close.append(i)

                # Close tabs in reverse order to keep indices valid
                for i in sorted(tabs_to_close, reverse=True):
                    self.close_tab(i)

                # Remove from tracking dictionary
                keys_to_delete = [k for k in self.open_file_paths if
                                  k == file_path or (is_dir and k.startswith(file_path + os.sep))]
                for key in keys_to_delete:
                    del self.open_file_paths[key]

                # --- Refresh UI ---
                self.file_model.setRootPath(self.file_model.rootPath())
                self.git_panel.update_status()

            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Could not delete {item_type}:\n{e}")

    def setup_shortcuts(self):
        save_shortcut = QAction(self)
        save_shortcut.setShortcut("Ctrl+S")
        save_shortcut.triggered.connect(self.save_file)
        self.addAction(save_shortcut)

        run_shortcut = QAction(self)
        run_shortcut.setShortcut("Ctrl+R")
        run_shortcut.triggered.connect(self.run_code)
        self.addAction(run_shortcut)

        new_shortcut = QAction(self)
        new_shortcut.setShortcut("Ctrl+N")
        new_shortcut.triggered.connect(self.new_file)
        self.addAction(new_shortcut)

        open_shortcut = QAction(self)
        open_shortcut.setShortcut("Ctrl+O")
        open_shortcut.triggered.connect(self.open_file)
        self.addAction(open_shortcut)

        debug_shortcut = QAction(self)
        debug_shortcut.setShortcut("Ctrl+D")
        debug_shortcut.triggered.connect(self.toggle_debugger)
        self.addAction(debug_shortcut)

        git_shortcut = QAction(self)
        git_shortcut.setShortcut("Ctrl+G")
        git_shortcut.triggered.connect(lambda: self.file_sidebar_tabs.setCurrentWidget(self.git_panel))
        self.addAction(git_shortcut)

    def new_file(self, initial_load=False):
        if initial_load:
            if self.editor_tabs.count() > 0:
                return

            # Create a single "Untitled" tab if no project is loaded or no files are open
            editor = CodeEditor(self)
            editor.set_language("python")
            editor.request_ai_completion.connect(self.handle_ai_completion_request)
            self.editor_tabs.addTab(editor, "Untitled")
            return

        supported_extensions = ", ".join(sorted(LANGUAGE_MAP.keys()))

        filename, ok = QInputDialog.getText(
            self, 'Create New File',
            f'Enter filename (must include extension: {supported_extensions}):',
            text=f"new_file_{self.editor_tabs.count() + 1}.py"
        )

        if not ok or not filename:
            return

        name = Path(filename).name
        suffix = Path(filename).suffix.lower()

        if suffix not in LANGUAGE_MAP:
            QMessageBox.warning(
                self, "Invalid File Type",
                f"The file name **must** include one of the supported extensions: {supported_extensions}."
            )
            return

        language_name = LANGUAGE_MAP.get(suffix)
        full_path = Path(QDir.currentPath()) / name

        if full_path.exists():
            QMessageBox.warning(self, "File Exists", f"A file named '{name}' already exists in the project root.")
            return

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not create file on disk:\n{e}")
            return

        editor = CodeEditor(self)
        editor.set_language(language_name.lower())
        editor.request_ai_completion.connect(self.handle_ai_completion_request)

        # Remove default "Untitled" tab if it's the only one and empty
        if self.editor_tabs.count() == 1:
            existing_editor = self.editor_tabs.widget(0)
            if existing_editor and self.editor_tabs.tabText(0) == "Untitled" and not existing_editor.toPlainText():
                self.editor_tabs.removeTab(0)

        tab_name = Path(full_path).name
        tab_index = self.editor_tabs.addTab(editor, tab_name)
        self.editor_tabs.setCurrentWidget(editor)

        editor.file_path = str(full_path.resolve())
        self.current_file = editor.file_path
        self.open_file_paths[editor.file_path] = tab_index
        self.watcher.addPath(editor.file_path)

        self.file_model.setRootPath(self.file_model.rootPath())
        self.git_panel.update_status()

        self.console.append(f"✓ File created and saved: {name}\n")

    def open_file(self):
        start_dir = self.file_model.filePath(self.file_explorer.rootIndex())

        all_filters = "All Files (*);" + ";".join([f"{lang} Files (*{ext})" for ext, lang in LANGUAGE_MAP.items()])

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", start_dir, all_filters
        )

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        """Load file into editor"""
        try:
            for i in range(self.editor_tabs.count()):
                editor = self.editor_tabs.widget(i)
                if hasattr(editor, 'file_path') and editor.file_path == file_path:
                    self.editor_tabs.setCurrentIndex(i)
                    return

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                QMessageBox.warning(self, "Load Error",
                                    f"File '{Path(file_path).name}' cannot be displayed. It may be a binary file, an image, or use a non-standard text encoding.")
                self.console.append(f"❌ Load Failed: File {Path(file_path).name} is unreadable or non-text.\n")
                return

            editor = CodeEditor(self)
            editor.setPlainText(content)

            ext = Path(file_path).suffix.lower()
            language = LANGUAGE_MAP.get(ext, 'Text')

            editor.set_language(language.lower())

            # Remove default "Untitled" tab if it's the only one and empty
            if self.editor_tabs.count() == 1:
                existing_editor = self.editor_tabs.widget(0)
                if existing_editor and self.editor_tabs.tabText(0) == "Untitled" and not existing_editor.toPlainText():
                    self.editor_tabs.removeTab(0)

            tab_name = Path(file_path).name
            tab_index = self.editor_tabs.addTab(editor, tab_name)
            self.editor_tabs.setCurrentIndex(tab_index)

            editor.file_path = file_path
            self.current_file = file_path
            self.open_file_paths[file_path] = tab_index
            self.watcher.addPath(file_path)

            editor.request_ai_completion.connect(self.handle_ai_completion_request)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open file due to system error:\n{str(e)}")

    def handle_ai_completion_request(self, file_path, context):
        """Writes the completion request to the IPC file for the background agent to handle."""

        if self.completion_file.exists():
            return

        try:
            with open(self.completion_file, 'w') as f:
                json.dump({"file_path": file_path, "context": context}, f)

            # Relying on the continuous polling timer (_handle_completion_response)
            # which is started in __init__ to read the response.

        except Exception as e:
            self.console.append(f"❌ Failed to write completion request: {e}\n")

    def save_file(self):
        """
        Saves current file. If it's a completely new/unsaved tab, prompts for Save As.
        Returns the saved file path (str) or None if cancelled/failed.
        """
        current_editor = self.editor_tabs.currentWidget()
        if not current_editor:
            return None

        file_path = getattr(current_editor, 'file_path', None)

        # Default language for an unsaved file (e.g., "Untitled")
        current_language = current_editor.language.lower()

        if file_path and Path(file_path).is_file():
            final_path = file_path
        else:
            # Save As logic
            start_dir = self.file_model.filePath(self.file_explorer.rootIndex()) or str(Path.home())

            default_filename = self.editor_tabs.tabText(self.editor_tabs.currentIndex())

            current_lang_capitalized = current_language.capitalize()

            ext_for_filter = next(
                (ext for ext, lang in LANGUAGE_MAP.items() if lang.lower() == current_language),
                f".{current_language.replace('++', 'cpp').replace('javascript', 'js')}"
            )

            ext_filter = f"{current_lang_capitalized} Files (*{ext_for_filter});;All Files (*)"

            final_path, selected_filter = QFileDialog.getSaveFileName(
                self, "Save File As", str(Path(start_dir) / default_filename), ext_filter
            )

            if not final_path:
                return None

            suffix_to_append = ext_for_filter if ext_for_filter.startswith('.') else f".{ext_for_filter}"

            # Simple logic to ensure the file has an extension if one was intended
            if not final_path.lower().endswith(tuple(LANGUAGE_MAP.keys())):
                final_path += suffix_to_append

        try:
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(current_editor.toPlainText())

            # Update tracking dictionary and watcher if the file path changed
            if file_path and file_path != final_path:
                if file_path in self.open_file_paths:
                    self.watcher.removePath(file_path)
                    del self.open_file_paths[file_path]

            current_editor.file_path = final_path
            self.current_file = final_path
            self.open_file_paths[final_path] = self.editor_tabs.currentIndex()
            self.watcher.addPath(final_path)

            tab_index = self.editor_tabs.currentIndex()
            self.editor_tabs.setTabText(tab_index, Path(final_path).name)

            new_ext = Path(final_path).suffix.lower()
            new_language = LANGUAGE_MAP.get(new_ext, 'Text')
            current_editor.set_language(new_language.lower())

            # Refresh file explorer if the file was saved in the current project root
            if not file_path:
                self.file_model.setRootPath(QDir.currentPath())

            self.git_panel.update_status()

            self.console.append(f"✓ File saved: {final_path}\n")
            return final_path

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")
            return None

    def close_tab(self, index):
        editor = self.editor_tabs.widget(index)

        # Remove from watcher and tracking dictionary
        if hasattr(editor, 'file_path') and editor.file_path and editor.file_path in self.open_file_paths:
            self.watcher.removePath(editor.file_path)
            del self.open_file_paths[editor.file_path]

        # If there is more than one tab, just close the requested one
        if self.editor_tabs.count() > 1:
            self.editor_tabs.removeTab(index)
        # If there's only one tab left, reset it to "Untitled" instead of closing the tab widget entirely
        elif self.editor_tabs.count() == 1:
            editor.clear()
            editor.file_path = None
            editor.set_language("python")
            self.editor_tabs.setTabText(0, "Untitled")

    def on_tab_changed(self, index):
        if index >= 0:
            editor = self.editor_tabs.widget(index)
            if hasattr(editor, 'file_path'):

                if editor.file_path is not None:
                    self.current_file = editor.file_path
                    ext = Path(editor.file_path).suffix.lower()
                    language = LANGUAGE_MAP.get(ext, 'Text')
                    self.language_status_label.setText(f"Lang: {language}")
                else:
                    self.current_file = None
                    self.language_status_label.setText("Lang: Python (Unsaved)")

            if editor and isinstance(editor, CodeEditor):
                editor.highlight_current_line()
                # Disconnect and reconnect to avoid multiple connections if tabs change rapidly
                try:
                    editor.cursorPositionChanged.disconnect(self._update_cursor_status)
                except:
                    pass
                editor.cursorPositionChanged.connect(self._update_cursor_status)
                self._update_cursor_status()
        else:
            self.language_status_label.setText("Lang: N/A")
            self.cursor_status_label.setText("Ln N/A, Col N/A")

    def _update_cursor_status(self):
        editor = self.editor_tabs.currentWidget()
        if editor and isinstance(editor, CodeEditor):
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.cursor_status_label.setText(f"Ln {line}, Col {col}")

    def open_file_from_explorer(self, index):
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path):
            self.load_file(file_path)

    def check_and_save_all_open_tabs(self):
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            tab_name = self.editor_tabs.tabText(i)

            if editor is None: continue

            # Skip the default empty "Untitled" tab
            if not hasattr(editor, 'file_path') and not editor.toPlainText() and tab_name == "Untitled":
                continue

            current_text = editor.toPlainText()
            file_path = getattr(editor, 'file_path', None)

            saved_text = ""
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        saved_text = f.read()
                except Exception:
                    # If file is unreadable or non-text, assume it's different to prompt user
                    saved_text = "DIFFERENT"

            # Check for actual modification
            if current_text != saved_text:
                response = QMessageBox.question(
                    self, "Unsaved Changes",
                    f"File '{tab_name}' has unsaved changes. Do you want to save it before continuing?",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
                )

                if response == QMessageBox.StandardButton.Save:
                    self.editor_tabs.setCurrentIndex(i)
                    if self.save_file() is None:
                        return False
                elif response == QMessageBox.StandardButton.Cancel:
                    return False

        return True

    def show_startup_logic(self):
        # Read the last saved theme setting
        last_dark_mode = self.settings.value("dark_mode", True, type=bool)

        # 1. Check for path passed via command line
        if self.initial_project_path and os.path.isdir(self.initial_project_path):
            self.is_dark_mode = last_dark_mode  # Apply saved setting to IDE
            self.start_session(self.initial_project_path)
            return

        # 2. Check for last saved directory
        last_dir = self.settings.value("current_dir", "", type=str)
        if os.path.isdir(last_dir):
            self.is_dark_mode = last_dark_mode  # Apply saved setting to IDE
            self.start_session(last_dir)
        else:
            # 3. Show start screen
            self.start_screen = StartScreen(initial_dark_mode=last_dark_mode)

            self.start_screen.open_folder_requested.connect(self.prompt_for_project_folder)
            self.start_screen.new_project_requested.connect(self.create_new_project_folder)

            # Link StartScreen theme state to IDEWindow's state when opening the IDE
            self.start_screen.open_folder_requested.connect(
                lambda: self._set_ide_mode_from_start_screen(self.start_screen.is_dark_mode))
            self.start_screen.new_project_requested.connect(
                lambda: self._set_ide_mode_from_start_screen(self.start_screen.is_dark_mode))

            # Show in Full Screen Mode
            self.start_screen.showFullScreen()

    def _set_ide_mode_from_start_screen(self, is_dark_mode):
        """Helper to sync the IDE's mode with the final mode set on the StartScreen."""
        self.is_dark_mode = is_dark_mode
        self.apply_theme()

    def start_session(self, directory_path):
        if self.start_screen:
            # Close the start screen after project is loaded
            self.start_screen.close()
            self.start_screen = None

        self.set_project_root(directory_path)

        # Apply Theme and restore window state
        # The IDEWindow's self.is_dark_mode is already set by _set_ide_mode_from_start_screen or startup_logic
        self.apply_theme()

        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

        # Restore open files
        open_files_json = self.settings.value("open_files", "[]", type=str)
        try:
            open_files = json.loads(open_files_json)

            # Clear any default "Untitled" tab before loading saved files
            if self.editor_tabs.count() == 1:
                editor = self.editor_tabs.widget(0)
                if not hasattr(editor, 'file_path') and not editor.toPlainText():
                    self.editor_tabs.removeTab(0)

            for file_path in open_files:
                if os.path.exists(file_path):
                    self.load_file(file_path)

            # If no files were loaded (or the list was empty), open a new "Untitled" tab
            if self.editor_tabs.count() == 0:
                self.new_file(initial_load=True)

            # Restore splitter positions
            main_splitter_state = self.settings.value("main_splitter_sizes")
            if main_splitter_state:
                self.main_splitter.restoreState(main_splitter_state)
            vertical_splitter_state = self.settings.value("vertical_splitter_sizes")
            if vertical_splitter_state:
                self.vertical_splitter.restoreState(vertical_splitter_state)

        except Exception as e:
            if self.editor_tabs.count() == 0:
                self.new_file(initial_load=True)
            self.console.append(f"Error loading session: {e}")

        # Maximize the main IDE window (optional, but standard for an IDE)
        # self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self.show()

    def prompt_for_project_folder(self):
        if self.start_screen:
            self.start_screen.hide()

        directory_path = QFileDialog.getExistingDirectory(
            self, "Select Project Folder", str(Path.home())
        )

        if directory_path:
            self.start_session(directory_path)
        else:
            QCoreApplication.exit(0)

    def create_new_project_folder(self):
        if self.start_screen:
            self.start_screen.hide()

        desktop_path = Path.home() / "Desktop"

        # QFileDialog.getSaveFileName is used to get a path/name, even though we create a directory
        new_folder_path, _ = QFileDialog.getSaveFileName(
            self, "Choose New Project Location and Name",
            str(desktop_path / "NewProject"),
            "Folder Name (*)"
        )

        if new_folder_path:
            new_dir = Path(new_folder_path)

            try:
                new_dir.mkdir(parents=True, exist_ok=True)

                self.editor_tabs.clear()
                self.settings.setValue("open_files", "[]")

                self.start_session(str(new_dir))

            except Exception as e:
                QMessageBox.critical(self, "Error Creating Folder", f"Could not create directory:\n{e}")
                QCoreApplication.exit(0)
        else:
            QCoreApplication.exit(0)

    def exit_project(self):
        if not self.check_and_save_all_open_tabs():
            return

        self.save_session()

        self.settings.remove("current_dir")
        self.settings.sync()

        QCoreApplication.exit(RESTART_ID)

    # ----------------------------------------
    # QProcess Handlers
    # ----------------------------------------

    def handle_stdout(self):
        # Determine which process is sending output
        sender_process = self.sender()
        output = bytes(sender_process.readAllStandardOutput()).decode('utf-8', errors='ignore')
        if hasattr(self, 'console'):
            self.console.append(output)

        if sender_process == self.process and self.process.state() == QProcess.ProcessState.Running and output.strip() and not output.endswith(
                ('\n', '\r')):
            self.console.set_prompt()

    def handle_stderr(self):
        sender_process = self.sender()
        error = bytes(sender_process.readAllStandardError()).decode('utf-8', errors='ignore')
        if hasattr(self, 'console'):
            self.console.append(f"\n⚠ Errors:\n{error}")

    def handle_process_finished(self, exit_code, exit_status):
        if hasattr(self, 'console'):
            if exit_status == QProcess.ExitStatus.NormalExit:
                self.console.append(f"\n✓ Execution completed (Exit Code: {exit_code})")
            else:
                self.console.append(f"\n❌ Execution crashed (Exit Status: {exit_status})")

            # Cleanup temporary files (Only for compiled languages if needed)
            self._cleanup_temp_files()

            self.console.setReadOnly(True)
            self.console.input_start_pos = None

    def handle_compilation_finished(self, exit_code, exit_status):
        """Handles the completion of the compilation QProcess (asynchronously)."""
        if self._pending_run_details is None:
            return

        details = self._pending_run_details
        self._pending_run_details = None

        if exit_code != 0:
            # Errors already printed via handle_stderr
            if hasattr(self, 'console'):
                self.console.append(f"❌ Compilation Failed (Exit Code: {exit_code}). Aborting run.\n")
            return

        # Compilation successful. Now execute the code.
        language = details['language']
        main_file_path = details['path']
        working_dir = details['working_dir']

        program = []
        arguments = []

        if language in ['c', 'c++']:
            output_name = "temp_output"
            # Use os.name to correctly choose executable path
            program = ['./' + output_name] if os.name != 'nt' else [output_name + '.exe']
        elif language == 'java':
            try:
                # Attempt to find public class name
                main_file = Path(main_file_path)
                class_name_match = re.search(r'\s*public\s+class\s+(\w+)\s*{', main_file.read_text(encoding='utf-8'))
                class_name = class_name_match.group(1) if class_name_match else main_file.stem
            except Exception:
                class_name = Path(main_file_path).stem

            program = ['java', class_name]

        self._execute_compiled_code(main_file_path, working_dir, program, arguments)

    def write_to_process_stdin(self, text):
        # Determine if we're in the Output Console or Terminal
        current_tab = self.console_tab_widget.currentWidget()
        target_process = self.process

        if isinstance(current_tab, TerminalWidget):
            # Placeholder for actual terminal input
            if hasattr(self, 'console'):
                self.console.append("\n(Terminal input not fully implemented for execution.)\n")
            return

        if target_process.state() == QProcess.ProcessState.Running:
            target_process.write(text.encode('utf-8'))
        elif hasattr(self, 'console'):
            self.console.append("\n(No program is running to receive input.)\n")

    def _get_compile_command(self, language, main_file_name):
        if language == 'c':
            return 'gcc', [main_file_name, '-o', "temp_output"]
        elif language == 'c++':
            return 'g++', [main_file_name, '-o', "temp_output"]
        elif language == 'java':
            return 'javac', [main_file_name]
        return None, None

    def _execute_compiled_code(self, main_file_path, working_dir, program, arguments):
        """Starts the execution of a prepared program (for Python or after compilation)."""
        if not program:
            if hasattr(self, 'console'):
                self.console.append(f"❌ Execution command not set.\n")
            return

        if hasattr(self, 'console'):
            self.console.append(f"Running: {Path(main_file_path).name}\n")
        self.process.setWorkingDirectory(working_dir)
        command = program + arguments

        # Ensure we clear existing environment for the main run if it's not Python
        if Path(sys.executable).name not in program[0]:
            env = QProcessEnvironment()
            self.process.setProcessEnvironment(env)

        self.process.start(command[0], command[1:])

        if not self.process.waitForStarted(1000):
            if hasattr(self, 'console'):
                self.console.append(
                    f"❌ Failed to start process: {self.process.errorString()}. Is '{command[0]}' installed?\n")

    def _cleanup_temp_files(self):
        """Utility to clean up compiled temporary files."""
        working_dir = Path(QDir.currentPath())
        try:
            temp_output_path = working_dir / "temp_output"
            if temp_output_path.exists():
                os.remove(temp_output_path)
            temp_exe_path = working_dir / "temp_output.exe"
            if temp_exe_path.exists():
                os.remove(temp_exe_path)
            # Java cleanup - remove .class file
            for f in working_dir.glob('*.class'):
                os.remove(f)
        except Exception as e:
            if hasattr(self, 'console'):
                self.console.append(f"⚠️ Cleanup failed: {e}\n")

    def run_code(self):
        # Check if any process is running
        if self.process.state() == QProcess.ProcessState.Running or self.compile_process.state() == QProcess.ProcessState.Running:
            QMessageBox.warning(self, "Running", "A process is already running. Please wait or terminate it.")
            return

        main_file_path = self.save_file()
        if not main_file_path:
            if hasattr(self, 'console'):
                self.console.append("❌ Aborted: Cannot run unsaved file or save failed.\n")
            return

        self.console_tab_widget.setCurrentIndex(0)
        self.console.clear()

        main_file = Path(main_file_path)
        main_file_name = main_file.name
        working_dir = str(main_file.parent)
        ext = main_file.suffix.lower()
        language = LANGUAGE_MAP.get(ext, 'Text').lower()

        program = []
        arguments = []

        if language == 'python':
            program = [sys.executable, main_file_name]
            env = QProcessEnvironment.systemEnvironment()
            env.insert('PYTHONUNBUFFERED', '1')  # Required for real-time output
            self.process.setProcessEnvironment(env)
            self._execute_compiled_code(main_file_path, working_dir, program, arguments)

        elif language in ['c', 'c++', 'java']:
            # Start compilation asynchronously
            compiler, compile_args = self._get_compile_command(language, main_file_name)

            if not compiler:
                if hasattr(self, 'console'):
                    self.console.append(f"⚠️ No compilation command found for {language}. Is the compiler installed?\n")
                return

            if hasattr(self, 'console'):
                self.console.append(f"\n◈ Compiling {main_file_name}...\n")

            # Store details needed for execution after compilation finishes
            self._pending_run_details = {
                'path': main_file_path,
                'working_dir': working_dir,
                'language': language
            }

            self.compile_process.setWorkingDirectory(working_dir)
            self.compile_process.start(compiler, compile_args)

            # Execution will be started by handle_compilation_finished

        elif language in ['html', 'javascript']:
            url = f"file://{main_file_path}"
            webbrowser.open_new_tab(url)
            if hasattr(self, 'console'):
                self.console.append(f"\n✓ Running {main_file_name} in web browser: {url}\n")
            return

        else:
            if hasattr(self, 'console'):
                self.console.append(
                    f"⚠️ Warning: Cannot execute '{main_file_name}'. No execution command defined for **.{ext}** files.\n")
            return

    def apply_theme(self):
        # UNIFIED COLOR PALETTE
        if self.is_dark_mode:
            # Dark Mode Colors (Deep Space Theme)
            PRIMARY_ACCENT = "#9B70FF"  # Lighter Purple
            background_color = "#12121e"  # Deep Dark Blue/Purple Background
            foreground_color = "#EBE9F5"  # Light Text
            panel_background = "#1a1523"  # Slightly darker panel/sidebar background
            accent_color = PRIMARY_ACCENT
            text_color = "#FFFFFF"
            theme_btn_text = "🌝"
            # CONSOLE BUTTON COLOR
            console_button_bg = PRIMARY_ACCENT
            console_button_text = "white"
        else:
            # Light Mode Colors (Clean White Theme)
            PRIMARY_ACCENT = "#7F5EFA"  # Darker Purple
            background_color = "#FFFFFF"  # White background
            foreground_color = "#2F2F4F"  # Dark navy text
            panel_background = "#F5F6FA"  # Light gray panel/sidebar
            accent_color = PRIMARY_ACCENT
            text_color = "#000000"
            theme_btn_text = "🌚"
            # CONSOLE BUTTON COLOR
            console_button_bg = PRIMARY_ACCENT
            console_button_text = "white"

        self.setStyleSheet(f"""
            /* General Window/Widget Styling */
            QMainWindow, QWidget, QSplitter::handle {{
                background-color: {background_color};
                color: {foreground_color};
                font-family: Arial, sans-serif;
            }}

            /* --- FLOATING THEME TOGGLE BUTTON STYLING --- */
            #themeButtonCircle {{
                background: {PRIMARY_ACCENT};
                color: {'white' if self.is_dark_mode else text_color};
                border: none;
                border-radius: 20px;
                font-size: 18px;
                font-weight: bold;
            }}
            #themeButtonCircle:hover {{
                background: {PRIMARY_ACCENT}CC;
            }}

            /* --- UNIFIED HEADER STYLING (Increased Height & Consistency) --- */
            QToolBar {{
                background-color: {panel_background}; /* Base color of the header */
                border-bottom: 3px solid {PRIMARY_ACCENT};
                min-height: 45px; /* Increased height */
                padding: 5px 10px; /* Increased vertical padding */
            }}
            #AppTitleLabel {{
                color: {PRIMARY_ACCENT};
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 20px;
                font-weight: 900;
                letter-spacing: 2px;
            }}
            /* ----------------------------- */

            QTabWidget::pane {{
                border-top: 2px solid {panel_background};
            }}
            QTabBar::tab {{
                background-color: {panel_background};
                color: {foreground_color};
                padding: 5px 10px;
            }}
            QTabBar::tab:selected {{
                background-color: {background_color};
                border-top: 2px solid {accent_color};
            }}

            /* File Explorer & Project Title */
            #ProjectTitleLabel {{
                background-color: {panel_background};
                padding: 8px 10px;
                border-bottom: 1px solid {background_color};
                font-weight: bold;
                color: {accent_color};
            }}
            QTreeView {{
                background-color: {panel_background};
                color: {foreground_color};
                alternate-background-color: {panel_background};
                show-decoration-selected: 1;
            }}
            QTreeView::item:selected {{
                background-color: {accent_color}33;
            }}

            /* Code Editor (Base styles only, colors handled by CodeEditor.setup_editor and highlighter) */
            QPlainTextEdit {{
                background-color: {background_color};
                color: {text_color};
                selection-background-color: #007ACC;
                selection-color: white;
                border: none;
            }}

            /* Console Output */
            #ConsoleWidget, InteractiveConsole, TerminalWidget, QTextEdit#ConsoleTabWidget, GitPanel, QListWidget {{
                background-color: {panel_background};
                color: {foreground_color};
                border: none;
            }}
            /* Specific TextEdit for Output tab */
            #ConsoleWidget {{
                background-color: {panel_background};
            }}

            /* Git Panel Styling */
            QListWidget {{
                background-color: {panel_background};
                color: {foreground_color};
                border: 1px solid {background_color};
            }}
            QLineEdit {{
                background-color: {background_color};
                color: {foreground_color};
                border: 1px solid {accent_color};
                padding: 3px;
            }}

            /* Action Buttons (Run, Exit, Theme) - Blending into header */
            QToolBar QAction, QPushButton, QToolButton:!hover {{
                color: {foreground_color};
                background-color: {panel_background}; /* FIX: Ensures dark color blends with QToolBar background */
                border: 1px solid {accent_color};
                border-radius: 4px;
                padding: 3px 8px;
            }}
            QToolBar QAction:hover, QPushButton:hover, QToolButton:hover {{
                background-color: {accent_color}55;
            }}
            QStatusBar {{
                background-color: {panel_background};
                color: {foreground_color};
            }}

            /* Center credit styling */
            QLabel#CreditLabel {{
                /* REMOVED: This label is no longer in use in the status bar */
                color: {foreground_color}; 
                font-weight: bold;
                font-size: 13px;
                letter-spacing: 1px;
            }}

            QDockWidget::title {{
                background-color: {panel_background};
                border: 1px solid {accent_color};
                padding: 3px;
                font-weight: bold;
            }}
            /* Console Toggle Button styling */
            QToolButton#collapse_btn {{ 
                color: {foreground_color};
                font-weight: bold;
                background-color: transparent;
                border: none; /* Override default border for corner widget */
                padding: 0 8px;
            }}
            QToolButton#collapse_btn:hover {{
                background-color: {accent_color}33;
                border-radius: 4px;
            }}

            /* --- FLOATING CONSOLE BUTTON STYLES (Primary Accent Color) --- */
            QPushButton#FloatingConsoleVisible {{
                background-color: {console_button_bg}; 
                color: {console_button_text};
                border-radius: 18px;
                font-weight: bold;
                border: none;
            }}
            QPushButton#FloatingConsoleVisible:hover {{
                background-color: {PRIMARY_ACCENT}CC;
            }}

            QPushButton#FloatingConsoleHidden {{
                background-color: {background_color}; 
                color: {accent_color}; 
                border: 2px solid {accent_color};
                border-radius: 18px;
                font-weight: bold;
            }}
            QPushButton#FloatingConsoleHidden:hover {{
                background-color: {accent_color}33;
            }}
            /* -------------------------------------- */


        """)

        # Update the theme button icon text
        if hasattr(self, 'theme_btn') and self.theme_btn:
            self.theme_btn.setText(theme_btn_text)

        # Re-apply theme sensitive settings to widgets
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if isinstance(editor, CodeEditor):
                editor.setup_editor()
                if editor.highlighter:
                    # Re-trigger highlighting to pick up new colors
                    editor.highlighter.rehighlight()
                editor.highlight_current_line()
                editor.line_number_area.update()  # Repaint line numbers

        # Re-apply theme sensitive settings to consoles
        self.console.setReadOnly(False)
        self.console.setTextColor(QColor(text_color))
        self.console.setReadOnly(True)

        self.terminal.setTextColor(QColor(text_color))

        self.file_explorer_pane.update()
        self.update()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.settings.setValue("dark_mode", self.is_dark_mode)
        self.apply_theme()
        # Ensure the floating button is correctly positioned after theme/style changes
        self._position_global_elements()

    def save_session(self):
        open_files = []
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            # Only save file paths for files that exist and are not the empty "Untitled" placeholder
            if hasattr(editor, 'file_path') and editor.file_path and os.path.exists(editor.file_path):
                open_files.append(editor.file_path)

        self.settings.setValue("open_files", json.dumps(open_files))

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        self.settings.setValue("main_splitter_sizes", self.main_splitter.saveState())
        self.settings.setValue("vertical_splitter_sizes", self.vertical_splitter.saveState())

    def closeEvent(self, event):
        if self.check_and_save_all_open_tabs():
            self.save_session()

            # Ensure all processes are terminated cleanly
            if self.process.state() == QProcess.ProcessState.Running:
                self.process.terminate()
                self.process.waitForFinished(1000)

            if self.compile_process.state() == QProcess.ProcessState.Running:
                self.compile_process.terminate()
                self.compile_process.waitForFinished(1000)

            # Remove IPC files to prevent false starts on next run
            try:
                if self.completion_file.exists(): self.completion_file.unlink()
                if self.completion_response_file.exists(): self.completion_response_file.unlink()
                if self.request_file.exists(): self.request_file.unlink()
                if self.response_file.exists(): self.response_file.unlink()
            except Exception:
                pass

            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    # Initial setup for git and shlex for compatibility checks (optional but good practice)
    try:
        import git
        import shlex
    except ImportError as e:
        print(f"Required module not found: {e}. Please install requirements: `pip install PyQt6 GitPython`")
        sys.exit(1)

    current_exit_code = RESTART_ID
    while current_exit_code == RESTART_ID:
        if not QCoreApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QCoreApplication.instance()

        # Handle command line argument for project path
        project_path = sys.argv[1] if len(sys.argv) > 1 else None

        window = IDEWindow(project_path=project_path)

        current_exit_code = app.exec()

        # Clean up resources before potential restart
        del window
        del app

    sys.exit(current_exit_code)
