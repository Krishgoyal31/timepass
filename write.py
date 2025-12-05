import sys
import os
import textwrap
import random
import glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QSize, QTimer, Qt
from PyQt5.QtWidgets import QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy
from PyQt5.QtGui import QFont, QColor, QPalette


# ---------------------------
# Line-based realistic renderer (v5)
# ---------------------------
def render_pages_handwritten_v5(
        text,
        font_path,
        font_size=40,
        page_width=1200,
        page_height=1600,
        margin=80,
        line_spacing=1.45,
        paper_style="plain",
        slant_degree=-6.0,
        line_jitter=0.9,
        rotation_deg=0.9,
        baseline_wave=1.8,
        pressure_variation=0.18,
):
    try:
        # Load the font. PIL will use a default if font_path is 'Default Font'
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
        font_path = "Default Font"

    max_width = page_width - 2 * margin

    # Calculate average character width for text wrapping
    try:
        # Use getbbox for better sizing calculation in modern PIL
        bbox = font.getbbox("M" * 10)
        avg_char_width = (bbox[2] - bbox[0]) / 10
    except Exception:
        # Fallback for older PIL versions or error
        avg_char_width = font_size * 0.55

    approx_chars = max(20, int(max_width / avg_char_width * 0.95))  # 95% factor for safety margin
    wrapped_lines = []

    # Text wrapping logic
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            wrapped_lines.append("")
        else:
            # Use textwrap to wrap long lines
            wrapped_lines.extend(textwrap.wrap(paragraph, width=approx_chars))

    line_height = int(font_size * line_spacing)
    usable_height = page_height - 2 * margin
    lines_per_page = max(1, usable_height // line_height)

    # Paginate lines
    pages_lines = [wrapped_lines[i:i + lines_per_page] for i in range(0, len(wrapped_lines), lines_per_page)]
    if not pages_lines:
        pages_lines = [[""]]  # Ensure at least one blank page if text is empty

    slant_rad = slant_degree * 3.14159 / 180.0
    pages = []

    for page_block in pages_lines:
        # Paper Style
        if paper_style == "yellow":
            bg = (255, 249, 196)
        else:
            bg = (255, 255, 255)

        page_img = Image.new("RGB", (page_width, page_height), bg)
        draw = ImageDraw.Draw(page_img)

        # Lined Paper effect
        if paper_style == "lined":
            for yline in range(margin, page_height - margin, line_height):
                draw.line([(margin, yline), (page_width - margin, yline)], fill=(200, 220, 255), width=2)

        y = margin
        for line in page_block:
            if line.strip() == "":
                y += line_height
                continue

            # Jitter and wave effects
            base_shift = random.uniform(-baseline_wave, baseline_wave)

            # Get size of the line
            try:
                # Use getbbox for modern PIL sizing
                bbox = font.getbbox(line)
                w_w = bbox[2] - bbox[0]
                w_h = bbox[3] - bbox[1]
            except Exception:
                try:
                    # Fallback for older PIL/Pillow getsize
                    w_w, w_h = font.getsize(line)
                except Exception:
                    # Generic fallback
                    w_w, w_h = font_size * len(line) * 0.55, font_size

            if w_w > max_width:
                w_w = max_width

            # Create an intermediate image for transformations
            pad = max(12, int(font_size * 0.2))
            tmp_w = int(w_w + pad * 2)
            tmp_h = int(w_h + pad * 2)

            line_img = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
            ldraw = ImageDraw.Draw(line_img)

            # Draw text with slight offset for 'pressure' effect
            for layer in range(2):
                offset = layer * pressure_variation * 1.8
                ldraw.text((pad + offset, pad + offset), line, font=font, fill=(10, 10, 10, 255))

            # Apply slight blur for ink bleed
            if pressure_variation > 0.01:
                line_img = line_img.filter(ImageFilter.GaussianBlur(radius=0.12))

            # Apply Slant (Shear) transformation
            try:
                line_img = line_img.transform(
                    line_img.size,
                    Image.AFFINE,
                    (1.0, slant_rad, 0.0, 0.0, 1.0, 0.0),
                    resample=Image.BICUBIC,
                )
            except Exception:
                pass  # Ignore error if transform fails

            # Apply Rotation
            angle = random.uniform(-rotation_deg, rotation_deg)
            line_img = line_img.rotate(angle, expand=True, resample=Image.BICUBIC)

            # Calculate final paste position with jitter
            paste_x = int(margin + random.uniform(-line_jitter, line_jitter))
            # Subtract 'pad' because line_img includes it in its height calculation
            paste_y = int(y + base_shift - pad + random.uniform(-line_jitter, line_jitter))

            # Ensure coordinates are within bounds
            paste_x = max(0, min(paste_x, page_width - line_img.width))
            paste_y = max(0, min(paste_y, page_height - line_img.height))

            # Paste the transformed line onto the page
            page_img.paste(line_img, (paste_x, paste_y), line_img)

            y += line_height

        # Final page-level slight blur
        page_img = page_img.filter(ImageFilter.GaussianBlur(radius=0.06))
        pages.append(page_img)

    return pages


# ---------------------------
# PyQt5 GUI
# ---------------------------
class HandwrittenNotesApp(QtWidgets.QWidget):
    def __init__(self, app_instance):
        super().__init__()
        self.setWindowTitle("Made by Krish 🔧")
        self.resize(1400, 850)

        self.app = app_instance
        self.pages = []
        self.page_index = 0
        self.current_image = None
        self.available_fonts = {}
        self.dark_mode = False

        self._build_ui()
        self._populate_system_fonts()

        # Apply initial theme (which is toggled once)
        self.dark_mode = True
        self.toggle_theme()

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # --- HEADER ---
        header_container = QtWidgets.QHBoxLayout()
        header_container.setContentsMargins(20, 0, 20, 0)

        # Spacer to align the title
        header_container.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Main Title
        self.header_widget = QtWidgets.QLabel("VenomWrite Lab")
        self.header_widget.setObjectName("mainHeaderTitle")
        self.header_widget.setAlignment(QtCore.Qt.AlignCenter)
        self.header_widget.setFixedHeight(40)
        header_container.addWidget(self.header_widget)

        # Spacer to push the button all the way to the right
        header_container.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Toggle Button
        self.theme_btn = QPushButton("🌙", self)
        self.theme_btn.setObjectName("themeButtonCircle")
        self.theme_btn.setFixedSize(QSize(40, 40))
        self.theme_btn.clicked.connect(self.toggle_theme)
        header_container.addWidget(self.theme_btn)

        main_layout.addLayout(header_container)

        # Separator Line
        separator = QWidget()
        separator.setFixedHeight(3)
        separator.setObjectName("HeaderSeparator")
        main_layout.addWidget(separator)

        content_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(content_layout)

        # --- LEFT PANEL (Controls) ---
        left = QtWidgets.QVBoxLayout()
        # Adjusted: Reduced the left margin for the entire left panel to shift content left
        left.setContentsMargins(5, 10, 10, 10)
        content_layout.addLayout(left, 1)

        # QHBoxLayout for "Input Text:" label (to allow it to be truly left-aligned)
        input_text_label_layout = QtWidgets.QHBoxLayout()
        input_text_label = QtWidgets.QLabel("Input Text:", objectName="LabelText")
        input_text_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        input_text_label_layout.addWidget(input_text_label)
        input_text_label_layout.addStretch(1)  # This pushes the label to the very left
        left.addLayout(input_text_label_layout)

        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type or load text here...")
        self.text_edit.setObjectName("InputTextEdit")
        # FIX 1: Restore correct stretch on the text box (using factor 3)
        left.addWidget(self.text_edit, 3)

        bc = QtWidgets.QHBoxLayout()
        load_btn = QtWidgets.QPushButton("Load Text File")
        load_btn.clicked.connect(self.load_text)
        bc.addWidget(load_btn)

        clr = QtWidgets.QPushButton("Clear")
        clr.clicked.connect(self.text_edit.clear)
        bc.addWidget(clr)
        left.addLayout(bc)

        # Font Selection
        font_row = QtWidgets.QHBoxLayout()
        font_row.addWidget(QtWidgets.QLabel("Font:", objectName="LabelText"))
        self.font_combo = QtWidgets.QComboBox()
        font_row.addWidget(self.font_combo)
        choose = QtWidgets.QPushButton("Choose Font (.ttf)")
        choose.clicked.connect(self.choose_font)
        font_row.addWidget(choose)
        left.addLayout(font_row)

        # Font Size & Paper Style
        settings_row = QtWidgets.QHBoxLayout()

        settings_row.addWidget(QtWidgets.QLabel("Size:", objectName="LabelText"))
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(18, 100)
        self.font_size.setValue(40)
        settings_row.addWidget(self.font_size)

        settings_row.addWidget(QtWidgets.QLabel("Paper:", objectName="LabelText"))
        self.paper_combo = QtWidgets.QComboBox()
        self.paper_combo.addItems(["plain", "lined", "yellow"])
        settings_row.addWidget(self.paper_combo)

        left.addLayout(settings_row)

        # Action Buttons
        action_row = QtWidgets.QHBoxLayout()
        gen = QtWidgets.QPushButton("Generate Preview")
        gen.clicked.connect(self.generate_preview)
        action_row.addWidget(gen)

        save_png = QtWidgets.QPushButton("Save PNGs")
        save_png.clicked.connect(self.save_pngs)
        action_row.addWidget(save_png)

        save_pdf = QtWidgets.QPushButton("Save PDF")
        save_pdf.clicked.connect(self.save_pdf)
        action_row.addWidget(save_pdf)

        left.addLayout(action_row)

        self.tip_label = QtWidgets.QLabel(
            "Tip: use a handwriting font (Patrick Hand, Caveat, Homemade Apple)",
            objectName="TipLabel"
        )
        left.addWidget(self.tip_label)

        # FIX 2: Add correct stretch at the VERY END of the left panel
        left.addStretch()

        # --- RIGHT PANEL (Preview) ---
        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        content_layout.addLayout(right, 1)

        right.addWidget(QtWidgets.QLabel("Preview:", objectName="LabelText"))

        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setObjectName("PreviewLabel")
        # FIX 3: Set fixed height to control overall content size
        self.preview_label.setFixedHeight(800)
        self.preview_label.setAlignment(Qt.AlignCenter)

        right.addWidget(self.preview_label, 6)

        # Navigation
        nav = QtWidgets.QHBoxLayout()
        self.prev_btn = QtWidgets.QPushButton("◀ Prev")
        self.prev_btn.setObjectName("NavButton")
        self.prev_btn.clicked.connect(self.prev_page)
        nav.addWidget(self.prev_btn)

        self.page_label = QtWidgets.QLabel("Page 0 / 0", objectName="PageLabel")
        self.page_label.setAlignment(QtCore.Qt.AlignCenter)
        nav.addWidget(self.page_label, 1)

        self.next_btn = QtWidgets.QPushButton("Next ▶")
        self.next_btn.setObjectName("NavButton")
        self.next_btn.clicked.connect(self.next_page)
        nav.addWidget(self.next_btn)

        right.addLayout(nav)

        self.status = QtWidgets.QLabel("Ready.", objectName="StatusLabel")
        right.addWidget(self.status)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_page(self.page_index)

    def _populate_system_fonts(self):
        font_paths = []

        if sys.platform == "win32":
            font_dirs = [os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts"]
        elif sys.platform == "darwin":
            font_dirs = ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
        else:
            font_dirs = ["/usr/share/fonts/truetype", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]

        prioritized_names = [
            "Patrick Hand", "Caveat", "Homemade Apple", "Permanent Marker", "Indie Flower",
            "Arial", "Times New Roman", "Consolas"
        ]

        for d in font_dirs:
            for pattern in ["*.ttf", "*.otf"]:
                for font_file in glob.glob(os.path.join(d, pattern), recursive=True):
                    base_name = os.path.splitext(os.path.basename(font_file))[0]
                    if base_name not in self.available_fonts:
                        self.available_fonts[base_name] = font_file

        display_names = []
        for name in prioritized_names:
            if name in self.available_fonts:
                display_names.append(name)

        other_names = sorted(
            [name for name in self.available_fonts if name not in prioritized_names])
        display_names.extend(other_names)

        for name in display_names:
            self.font_combo.addItem(name, self.available_fonts.get(name))

        default_font = "Patrick Hand"
        if default_font in self.available_fonts:
            self.font_combo.setCurrentText(default_font)
        elif self.font_combo.count() > 0:
            self.font_combo.setCurrentIndex(0)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode

        if self.dark_mode:
            self.setStyleSheet(self._get_dark_stylesheet())
            self.theme_btn.setText("🌝")
        else:
            self.setStyleSheet(self._get_light_stylesheet())
            self.theme_btn.setText("🌚")

        self.app.processEvents()

    def _get_light_stylesheet(self):
        PRIMARY_ACCENT = "#7F5EFA"
        SOFT_BACKGROUND = "#F5F6FA"
        TEXT_COLOR = "#2F2F4F"
        HOVER_ACCENT = "#9B70FF"

        return f"""
            QWidget {{ background-color: {SOFT_BACKGROUND}; color: {TEXT_COLOR}; }}

            #mainHeaderTitle {{
                background-color: transparent;
                color: {PRIMARY_ACCENT};
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 24px;
                font-weight: 900;
                padding: 5px 0;
                letter-spacing: 2px;
                min-height: 40px;
            }}
            #HeaderSeparator {{
                background-color: {PRIMARY_ACCENT};
                border: none;
                margin: 0;
            }}

            #themeButtonCircle {{
                background: {PRIMARY_ACCENT};
                color: white;
                border: 1px solid {PRIMARY_ACCENT};
                border-radius: 20px;
                font-size: 22px;       
                padding: 0px;          
                line-height: 40px;     
                text-align: center;    
            }}
            #themeButtonCircle:hover {{
                background: {HOVER_ACCENT};
                border: 1px solid {HOVER_ACCENT};
            }}
            #themeButtonCircle:pressed {{
                background: #5D43C1;
                border: 1px solid #5D43C1;
            }}

            #LabelText, #PageLabel, #TipLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
                padding: 5px 0;
            }}
            #TipLabel {{ color: #A9A9A9; font-style: italic; }}
            #StatusLabel {{ color: {PRIMARY_ACCENT}; font-weight: bold; font-size: 14px; }}

            #InputTextEdit {{
                background-color: white;
                color: {TEXT_COLOR};
                border: 1px solid #CCC;
                border-radius: 6px;
                padding: 5px;
            }}
            #PreviewLabel {{
                background-color: #FFFFFF;
                border: 2px solid #EBE9F5;
                border-radius: 8px;
            }}

            QPushButton {{
                background-color: {PRIMARY_ACCENT};
                color: white;
                border: none;
                padding: 7px 10px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #9B70FF;
            }}
            QPushButton:pressed {{
                background-color: #5D43C1;
            }}

            #NavButton {{
                background-color: transparent;
                color: {TEXT_COLOR};
                border: 1px solid {PRIMARY_ACCENT};
                padding: 5px 10px;
                border-radius: 8px;
                font-size: 12px;
            }}
            #NavButton:hover {{
                background-color: {PRIMARY_ACCENT}10;
            }}

            QComboBox, QSpinBox {{
                border: 1px solid #CCC;
                border-radius: 4px;
                padding: 5px;
                color: {TEXT_COLOR};
                background-color: white;
            }}
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
                border: none; background-color: transparent;
            }}
        """

    def _get_dark_stylesheet(self):
        PRIMARY_ACCENT = "#9B70FF"
        SOFT_BACKGROUND = "#1A1523"
        PANEL_BACKGROUND = "#282038"
        TEXT_COLOR = "#EBE9F5"
        HOVER_ACCENT = "#7F5EFA"

        return f"""
            QWidget {{ background-color: {SOFT_BACKGROUND}; color: {TEXT_COLOR}; }}

            #mainHeaderTitle {{
                background-color: transparent;
                color: {PRIMARY_ACCENT};
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 24px;
                font-weight: 900;
                padding: 5px 0;
                letter-spacing: 2px;
                min-height: 40px;
            }}
            #HeaderSeparator {{
                background-color: {PRIMARY_ACCENT};
                border: none;
                margin: 0;
            }}

            #themeButtonCircle {{
                background: {PRIMARY_ACCENT};
                color: {TEXT_COLOR}; 
                border: 1px solid {PRIMARY_ACCENT};
                border-radius: 20px;
                font-size: 22px;       
                padding: 0px;          
                line-height: 40px;     
                text-align: center;    
            }}
            #themeButtonCircle:hover {{
                background: {HOVER_ACCENT};
                border: 1px solid {HOVER_ACCENT};
            }}
            #themeButtonCircle:pressed {{
                background: #5D43C1;
                border: 1px solid #5D43C1;
            }}

            #LabelText, #PageLabel, #TipLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
                padding: 5px 0;
            }}
            #TipLabel {{ color: #777; font-style: italic; }}
            #StatusLabel {{ color: #00FFFF; font-weight: bold; font-size: 14px; }}

            #InputTextEdit {{
                background-color: {PANEL_BACKGROUND};
                color: {TEXT_COLOR};
                border: 1px solid #453A5A;
                border-radius: 6px;
                padding: 5px;
            }}
            #PreviewLabel {{
                background-color: #FFFFFF;
                border: 2px solid #352D45;
                border-radius: 8px;
            }}

            QPushButton {{
                background-color: {PRIMARY_ACCENT};
                color: white;
                border: none;
                padding: 7px 10px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #7F5EFA;
            }}
            QPushButton:pressed {{
                background-color: #5D43C1;
            }}

            #NavButton {{
                background-color: transparent;
                color: {TEXT_COLOR};
                border: 1px solid {PRIMARY_ACCENT};
                padding: 5px 10px;
                border-radius: 8px;
                font-size: 12px;
            }}
            #NavButton:hover {{
                background-color: {PANEL_BACKGROUND};
            }}

            QComboBox, QSpinBox {{
                border: 1px solid #453A5A;
                border-radius: 4px;
                padding: 5px;
                color: {TEXT_COLOR};
                background-color: {PANEL_BACKGROUND};
            }}
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
                border: none; background-color: transparent;
            }}
        """

    def load_text(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open text file", "", "Text Files (*.txt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.text_edit.setPlainText(f.read())
            except Exception as e:
                self.status.setText(f"Error loading file: {e}")

    def choose_font(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Font (.ttf/.otf)", "", "Fonts (*.ttf *.otf)")
        if path:
            font_name = os.path.splitext(os.path.basename(path))[0]

            if self.available_fonts.get(font_name) != path:
                self.available_fonts[font_name] = path
                self.font_combo.addItem(font_name, path)
                self.font_combo.setCurrentText(font_name)

    def generate_preview(self):
        text = self.text_edit.toPlainText()
        if not text.strip():
            self.status.setText("Enter text first.")
            return

        current_index = self.font_combo.currentIndex()
        if current_index == -1:
            self.status.setText("No font selected.")
            return

        font_path = self.font_combo.itemData(current_index)
        if not font_path:
            font_path = self.font_combo.currentText()

        if not font_path or (font_path != "Default Font" and not os.path.exists(font_path)):
            self.status.setText("Error: Font file not found or selected.")
            return

        self.status.setText("Generating pages... Please wait.")
        self.app.processEvents()

        try:
            self.pages = render_pages_handwritten_v5(
                text=text,
                font_path=font_path,
                font_size=self.font_size.value(),
                paper_style=self.paper_combo.currentText(),
                slant_degree=-6.0,
                line_jitter=0.9,
                rotation_deg=0.9,
                baseline_wave=1.6,
                pressure_variation=0.15,
            )
            self.page_index = 0
            self.show_page(0)
            self.status.setText(f"Generated {len(self.pages)} page(s).")
        except Exception as e:
            self.status.setText("Error during rendering: " + str(e))

    def show_page(self, idx):
        if not self.pages:
            self.preview_label.clear()
            self.page_label.setText("Page 0 / 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        idx = max(0, min(idx, len(self.pages) - 1))
        self.page_index = idx

        pil_img = self.pages[idx]
        qimg = pil_to_qimage(pil_img)
        pix = QtGui.QPixmap.fromImage(qimg)

        # Scale the pixmap to fit the preview area while maintaining aspect ratio
        pix = pix.scaled(
            self.preview_label.width(),
            self.preview_label.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        self.preview_label.setPixmap(pix)
        self.page_label.setText(f"Page {idx + 1} / {len(self.pages)}")
        self.prev_btn.setEnabled(idx > 0)
        self.next_btn.setEnabled(idx < len(self.pages) - 1)

    def prev_page(self):
        if self.page_index > 0:
            self.show_page(self.page_index - 1)

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.show_page(self.page_index + 1)

    def save_pngs(self):
        if not self.pages:
            self.status.setText("No pages to save.")
            return

        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder to save PNGs")
        if not folder:
            return

        base = "handwritten_page"
        try:
            for i, p in enumerate(self.pages, start=1):
                fname = os.path.join(folder, f"{base}_{i}.png")
                # Ensure saved in RGB format for compatibility
                p.convert("RGB").save(fname, "PNG")

            self.status.setText(f"Saved {len(self.pages)} PNG(s) to {folder}")
        except Exception as e:
            self.status.setText("Error saving PNGs: " + str(e))

    def save_pdf(self):
        if not self.pages:
            self.status.setText("No pages to save.")
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save PDF", "handwritten_notes.pdf", "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            rgb_pages = [p.convert("RGB") for p in self.pages]
            if rgb_pages:
                # Save the first page, then append the rest
                rgb_pages[0].save(path, save_all=True, append_images=rgb_pages[1:], format="PDF")
                self.status.setText(f"Saved PDF: {path}")
            else:
                self.status.setText("No pages to save.")
        except Exception as e:
            self.status.setText("Error saving PDF: " + str(e))


# ---------------------------
# PIL → QImage helper
# ---------------------------
def pil_to_qimage(img):
    # Ensure image is in RGBA format for PyQt to handle transparency correctly
    img = img.convert("RGBA")
    # Convert image data to a QImage object
    data = img.tobytes("raw", "RGBA")
    return QtGui.QImage(data, img.width, img.height, img.width * 4, QtGui.QImage.Format_RGBA8888)


# ---------------------------
# Run App
# ---------------------------
if __name__ == "__main__":
    # Check if a QApplication instance already exists
    if not QtWidgets.QApplication.instance():
        app = QtWidgets.QApplication(sys.argv)
    else:
        app = QtWidgets.QApplication.instance()

    w = HandwrittenNotesApp(app)
    w.show()

    # Start the PyQt event loop
    sys.exit(app.exec_())
