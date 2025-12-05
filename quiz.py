import sys
import json
import requests
from datetime import datetime
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QSpinBox, QComboBox,
    QMessageBox, QFileDialog, QRadioButton, QButtonGroup, QProgressBar,
    QFrame, QScrollArea, QDialog, QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QObject, pyqtSignal, QThread, QTimer, QSize, pyqtSlot
)
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QPalette


# --- Custom signal class ---
class OllamaSignals(QObject):
    # Signals for Quiz Generation
    quiz_generated = pyqtSignal(list)
    generation_error = pyqtSignal(str)
    connection_error = pyqtSignal(str)
    quiz_button_state = pyqtSignal(bool, str)  # enable/disable, text

    # Signals for Chatbot
    chat_chunk_received = pyqtSignal(str)
    chat_stream_finished = pyqtSignal()
    chat_error = pyqtSignal(str)
    chat_button_state = pyqtSignal(bool, str)


# --- QThread Worker for Ollama API Interaction (Best Practice) ---
class OllamaWorker(QObject):
    def __init__(self, signals, model, endpoint, parent=None):
        super().__init__(parent)
        self.signals = signals
        self.ollama_model = model
        self.ollama_endpoint = endpoint

    @pyqtSlot(str, int, str)
    def fetch_quiz(self, topic, num_questions, difficulty):
        """Worker function to fetch quiz data from Ollama."""
        prompt = f"""Generate a quiz with exactly {num_questions} multiple choice questions about {topic} at {difficulty} difficulty level.
Format the response as a valid JSON array with this exact structure:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": 0,
    "explanation": "Brief explanation of why this is correct"
  }}
]
Rules:
- correct_answer must be the index (0-3) of the correct option
- Make questions clear and educational
- Provide helpful explanations
- Ensure proper JSON formatting and strictly adhere to the requested number of questions."""

        try:
            response = requests.post(self.ollama_endpoint,
                                     json={
                                         'model': self.ollama_model,
                                         'prompt': prompt,
                                         'stream': False,
                                         'temperature': 0.7
                                     },
                                     timeout=180)

            if response.status_code == 200:
                result = response.json()
                quiz_text = result.get('response', '')

                # Robust JSON Extraction
                quiz_text = quiz_text.strip()
                if quiz_text.startswith('```json'):
                    quiz_text = quiz_text[7:].strip()
                if quiz_text.endswith('```'):
                    quiz_text = quiz_text[:-3].strip()

                start_idx = quiz_text.find('[')
                end_idx = quiz_text.rfind(']') + 1

                if start_idx != -1 and end_idx > start_idx:
                    json_str = quiz_text[start_idx:end_idx]
                    quiz_data = json.loads(json_str)

                    if len(quiz_data) < 1 or not all(
                            isinstance(q, dict) and 'question' in q for q in quiz_data):
                        raise ValueError("Generated JSON array is empty or malformed structure.")

                    self.signals.quiz_generated.emit(quiz_data)
                else:
                    self.signals.generation_error.emit(
                        "AI response did not contain a valid JSON array structure.")

            elif response.status_code == 404:
                self.signals.generation_error.emit(
                    f"Model '{self.ollama_model}' not found. Please pull it first.")
            else:
                self.signals.generation_error.emit(
                    f"Ollama API error: Status {response.status_code}. Response: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            self.signals.connection_error.emit(
                f"Could not connect to Ollama at {self.ollama_endpoint}. Ensure Ollama is running.")
        except requests.exceptions.Timeout:
            self.signals.generation_error.emit(
                "Ollama response timed out (180s). Try a simpler topic or fewer questions.")
        except (json.JSONDecodeError, ValueError) as e:
            self.signals.generation_error.emit(
                f"Failed to parse quiz data. Malformed JSON or invalid structure: {e}. Raw response start: {quiz_text[:100]}")
        except Exception as e:
            self.signals.generation_error.emit(f"An unexpected error occurred: {str(e)}")
        finally:
            self.signals.quiz_button_state.emit(True, "🚀 Generate Quiz")

    @pyqtSlot(str, dict)
    def ask_chatbot_stream(self, user_question, current_question_data):
        """Worker function to stream chat responses from Ollama."""
        q_data = current_question_data

        prompt = f"""You are a Quiz Assistant AI. The current question is: "{q_data.get('question', 'Unknown Question')}". 
The options are: {q_data.get('options', [])}. 
The user is asking: "{user_question}". 
Your primary goal is to provide **helpful context and educational details** without giving away the correct answer. Provide a conversational, brief, and insightful response."""

        try:
            response = requests.post(self.ollama_endpoint,
                                     json={
                                         'model': self.ollama_model,
                                         'prompt': prompt,
                                         'stream': True,
                                         'temperature': 0.5
                                     },
                                     timeout=60,
                                     stream=True)

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            content = chunk.get('response', '')

                            if content:
                                self.signals.chat_chunk_received.emit(content)

                            if chunk.get('done'):
                                break

                        except json.JSONDecodeError:
                            continue

            else:
                self.signals.chat_error.emit(f"Error querying AI: Status {response.status_code}")

        except requests.exceptions.ConnectionError:
            self.signals.chat_error.emit("Connection failed. Is Ollama running and accessible?")
        except Exception as e:
            self.signals.chat_error.emit(f"An internal error occurred: {str(e)}")
        finally:
            self.signals.chat_stream_finished.emit()


# --- Main Application Window ---
class QuizMakerApp(QMainWindow):
    # Dynamic Signals to start tasks in the worker thread
    start_quiz_fetch = pyqtSignal(str, int, str)
    start_chat_fetch = pyqtSignal(str, dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Made by Krish 🔧")
        self.setGeometry(100, 100, 1100, 750)

        # --- Theme colors ---
        self.themes = {
            'light': {
                'bg': '#F5F6FA',
                'fg': '#2F2F4F',
                'card_bg': '#FFFFFF',
                'accent': '#7F5EFA',
                'hover': '#9B70FF',
                'correct': '#3CB371',
                'wrong': '#FF6347',
                'border': '#EBE9F5',
                'chat_user_bg': '#EBE9F5',
                'chat_ai_bg': '#FFFFFF'
            },
            'dark': {
                'bg': '#1A1523',
                'fg': '#EBE9F5',
                'card_bg': '#282038',
                'accent': '#9B70FF',
                'hover': '#7F5EFA',
                'correct': '#66bb6a',
                'wrong': '#ef5350',
                'border': '#352D45',
                'chat_user_bg': '#352D45',
                'chat_ai_bg': '#1A1523'
            }
        }

        self.current_theme = 'dark'
        self.quiz_data = []
        self.current_question_index = 0
        self.score = 0
        self.user_answers = []
        self.ai_stream_start_cursor_pos = 0
        self.chatbot_text_display = None  # Initialize reference for safety checks

        # --- Ollama Configuration ---
        self.ollama_model = 'llama3.2'
        self.ollama_endpoint = 'http://localhost:11434/api/generate'

        # --- QThread Worker Setup (FIXED ORDER) ---

        # 1. Initialize Signal Object FIRST (Resolves AttributeError)
        self.ollama_signals = OllamaSignals()
        self._connect_signals()

        # 2. QThread and Worker Setup SECOND
        self.worker_thread = QThread()
        self.ollama_worker = OllamaWorker(
            self.ollama_signals, self.ollama_model, self.ollama_endpoint
        )
        self.ollama_worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Connect Main Thread signals to Worker Slots
        self.start_quiz_fetch.connect(self.ollama_worker.fetch_quiz)
        self.start_chat_fetch.connect(self.ollama_worker.ask_chatbot_stream)

        self.setup_ui()
        self.apply_theme()
        self.show_home_screen()

    def _connect_signals(self):
        """Connects worker signals to UI handlers."""
        self.ollama_signals.quiz_generated.connect(self._handle_quiz_generated)
        self.ollama_signals.generation_error.connect(self._handle_generation_error_ui)
        self.ollama_signals.connection_error.connect(self._handle_connection_error_ui)
        self.ollama_signals.quiz_button_state.connect(self._update_generate_button_ui)

        self.ollama_signals.chat_chunk_received.connect(self._append_chat_chunk_ui)
        self.ollama_signals.chat_stream_finished.connect(self._handle_chat_stream_finished_ui)
        self.ollama_signals.chat_error.connect(self._handle_chat_error_ui)
        self.ollama_signals.chat_button_state.connect(self._update_chat_button_ui)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header Frame
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(60)
        self.header_frame.setObjectName("header_frame")

        self.header_layout = QGridLayout(self.header_frame)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setHorizontalSpacing(0)
        self.header_layout.setVerticalSpacing(0)

        # Main Title (Centered)
        self.title_label = QLabel("🎓 VenomIQ Lab")
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.header_layout.addWidget(self.title_label, 0, 0, 1, 3)

        # Theme Toggle Button (Top Right)
        self.theme_btn = QPushButton("🌝" if self.current_theme == 'dark' else "🌚")
        self.theme_btn.setFont(QFont('Segoe UI', 16))
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setObjectName("ThemeButtonCircle")
        self.header_layout.addWidget(self.theme_btn, 0, 2, Qt.AlignRight | Qt.AlignVCenter)

        self.main_layout.addWidget(self.header_frame)

        # Content area
        self.content_container = QFrame()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(20, 10, 20, 10)
        self.content_layout.setSpacing(0)
        self.main_layout.addWidget(self.content_container)

    def clear_content(self):
        # Safely remove all widgets from the content layout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                widget = item.widget()

                # Check if the widget being deleted is the chatbot display
                if widget is self.chatbot_text_display:
                    self.chatbot_text_display = None  # Clear the reference immediately

                widget.deleteLater()
            elif item.layout():
                # Recursively clear sub-layouts
                while item.layout().count():
                    child_item = item.layout().takeAt(0)
                    if child_item.widget():
                        child_item.widget().deleteLater()
                item.layout().deleteLater()

    def show_home_screen(self):
        self.clear_content()
        self.apply_theme()

        home_frame = QFrame()
        home_layout = QVBoxLayout(home_frame)
        home_layout.setAlignment(Qt.AlignCenter)
        home_layout.setSpacing(15)

        welcome_label = QLabel("Create Your Custom Quiz")
        welcome_label.setFont(QFont('Segoe UI', 28, QFont.Bold))
        welcome_label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(welcome_label)

        subtitle_label = QLabel(f"Powered by {self.ollama_model} via Ollama (Requires local setup)")
        subtitle_label.setFont(QFont('Segoe UI', 12))
        subtitle_label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(subtitle_label)

        # Input card
        input_card = QFrame()
        input_card.setContentsMargins(20, 20, 20, 20)
        input_card_layout = QVBoxLayout(input_card)
        input_card.setObjectName("InputCard")
        input_card.setMinimumWidth(600)
        input_card.setMaximumWidth(800)
        home_layout.addWidget(input_card, alignment=Qt.AlignCenter)

        # Topic input
        input_card_layout.addWidget(QLabel("Quiz Topic:", font=QFont('Segoe UI', 12, QFont.Bold)))
        self.topic_entry = QTextEdit("E.g., Python Programming, World History, Biology...")
        self.topic_entry.setFont(QFont('Segoe UI', 11))
        self.topic_entry.setFixedHeight(70)
        self.topic_entry.textChanged.connect(self._clear_placeholder_on_edit)
        input_card_layout.addWidget(self.topic_entry)

        # Options frame (horizontal)
        options_h_layout = QHBoxLayout()
        options_h_layout.setSpacing(20)
        input_card_layout.addLayout(options_h_layout)

        # Number of questions
        num_q_v_layout = QVBoxLayout()
        num_q_v_layout.addWidget(QLabel("Number of Questions (Max 50):", font=QFont('Segoe UI', 10, QFont.Bold)))
        self.num_questions_spinbox = QSpinBox()
        self.num_questions_spinbox.setRange(3, 50)
        self.num_questions_spinbox.setValue(5)
        self.num_questions_spinbox.setFont(QFont('Segoe UI', 11))
        num_q_v_layout.addWidget(self.num_questions_spinbox)
        options_h_layout.addLayout(num_q_v_layout)

        # Difficulty level
        difficulty_v_layout = QVBoxLayout()
        difficulty_v_layout.addWidget(QLabel("Difficulty Level:", font=QFont('Segoe UI', 10, QFont.Bold)))
        self.difficulty_combobox = QComboBox()
        self.difficulty_combobox.addItems(['Easy', 'Medium', 'Hard'])
        self.difficulty_combobox.setCurrentText('Medium')
        self.difficulty_combobox.setFont(QFont('Segoe UI', 11))
        difficulty_v_layout.addWidget(self.difficulty_combobox)
        options_h_layout.addLayout(difficulty_v_layout)

        # Generate button
        self.generate_btn = QPushButton("🚀 Generate Quiz")
        self.generate_btn.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.generate_btn.setFixedHeight(50)
        self.generate_btn.clicked.connect(self.generate_quiz)
        self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.setObjectName("AccentButton")
        input_card_layout.addWidget(self.generate_btn)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setFont(QFont('Segoe UI', 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setObjectName("StatusLabel")
        home_layout.addWidget(self.status_label)

        self.content_layout.addWidget(home_frame)
        self.apply_theme()

    def _clear_placeholder_on_edit(self):
        if self.topic_entry.toPlainText() == "E.g., Python Programming, World History, Biology...":
            QTimer.singleShot(0, self.topic_entry.clear)

    def generate_quiz(self):
        topic = self.topic_entry.toPlainText().strip()
        if not topic or topic == "E.g., Python Programming, World History, Biology...":
            QMessageBox.warning(self, "Input Required", "Please enter a quiz topic!")
            return

        num_q = self.num_questions_spinbox.value()
        difficulty = self.difficulty_combobox.currentText()

        colors = self.themes[self.current_theme]
        self.status_label.setText("🔄 Generating quiz... This might take up to a minute.")
        self.status_label.setStyleSheet(f"color: {colors['accent']};")
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        # Start the worker task via signal
        self.start_quiz_fetch.emit(topic, num_q, difficulty)

    # --- Quiz Generation UI Handlers (Connected to Worker Signals) ---

    def _handle_quiz_generated(self, quiz_data):
        self.quiz_data = quiz_data
        self.current_question_index = 0
        self.score = 0
        self.user_answers = []
        self.show_quiz()

    def _handle_generation_error_ui(self, msg):
        QMessageBox.warning(self, "Quiz Generation Error", msg)

    def _handle_connection_error_ui(self, msg):
        QMessageBox.critical(self, "Connection Error", msg)

    def _update_generate_button_ui(self, enable, text):
        self.generate_btn.setEnabled(enable)
        self.generate_btn.setText(text)
        self.status_label.setStyleSheet("")

    # --- Quiz Screen Setup ---
    def show_quiz(self):
        self.clear_content()

        if self.current_question_index >= len(self.quiz_data):
            self.show_results()
            return

        quiz_main_h_layout = QHBoxLayout()
        self.content_layout.addLayout(quiz_main_h_layout)

        quiz_v_layout = QVBoxLayout()
        quiz_main_h_layout.addLayout(quiz_v_layout, 2)

        self.chatbot_frame(quiz_main_h_layout)
        self.apply_theme()

        # Progress bar
        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        progress_text = f"Question {self.current_question_index + 1} of {len(self.quiz_data)}"
        progress_label = QLabel(progress_text)
        progress_label.setFont(QFont('Segoe UI', 12, QFont.Bold))
        progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.quiz_data))
        self.progress_bar.setValue(self.current_question_index + 1)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setObjectName("QuizProgressBar")
        progress_layout.addWidget(self.progress_bar)
        quiz_v_layout.addWidget(progress_frame)

        # Question card
        question_card = QFrame()
        question_card.setObjectName("InputCard")
        question_card_layout = QVBoxLayout(question_card)
        question_card_layout.setContentsMargins(20, 20, 20, 20)
        question_card_layout.setSpacing(15)
        quiz_v_layout.addWidget(question_card, 1)

        q_data = self.quiz_data[self.current_question_index]

        q_label = QLabel(q_data.get('question', 'Error: Question text missing.'))
        q_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        q_label.setWordWrap(True)
        q_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        question_card_layout.addWidget(q_label)

        # Options
        self.option_button_group = QButtonGroup(self)
        self.option_button_group.setExclusive(True)
        self.option_buttons = []

        options = q_data.get('options', [])

        options_container = QFrame()
        options_container_layout = QVBoxLayout(options_container)
        options_container_layout.setContentsMargins(20, 10, 20, 10)

        for i, option_text in enumerate(options):
            btn = QRadioButton(f"{chr(65 + i)}. {option_text}")
            btn.setFont(QFont('Segoe UI', 12))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName("OptionRadioButton")
            self.option_button_group.addButton(btn, i)
            self.option_buttons.append(btn)
            options_container_layout.addWidget(btn, alignment=Qt.AlignLeft)

        question_card_layout.addWidget(options_container)

        # Submit button
        submit_btn_frame = QFrame()
        submit_btn_layout = QHBoxLayout(submit_btn_frame)
        submit_btn_layout.setAlignment(Qt.AlignCenter)
        submit_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.submit_btn = QPushButton("Submit Answer")
        self.submit_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self.submit_btn.setFixedHeight(45)
        self.submit_btn.setFixedWidth(180)
        self.submit_btn.clicked.connect(self.check_answer)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.setObjectName("AccentButton")
        submit_btn_layout.addWidget(self.submit_btn)
        question_card_layout.addWidget(submit_btn_frame)
        question_card_layout.addStretch()

        self.option_button_group.buttonClicked.connect(lambda: self.submit_btn.setEnabled(True))
        self.apply_theme()

    def check_answer(self):
        selected_id = self.option_button_group.checkedId()
        if selected_id == -1:
            return

        q_data = self.quiz_data[self.current_question_index]
        correct = q_data.get('correct_answer', -1)
        selected = selected_id

        self.user_answers.append(selected)

        for btn in self.option_buttons:
            btn.setEnabled(False)
        self.submit_btn.setEnabled(False)

        self._show_result_dialog(q_data, selected, correct)

    def _show_result_dialog(self, q_data, selected, correct):
        is_correct = selected == correct
        colors = self.themes[self.current_theme]

        result_dialog = QDialog(self)
        result_dialog.setWindowTitle("Answer Result")
        result_dialog.setFixedSize(500, 350)
        result_dialog.setModal(True)
        result_dialog_layout = QVBoxLayout(result_dialog)
        result_dialog_layout.setAlignment(Qt.AlignCenter)

        frame_geom = self.frameGeometry()
        dialog_geom = result_dialog.frameGeometry()
        dialog_geom.moveCenter(frame_geom.center())
        result_dialog.move(dialog_geom.topLeft())

        result_dialog.setStyleSheet(f"""
            QDialog {{ background-color: {colors['card_bg']}; }}
            QLabel#ResultTitle {{ color: {'#4caf50' if is_correct else '#f44336'}; }}
            QFrame#ExplanationFrame {{ background-color: {colors['bg']}; border-radius: 5px; }}
        """)

        if is_correct:
            self.score += 1
            icon = "✅"
            title = "Correct!"
            color = colors['correct']
        else:
            icon = "❌"
            title = "Incorrect"
            color = colors['wrong']

        icon_label = QLabel(icon)
        icon_label.setFont(QFont('Segoe UI', 48))
        icon_label.setStyleSheet(f"color: {color};")
        result_dialog_layout.addWidget(icon_label, alignment=Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setFont(QFont('Segoe UI', 24, QFont.Bold))
        title_label.setObjectName("ResultTitle")
        result_dialog_layout.addWidget(title_label, alignment=Qt.AlignCenter)

        if not is_correct:
            correct_option_text = q_data.get('options', ['N/A'])[correct] if 0 <= correct < len(
                q_data.get('options', [])) else "N/A"
            correct_text = f"Correct Answer: {chr(65 + correct)}. {correct_option_text}"
            correct_label = QLabel(correct_text)
            correct_label.setFont(QFont('Segoe UI', 11))
            correct_label.setWordWrap(True)
            correct_label.setStyleSheet(f"color: {colors['fg']};")
            result_dialog_layout.addWidget(correct_label, alignment=Qt.AlignCenter)

        exp_frame = QFrame()
        exp_frame.setObjectName("ExplanationFrame")
        exp_frame_layout = QVBoxLayout(exp_frame)
        exp_frame_layout.setContentsMargins(10, 10, 10, 10)

        tk_label = QLabel("💡 Explanation:")
        tk_label.setFont(QFont('Segoe UI', 10, QFont.Bold))
        tk_label.setStyleSheet(f"color: {colors['fg']};")
        exp_frame_layout.addWidget(tk_label, alignment=Qt.AlignLeft)

        exp_content = QLabel(q_data.get('explanation', 'No explanation provided.'))
        exp_content.setFont(QFont('Segoe UI', 10))
        exp_content.setWordWrap(True)
        exp_content.setStyleSheet(f"color: {colors['fg']};")
        exp_frame_layout.addWidget(exp_content, alignment=Qt.AlignLeft)

        result_dialog_layout.addWidget(exp_frame)

        next_btn = QPushButton("Next Question →" if self.current_question_index < len(
            self.quiz_data) - 1 else "Finish Quiz")
        next_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        next_btn.setFixedSize(200, 45)
        next_btn.clicked.connect(lambda: [result_dialog.accept(), self.next_question()])
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setObjectName("AccentButton")
        result_dialog_layout.addWidget(next_btn, alignment=Qt.AlignCenter)

        result_dialog.exec_()

    def next_question(self):
        self.current_question_index += 1
        self.show_quiz()

    # --- Chatbot Implementation ---
    def chatbot_frame(self, parent_layout):
        colors = self.themes[self.current_theme]

        chat_container = QFrame()
        chat_container.setFixedWidth(350)
        chat_container.setObjectName("InputCard")
        chat_v_layout = QVBoxLayout(chat_container)
        chat_v_layout.setContentsMargins(0, 0, 0, 0)
        chat_v_layout.setSpacing(0)

        # Header
        chat_header = QLabel("🤖 Quiz Assistant")
        chat_header.setFont(QFont('Segoe UI', 14, QFont.Bold))
        chat_header.setAlignment(Qt.AlignCenter)
        chat_header.setFixedHeight(40)
        chat_header.setStyleSheet(f"background-color: {colors['accent']}; color: white; border-radius: 8px 8px 0 0;")
        chat_v_layout.addWidget(chat_header)

        # Chat display area
        self.chatbot_text_display = QTextEdit()
        self.chatbot_text_display.setReadOnly(True)
        self.chatbot_text_display.setFont(QFont('Segoe UI', 10))
        self.chatbot_text_display.setObjectName("ChatTextDisplay")
        chat_v_layout.addWidget(self.chatbot_text_display)

        # Input area
        chat_input_frame = QFrame()
        chat_input_frame.setObjectName("ChatInputFrame")
        chat_input_h_layout = QHBoxLayout(chat_input_frame)
        chat_input_h_layout.setContentsMargins(5, 5, 5, 5)
        chat_input_h_layout.setSpacing(5)

        self.chat_input_entry = QLineEdit()
        self.chat_input_entry.setFont(QFont('Segoe UI', 10))
        self.chat_input_entry.setPlaceholderText("Ask a question about the current topic...")
        self.chat_input_entry.returnPressed.connect(self.send_chat_message)
        self.chat_input_entry.setObjectName("ChatInputEntry")
        chat_input_h_layout.addWidget(self.chat_input_entry)

        self.chat_send_btn = QPushButton("Send")
        self.chat_send_btn.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.chat_send_btn.setFixedSize(60, 35)
        self.chat_send_btn.clicked.connect(self.send_chat_message)
        self.chat_send_btn.setCursor(Qt.PointingHandCursor)
        self.chat_send_btn.setObjectName("ChatSendButton")
        chat_input_h_layout.addWidget(self.chat_send_btn)

        chat_v_layout.addWidget(chat_input_frame)
        parent_layout.addWidget(chat_container, 1)

    def send_chat_message(self):
        user_message = self.chat_input_entry.text().strip()
        self.chat_input_entry.clear()

        if not user_message:
            return

        self.append_chat_message("You", user_message, 'user')
        self._start_ai_response_display()

        self.ollama_signals.chat_button_state.emit(False, "...")

        # Start the worker task via signal
        q_data = self.quiz_data[self.current_question_index]
        self.start_chat_fetch.emit(user_message, q_data)

    # --- Chatbot UI Handlers (Connected to Worker Signals) ---

    def _start_ai_response_display(self):
        if self.chatbot_text_display is None: return  # Safety check
        colors = self.themes[self.current_theme]
        cursor = self.chatbot_text_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        format.setBackground(QColor(colors['chat_ai_bg']))
        format.setForeground(QColor(colors['fg']))
        format.setFontWeight(QFont.Bold)

        cursor.insertBlock()
        cursor.insertText("Assistant: ", format)

        format.setFontWeight(QFont.Normal)
        cursor.setCharFormat(format)

        self.ai_stream_start_cursor_pos = cursor.position()
        self.chatbot_text_display.setTextCursor(cursor)
        self.chatbot_text_display.ensureCursorVisible()

    def append_chat_message(self, sender, message, tag_name):
        if self.chatbot_text_display is None: return  # Safety check
        colors = self.themes[self.current_theme]
        cursor = self.chatbot_text_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        format = QTextCharFormat()
        if tag_name == 'user':
            format.setBackground(QColor(colors['chat_user_bg']))
            format.setForeground(QColor(colors['fg']))
            format.setFontWeight(QFont.Bold)
            prefix = f"{sender}: "
        elif tag_name == 'ai':
            format.setBackground(QColor(colors['chat_ai_bg']))
            format.setForeground(QColor(colors['fg']))
            format.setFontWeight(QFont.Bold)
            prefix = f"{sender}: "

        cursor.insertBlock()
        cursor.insertText(prefix, format)

        format.setFontWeight(QFont.Normal)
        cursor.insertText(message, format)

        self.chatbot_text_display.setTextCursor(cursor)
        self.chatbot_text_display.ensureCursorVisible()

    def _append_chat_chunk_ui(self, chunk):
        if self.chatbot_text_display is None: return  # Safety check
        cursor = self.chatbot_text_display.textCursor()
        cursor.setPosition(self.ai_stream_start_cursor_pos)

        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.MoveAnchor)

        cursor.insertText(chunk)

        self.ai_stream_start_cursor_pos = cursor.position()
        self.chatbot_text_display.setTextCursor(cursor)
        self.chatbot_text_display.ensureCursorVisible()

    def _handle_chat_stream_finished_ui(self):
        if self.chatbot_text_display is None: return  # Safety check
        cursor = self.chatbot_text_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock()
        self.chatbot_text_display.setTextCursor(cursor)
        self.chatbot_text_display.ensureCursorVisible()

        self.ollama_signals.chat_button_state.emit(True, "Send")

    def _handle_chat_error_ui(self, msg):
        self.append_chat_message("Assistant (Error)", msg, 'ai')
        self.ollama_signals.chat_button_state.emit(True, "Send")

    def _update_chat_button_ui(self, enable, text):
        self.chat_send_btn.setEnabled(enable)
        self.chat_send_btn.setText(text)
        self.chat_input_entry.setEnabled(enable)

    # --- Results and Report ---
    def show_results(self):
        self.clear_content()
        colors = self.themes[self.current_theme]

        results_frame = QFrame()
        results_layout = QVBoxLayout(results_frame)
        results_layout.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(results_frame)

        total_questions = len(self.quiz_data)
        percentage = (self.score / total_questions) * 100 if total_questions > 0 else 0

        tk_label = QLabel("🎉 Quiz Complete!")
        tk_label.setFont(QFont('Segoe UI', 28, QFont.Bold))
        results_layout.addWidget(tk_label, alignment=Qt.AlignCenter)

        score_text = f"{self.score} / {total_questions}"
        score_label = QLabel(score_text)
        score_label.setFont(QFont('Segoe UI', 48, QFont.Bold))
        results_layout.addWidget(score_label, alignment=Qt.AlignCenter)

        percent_label = QLabel(f"{percentage:.1f}%")
        percent_label.setFont(QFont('Segoe UI', 24))
        results_layout.addWidget(percent_label, alignment=Qt.AlignCenter)

        if percentage >= 80:
            message = "Excellent work! 🌟"
        elif percentage >= 60:
            message = "Good job! 👍"
        else:
            message = "Keep practicing! 💪"

        message_label = QLabel(message)
        message_label.setFont(QFont('Segoe UI', 16))
        results_layout.addWidget(message_label, alignment=Qt.AlignCenter)

        btn_frame = QFrame()
        btn_h_layout = QHBoxLayout(btn_frame)
        btn_h_layout.setSpacing(20)

        download_btn = QPushButton("📥 Download Report")
        download_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        download_btn.setFixedSize(200, 45)
        download_btn.setObjectName("AccentButton")
        download_btn.clicked.connect(self.download_report)
        btn_h_layout.addWidget(download_btn)

        new_quiz_btn = QPushButton("🏠 New Quiz")
        new_quiz_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        new_quiz_btn.setFixedSize(200, 45)
        new_quiz_btn.setObjectName("AccentButton")
        new_quiz_btn.clicked.connect(self.show_home_screen)
        btn_h_layout.addWidget(new_quiz_btn)

        results_layout.addWidget(btn_frame, alignment=Qt.AlignCenter)
        results_layout.addStretch()
        self.apply_theme()

    def download_report(self):
        if not self.quiz_data:
            return

        initial_file = f"quiz_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Quiz Report", initial_file,
            "Text files (*.txt);;JSON files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                report_data = {
                    'quiz_data': self.quiz_data,
                    'score': self.score,
                    'total': len(self.quiz_data),
                    'user_answers': self.user_answers,
                    'date': datetime.now().isoformat()
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("QUIZ REPORT\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    total = len(self.quiz_data)
                    f.write(f"Score: {self.score}/{total} ({(self.score / total * 100):.1f}%)\n")
                    f.write("\n" + "=" * 60 + "\n\n")

                    for i, q_data in enumerate(self.quiz_data):
                        f.write(f"Question {i + 1}: {q_data.get('question', 'N/A')}\n\n")

                        correct_idx = q_data.get('correct_answer', -1)
                        user_idx = self.user_answers[i] if i < len(self.user_answers) else -2

                        options = q_data.get('options', [])

                        for j, opt in enumerate(options):
                            marker = "✓" if j == correct_idx else " "
                            user_marker = "→" if j == user_idx else " "
                            f.write(f"  {user_marker} [{marker}] {chr(65 + j)}. {opt}\n")

                        f.write(f"\nExplanation: {q_data.get('explanation', 'No explanation provided.')}\n")
                        f.write("\n" + "-" * 60 + "\n\n")

            QMessageBox.information(self, "Success", f"Report saved successfully!\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save report: {str(e)}")

    # --- Theming and Styling ---
    def toggle_theme(self):
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.theme_btn.setText('🌝' if self.current_theme == 'dark' else '🌚')
        self.apply_theme()

    def apply_theme(self):
        colors = self.themes[self.current_theme]

        # 1. Main Palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(colors['bg']))
        palette.setColor(QPalette.WindowText, QColor(colors['fg']))
        palette.setColor(QPalette.Base, QColor(colors['card_bg']))
        palette.setColor(QPalette.Text, QColor(colors['fg']))
        palette.setColor(QPalette.Button, QColor(colors['accent']))
        palette.setColor(QPalette.ButtonText, QColor('white'))
        palette.setColor(QPalette.Highlight, QColor(colors['accent']))
        palette.setColor(QPalette.HighlightedText, QColor('white'))
        self.setPalette(palette)

        # 2. QSS (Cascading Style Sheets)
        qss = f"""
        QMainWindow {{
            background-color: {colors['bg']};
        }}
        QLabel {{
            color: {colors['fg']};
        }}
        QFrame {{
            background-color: {colors['bg']};
        }}

        QFrame#header_frame {{
            background-color: {colors['card_bg']};
            border-bottom: 3px solid {colors['accent']};
            border-radius: 0;
        }}

        QLabel#title_label {{
            color: {colors['accent']};
            font-family: 'Impact', 'Arial Black', sans-serif;
            font-size: 28px;
            font-weight: 900;
            padding: 10px 0; 
            letter-spacing: 2px;
            padding-left: 20px;
            padding-right: 20px;
        }}

        QPushButton#ThemeButtonCircle {{
            background: {colors['accent']};
            color: {colors['fg'] if self.current_theme == 'light' else 'white'}; 
            border: none;
            border-radius: 20px; 
            font-size: 18px;
            padding: 0;
            margin: 0; 
        }}
        QPushButton#ThemeButtonCircle:hover {{
            background: {colors['hover']};
        }}

        QFrame#InputCard {{
            background-color: {colors['card_bg']};
            border: 1px solid {colors['border']};
            border-radius: 12px; 
            padding: 15px;
        }}

        QSpinBox, QComboBox {{
            background-color: {colors['bg']};
            color: {colors['fg']};
            border: 1px solid {colors['border']};
            padding: 8px 5px;
            border-radius: 4px;
        }}
        QTextEdit, QLineEdit {{
            background-color: {colors['bg']};
            color: {colors['fg']};
            border: 1px solid {colors['border']};
            padding: 5px;
            border-radius: 4px;
        }}
        QTextEdit#ChatTextDisplay {{
            background-color: {colors['bg']};
            border: none;
        }}

        QPushButton#AccentButton {{
            background-color: {colors['accent']};
            color: white;
            border: none;
            border-radius: 10px; 
            padding: 10px 20px;
            font-weight: bold;
        }}
        QPushButton#AccentButton:hover {{
            background-color: {colors['hover']};
        }}
        QPushButton:disabled {{
            background-color: {colors['border']};
            color: {colors['fg']};
            border-radius: 10px;
        }}

        QRadioButton {{
            color: {colors['fg']};
            background-color: {colors['card_bg']};
            padding: 5px 0;
        }}

        QProgressBar#QuizProgressBar {{
            border: 1px solid {colors['border']};
            border-radius: 5px;
            background-color: {colors['border']};
            text-align: center;
            height: 10px;
        }}
        QProgressBar#QuizProgressBar::chunk {{
            background-color: {colors['accent']};
            border-radius: 5px;
        }}

        QTextEdit#ChatTextDisplay {{
            background-color: {colors['bg']};
            border: none;
        }}
        QFrame#ChatInputFrame {{
            background-color: {colors['card_bg']};
            border-top: 1px solid {colors['border']};
            border-radius: 0 0 12px 12px;
        }}
        QPushButton#ChatSendButton {{
            background-color: {colors['accent']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0;
            font-size: 11px;
        }}
        QPushButton#ChatSendButton:hover {{
            background-color: {colors['hover']};
        }}
        """

        self.setStyleSheet(qss)

        # 3. Apply chat background colors (Safe Widget Access Fix)
        if self.chatbot_text_display is not None:
            try:
                chat_palette = QPalette(self.chatbot_text_display.palette())
                chat_palette.setColor(QPalette.Base, QColor(colors['bg']))
                chat_palette.setColor(QPalette.Text, QColor(colors['fg']))
                self.chatbot_text_display.setPalette(chat_palette)
            except RuntimeError:
                pass

            # --- Main function setup ---


def main():
    sys.setrecursionlimit(2000)
    app = QApplication(sys.argv)
    window = QuizMakerApp()
    window.show()

    # Ensure worker thread is quit gracefully when the app closes
    def cleanup():
        if window.worker_thread.isRunning():
            window.worker_thread.quit()
            window.worker_thread.wait()

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
  
