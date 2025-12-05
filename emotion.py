import sys
import cv2
import numpy as np
from datetime import datetime, timedelta
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit,
                             QLineEdit, QScrollArea, QFrame, QFileDialog,
                             QTabWidget, QProgressBar, QSpinBox, QCheckBox,
                             QGridLayout, QGraphicsView, QGraphicsScene,
                             QSlider, QStyle, QGraphicsEllipseItem, QGraphicsRectItem,
                             QSizePolicy)
from PyQt6.QtCore import (QTimer, Qt, QPropertyAnimation, QEasingCurve,
                          pyqtSignal, QThread, QSize, QRectF, QPointF,
                          QPoint, pyqtProperty, QMutex, QEvent)
from PyQt6.QtGui import (QImage, QPixmap, QFont, QIcon, QPalette, QColor,
                         QBrush, QPen, QPainter, QImage, QKeyEvent, QRadialGradient, QLinearGradient, QPainterPath)
from PyQt6.QtGui import QFontDatabase
import json
import sqlite3
from pathlib import Path
import requests
from collections import Counter, deque
import time
import random
import math
import threading

# --- EXTERNAL LIBRARY IMPORTS ---
PYGAME_AVAILABLE = False
NUMPY_AVAILABLE = False

try:
    import pygame

    pygame.mixer.pre_init(44100, -16, 2, 512)
    PYGAME_AVAILABLE = True
except ImportError:
    pass

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    if PYGAME_AVAILABLE:
        pass
    NUMPY_AVAILABLE = False

# Initialize pygame if available
if PYGAME_AVAILABLE:
    try:
        if not pygame.get_init():
            pygame.init()
    except Exception as e:
        PYGAME_AVAILABLE = False

# Voice support
try:
    import pyttsx3
    import speech_recognition as sr

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# Emotion detection
try:
    from fer import FER

    FER_AVAILABLE = True
except ImportError:
    FER_AVAILABLE = False

# Plotting
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt

    plt.style.use('seaborn-v0_8-darkgrid')
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False

# --- CONFIGURATION CONSTANTS (Tuned for Stability) ---
CONFIDENCE_THRESHOLD = 0.55
SMOOTHING_WINDOW_SIZE = 75
DETECTION_INTERVAL = 5

# --- ZEN FLOW CONFIG ---
ZEN_FLOW_GRAVITY = 0.25
FRICTION = 0.998
BOUNCE_FACTOR = 0.5
MAX_BALLS = 200
FRAME_RATE_MS = 16
TRAIL_LENGTH = 60
GLOBAL_SOUND_COOLDOWN = 0.05
LAST_GLOBAL_SOUND_TIME = 0.0

# Enhanced Color Palettes
COLOR_THEMES = {
    'Ocean': [QColor(0x80DEEA), QColor(0x90CAF9), QColor(0xA59FE5), QColor(0xC7A8D7), QColor(0xB39DDB)],
    'Sunset': [QColor(0xFF6B6B), QColor(0xFFBE76), QColor(0xFECA57), QColor(0xFF7979), QColor(0xFFAA92)],
    'Forest': [QColor(0x6BCF7F), QColor(0x7DE5A1), QColor(0x95E1D3), QColor(0xAAF0D1), QColor(0xC7FFED)],
    'Aurora': [QColor(0x00D2FF), QColor(0x3A7BD5), QColor(0x928DAB), QColor(0xB695F8), QColor(0xE74EFF)]
}

CURRENT_THEME = 'Ocean'
CALM_COLORS = COLOR_THEMES[CURRENT_THEME]

# --- Sound Setup ---
TONE_BANK = []
SOUND_READY = PYGAME_AVAILABLE and NUMPY_AVAILABLE
sound_mutex = threading.Lock()

if SOUND_READY:
    def generate_calming_sound(freq, duration=0.15):
        sample_rate = 44100
        n_samples = int(round(duration * sample_rate))
        t = np.arange(n_samples) / sample_rate
        sine_wave = (2 ** 15 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
        window = np.hanning(n_samples)
        sine_wave_env = (sine_wave * window * 0.3).astype(np.int16)
        return pygame.mixer.Sound(sine_wave_env.tobytes())


    try:
        TONE_BANK = [
            generate_calming_sound(261.63),
            generate_calming_sound(293.66),
            generate_calming_sound(329.63),
            generate_calming_sound(392.00),
            generate_calming_sound(440.00),
        ]
        TONE_BANK = [s for s in TONE_BANK if s is not None]
        if not TONE_BANK:
            SOUND_READY = False
    except Exception as e:
        SOUND_READY = False


def play_calming_tone_async():
    global LAST_GLOBAL_SOUND_TIME

    if not SOUND_READY or not TONE_BANK:
        return

    current_time = time.time()
    if current_time - LAST_GLOBAL_SOUND_TIME < GLOBAL_SOUND_COOLDOWN:
        return

    LAST_GLOBAL_SOUND_TIME = current_time

    def run_sound():
        if sound_mutex.acquire(blocking=False):
            try:
                channel = pygame.mixer.find_channel(True)
                if channel:
                    channel.play(random.choice(TONE_BANK), fade_ms=80)
            finally:
                sound_mutex.release()

    thread = threading.Thread(target=run_sound)
    thread.daemon = True
    thread.start()


# ============================================================================
# ZEN FLOW LAUNCHER (NEW GAME IMPLEMENTATION)
# ============================================================================

# --- Star Background ---
class Star:
    def __init__(self, x, y, size, speed):
        self.x = x
        self.y = y
        self.size = size
        self.vy = speed * 0.05
        self.brightness = random.uniform(0.3, 1.0)
        self.twinkle_speed = random.uniform(0.01, 0.03)
        self.twinkle_phase = random.uniform(0, math.pi * 2)

    def update(self, height):
        self.twinkle_phase += self.twinkle_speed
        self.brightness = 0.5 + 0.5 * math.sin(self.twinkle_phase)

        self.y += self.vy
        if self.y > height:
            self.y = 0


# --- Particle Effect ---
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-8, -3)
        self.color = color
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.04)
        self.size = random.uniform(2, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3
        self.life -= self.decay
        return self.life > 0


# --- Ball Class ---
class Ball:
    def __init__(self, x, y, radius, color, vx=0, vy=0):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.vx = vx
        self.vy = vy
        self.is_resting = False
        self.positions = []
        self.speed = 0
        self.impact_flash = 0
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-5, 5)
        self.last_sound_time = 0.0
        self.sound_cooldown = 0.1

    def update(self, width, height, sound_enabled):
        current_time = time.time()

        if self.is_resting:
            if self.positions:
                self.positions.pop(0)
            self.impact_flash = max(0, self.impact_flash - 0.05)
            return None

        self.positions.append(QPoint(int(self.x), int(self.y)))
        if len(self.positions) > TRAIL_LENGTH:
            self.positions.pop(0)

        self.vx *= FRICTION
        self.vy += ZEN_FLOW_GRAVITY

        self.x += self.vx
        self.y += self.vy

        self.speed = math.sqrt(self.vx ** 2 + self.vy ** 2)
        self.rotation += self.rotation_speed

        self.impact_flash = max(0, self.impact_flash - 0.05)

        particles = []

        # Wall Collision
        if self.x + self.radius > width or self.x - self.radius < 0:
            impact_vel = abs(self.vx)

            self.vx *= -BOUNCE_FACTOR
            if self.x + self.radius > width:
                self.x = width - self.radius
            if self.x - self.radius < 0:
                self.x = self.radius
            self.impact_flash = 0.5
            if abs(self.vx) > 2:
                particles.extend(self._create_particles(5))

            if sound_enabled and current_time - self.last_sound_time > self.sound_cooldown and impact_vel > 8:
                play_calming_tone_async()
                self.last_sound_time = current_time

        # Floor Collision
        if self.y + self.radius > height:
            impact_vel = abs(self.vy)

            self.vy *= -BOUNCE_FACTOR
            self.y = height - self.radius
            self.impact_flash = min(1.0, impact_vel / 20)

            if impact_vel > 3:
                particles.extend(self._create_particles(int(impact_vel)))

            if sound_enabled and current_time - self.last_sound_time > self.sound_cooldown and impact_vel > 8:
                play_calming_tone_async()
                self.last_sound_time = current_time

            if abs(self.vy) < 0.5 and abs(self.vx) < 0.2:
                self.vy = 0
                self.vx = 0
                self.is_resting = True

        return particles

    def _create_particles(self, count):
        return [Particle(self.x, self.y, self.color) for _ in range(count)]


# --- Canvas Widget ---
class ZenFlowCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(QSize(800, 600))
        self.setStyleSheet("background-color: #000510; border-radius: 12px;")
        self.balls = []
        self.particles = []

        self.stars = []

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.is_dragging = False
        self.drag_start = None
        self.drag_current = None

        self.rain_mode = False
        self.rain_timer = QTimer(self)
        self.rain_timer.timeout.connect(self.rain_drop)

        self.show_stats = True
        self.sound_enabled = SOUND_READY
        self.gravity_multiplier = 1.0

        self.fps = 60
        self.frame_times = []
        self.last_frame_time = time.time()

        self._window_opacity = 1.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(FRAME_RATE_MS)

        QTimer.singleShot(50, self.initialize_stars_full_screen)

    def getWindowOpacity(self):
        return self._window_opacity

    def setWindowOpacity(self, value):
        self._window_opacity = value
        self.update()

    windowOpacity = pyqtProperty(float, getWindowOpacity, setWindowOpacity)

    def initialize_stars_full_screen(self):
        """Creates stars across the currently set canvas dimensions."""
        width = self.width()
        height = self.height()

        if width > 0 and height > 0:
            self.stars.clear()
            self.stars = [Star(random.uniform(0, width), random.uniform(0, height),
                               random.uniform(1, 2.5), random.uniform(0.1, 0.5))
                          for _ in range(150)]
            self.update()

    def resizeEvent(self, event):
        """Re-initialize stars when the window is resized to keep them spread out."""
        super().resizeEvent(event)
        if self.stars:
            self.initialize_stars_full_screen()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        width = self.width()
        height = self.height()

        # Background gradient
        bg_gradient = QLinearGradient(0, 0, 0, height)
        bg_gradient.setColorAt(0, QColor(0x000510))
        bg_gradient.setColorAt(1, QColor(0x0a0520))
        painter.fillRect(0, 0, width, height, bg_gradient)

        painter.setOpacity(self._window_opacity)

        # Draw stars
        for star in self.stars:
            star_color = QColor(255, 255, 255, int(star.brightness * 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(star_color)
            painter.drawEllipse(QPointF(star.x, star.y), star.size, star.size)

        # Draw particles
        for particle in self.particles:
            p_color = QColor(particle.color)
            p_color.setAlpha(int(particle.life * 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(p_color)
            painter.drawEllipse(QPointF(particle.x, particle.y), particle.size, particle.size)

        # Draw balls with glow
        for ball in self.balls:
            # Trail
            if len(ball.positions) > 1:
                for i in range(len(ball.positions) - 1):
                    alpha = int((i / len(ball.positions)) * 120)
                    trail_color = QColor(ball.color)
                    trail_color.setAlpha(alpha)
                    painter.setPen(QPen(trail_color, ball.radius * 0.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    painter.drawLine(ball.positions[i], ball.positions[i + 1])

            # Glow effect
            glow_radius = ball.radius * 2.5
            glow = QRadialGradient(ball.x, ball.y, glow_radius)
            glow_color = QColor(ball.color)
            glow_color.setAlpha(int(60 + ball.impact_flash * 100))
            glow.setColorAt(0, glow_color)
            glow_color.setAlpha(0)
            glow.setColorAt(1, glow_color)
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ball.x, ball.y), glow_radius, glow_radius)

            # Main ball with gradient
            ball_gradient = QRadialGradient(
                ball.x - ball.radius * 0.3,
                ball.y - ball.radius * 0.3,
                ball.radius * 1.5
            )

            highlight = QColor(ball.color).lighter(140)
            highlight.setAlpha(255)
            ball_gradient.setColorAt(0, highlight)
            ball_gradient.setColorAt(0.7, ball.color)

            shadow = QColor(ball.color).darker(120)
            ball_gradient.setColorAt(1, shadow)

            painter.setBrush(ball_gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ball.x, ball.y), ball.radius, ball.radius)

            # Impact flash
            if ball.impact_flash > 0:
                flash_color = QColor(255, 255, 255, int(ball.impact_flash * 150))
                painter.setBrush(flash_color)
                painter.drawEllipse(QPointF(ball.x, ball.y),
                                    ball.radius * 0.7, ball.radius * 0.7)

        # Draw aim line when dragging
        if self.is_dragging and self.drag_start and self.drag_current:
            painter.setPen(QPen(QColor(255, 255, 255, 150), 2, Qt.PenStyle.DashLine))
            painter.drawLine(self.drag_start, self.drag_current)

            # Draw power indicator
            dx = self.drag_current.x() - self.drag_start.x()
            dy = self.drag_current.y() - self.drag_start.y()
            power = min(math.sqrt(dx ** 2 + dy ** 2) / 10, 20)

            painter.setPen(QPen(QColor(128, 222, 234, 200), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            center_point_f = QPointF(self.drag_start)
            painter.drawEllipse(center_point_f, 20 + power * 1.5, 20 + power * 1.5)

        # Stats overlay
        if self.show_stats:
            painter.setOpacity(1.0)
            painter.setPen(QColor(128, 222, 234, 180))

            painter.setFont(QFont("Arial", 11))
            stats_text = f"Orbs: {len(self.balls)} | FPS: {self.fps} | Theme: {CURRENT_THEME} | Rain: {'ON' if self.rain_mode else 'OFF'}"
            painter.drawText(15, 25, stats_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_start = event.position().toPoint()
            self.drag_current = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            for _ in range(5):
                self.launch_ball(event.position().x(), event.position().y(),
                                 random.uniform(-4, 4), random.uniform(-25, -15))
        self.setFocus()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.drag_current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            dx = self.drag_current.x() - self.drag_start.x()
            dy = self.drag_current.y() - self.drag_start.y()

            launch_scale = 0.35
            launch_vx = dx * launch_scale
            launch_vy = dy * launch_scale - 10

            max_vel = 40
            current_vel = math.sqrt(launch_vx ** 2 + launch_vy ** 2)
            if current_vel > max_vel:
                ratio = max_vel / current_vel
                launch_vx *= ratio
                launch_vy *= ratio

            self.launch_ball(self.drag_start.x(), self.drag_start.y(), launch_vx, launch_vy)

            self.is_dragging = False
            self.drag_start = None
            self.drag_current = None
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            x = random.uniform(100, self.width() - 100)
            y = random.uniform(50, 200)
            self.launch_ball(x, y, random.uniform(-8, 8), random.uniform(-30, -20))

        elif event.key() == Qt.Key.Key_C:
            self.balls.clear()
            self.particles.clear()

        elif event.key() == Qt.Key.Key_R:
            self.rain_mode = not self.rain_mode
            if self.rain_mode:
                self.rain_timer.start(200)
            else:
                self.rain_timer.stop()

        elif event.key() == Qt.Key.Key_S:
            self.show_stats = not self.show_stats

        elif event.key() == Qt.Key.Key_T:
            themes = list(COLOR_THEMES.keys())
            global CURRENT_THEME, CALM_COLORS
            current_idx = themes.index(CURRENT_THEME)
            CURRENT_THEME = themes[(current_idx + 1) % len(themes)]
            CALM_COLORS = COLOR_THEMES[CURRENT_THEME]
            self.update()

        super().keyPressEvent(event)

    def launch_ball(self, x, y, vx=None, vy=None):
        radius = random.uniform(9, 16)
        color = random.choice(CALM_COLORS)

        if vx is None:
            vx = random.uniform(-6, 6)
        if vy is None:
            vy = random.uniform(-30, -15)

        new_ball = Ball(x, y, radius, color, vx, vy)
        self.balls.append(new_ball)

        if len(self.balls) > MAX_BALLS:
            self.balls.pop(0)

    def rain_drop(self):
        x = random.uniform(50, self.width() - 50)
        self.launch_ball(x, 0, random.uniform(-2, 2), random.uniform(-1, 1))

    def animate(self):
        # FPS calculation
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        self.frame_times.append(frame_time)
        if len(self.frame_times) > 30:
            self.frame_times.pop(0)
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        self.fps = int(1.0 / avg_frame_time) if avg_frame_time > 0 else 60

        width = self.width()
        height = self.height()

        # Update stars
        for star in self.stars:
            star.update(height)

        # Update balls
        global ZEN_FLOW_GRAVITY
        original_gravity = ZEN_FLOW_GRAVITY
        ZEN_FLOW_GRAVITY = original_gravity * self.gravity_multiplier

        balls_to_keep = []
        for ball in self.balls:
            new_particles = ball.update(width, height, self.sound_enabled)
            if new_particles:
                self.particles.extend(new_particles)
            if not ball.is_resting or len(ball.positions) > 0:
                balls_to_keep.append(ball)

        self.balls = balls_to_keep

        ZEN_FLOW_GRAVITY = original_gravity

        # Update particles
        self.particles = [p for p in self.particles if p.update()]

        self.update()


# --- Settings Panel ---
class SettingsPanel(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.setStyleSheet("""
            QWidget {
                background-color: #10101e;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel {
                color: #80deea;
                font-size: 13px;
            }
            QPushButton {
                background-color: #1a1a2e;
                color: #80deea;
                border: 1px solid #80deea;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #80deea;
                color: #1a1a2e;
            }
            QCheckBox {
                color: #80deea;
                font-size: 12px;
                padding: 5px 0;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #1a1a2e;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #80deea;
                border: 1px solid #5aa7b3;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

        layout = QVBoxLayout()

        # Title
        title = QLabel("⚙️ CONTROLS")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Sound toggle
        self.sound_check = QCheckBox("Sound Effects")
        self.sound_check.setChecked(canvas.sound_enabled)
        self.sound_check.stateChanged.connect(self.toggle_sound)
        if not SOUND_READY:
            self.sound_check.setEnabled(False)
            self.sound_check.setText("Sound Effects (Unavailable)")
        layout.addWidget(self.sound_check)

        # Stats toggle
        self.stats_check = QCheckBox("Show Stats (S)")
        self.stats_check.setChecked(canvas.show_stats)
        self.stats_check.stateChanged.connect(self.toggle_stats)
        layout.addWidget(self.stats_check)

        # Gravity slider
        gravity_label = QLabel("Gravity Multiplier:")
        layout.addWidget(gravity_label)

        self.gravity_slider = QSlider(Qt.Orientation.Horizontal)
        self.gravity_slider.setMinimum(0)
        self.gravity_slider.setMaximum(30)
        self.gravity_slider.setSingleStep(1)
        self.gravity_slider.setValue(int(canvas.gravity_multiplier * 10))
        self.gravity_slider.valueChanged.connect(self.change_gravity)
        layout.addWidget(self.gravity_slider)

        # Buttons
        clear_btn = QPushButton("Clear All (C)")
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)

        rain_btn = QPushButton("Toggle Rain (R)")
        rain_btn.clicked.connect(lambda: self.simulate_keypress(Qt.Key.Key_R))
        layout.addWidget(rain_btn)

        theme_btn = QPushButton("Change Theme (T)")
        theme_btn.clicked.connect(lambda: self.simulate_keypress(Qt.Key.Key_T))
        layout.addWidget(theme_btn)

        # Instructions
        instructions = QLabel(
            "<br><b>Shortcuts & Controls:</b><br>"
            "• **Left Click & Drag:** Aim & Launch<br>"
            "• **Right-click:** Launch Burst<br>"
            "• **Space:** Auto-Launch<br>"
            "• **R:** Rain Mode<br>"
            "• **C:** Clear Canvas<br>"
            "• **T:** Change Color Theme"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11px; color: #b3cde0;")
        layout.addWidget(instructions)

        layout.addStretch()
        self.setLayout(layout)

    def toggle_sound(self, state):
        self.canvas.sound_enabled = (state == Qt.CheckState.Checked.value)

    def toggle_stats(self, state):
        self.canvas.show_stats = (state == Qt.CheckState.Checked.value)

    def change_gravity(self, value):
        self.canvas.gravity_multiplier = value / 10.0

    def clear_all(self):
        self.canvas.balls.clear()
        self.canvas.particles.clear()
        self.canvas.update()

    def simulate_keypress(self, key):
        event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.canvas, event)


# ============================================================================
# BREATHING EXERCISE (MANUAL QTimer-driven implementation)
# ============================================================================

class BreathingExercise(QFrame):
    """Guided breathing exercise widget — QTimer-driven animation matching the provided Pygame behavior."""

    # Color tuples (RGB)
    COLOR_WHITE_T = (255, 255, 255)
    COLOR_GREEN_T = (34, 139, 34)
    COLOR_ORANGE_T = (255, 140, 0)
    BACKGROUND_COLOR = (20, 20, 30)

    # Timing (seconds) - matches Pygame values
    INFLATE_TIME = 4.0
    HOLD_1_TIME = 2.0
    DEFLATE_TIME = 6.0
    HOLD_2_TIME = 2.0
    TOTAL_CYCLE_TIME = INFLATE_TIME + HOLD_1_TIME + DEFLATE_TIME + HOLD_2_TIME

    # Radii (pixels)
    MIN_RADIUS = 50
    MAX_RADIUS = 200

    def __init__(self):
        super().__init__()
        self.setObjectName("breathingFrame")

        # animation state
        self.active = False
        self.cycle_count = 0
        self.target_cycles = 5
        self.start_time = None

        # UI layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self.title = QLabel("🧘 Deep Calming Breath (4-2-6-2)")
        self.title.setObjectName("breathingTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        # Graphics view (400x400, center at 200,200)
        self.graphics_view = QGraphicsView()
        self.graphics_view.setObjectName("breathingView")
        self.graphics_view.setFixedSize(400, 400)
        self.graphics_view.setStyleSheet("background: transparent; border: none;")
        self.graphics_scene = QGraphicsScene(QRectF(0, 0, 400, 400))
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setSceneRect(0, 0, 400, 400)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # initial rect centered at (200,200) using MIN_RADIUS
        r = self.MIN_RADIUS
        initial_rect = QRectF(200 - r, 200 - r, r * 2, r * 2)
        self.sphere = QGraphicsEllipseItem(initial_rect)
        self.sphere.setBrush(QBrush(QColor(*self.COLOR_WHITE_T)))
        self.sphere.setPen(QPen(QColor(255, 255, 255, 100), 3))
        self.sphere.setOpacity(0.95)
        self.graphics_scene.addItem(self.sphere)
        self.graphics_view.centerOn(200, 200)
        layout.addWidget(self.graphics_view, alignment=Qt.AlignmentFlag.AlignCenter)

        # instruction and cycles
        self.instruction = QLabel("Click Start to begin")
        self.instruction.setObjectName("breathingInstruction")
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.instruction)

        self.cycle_label = QLabel("Cycle: 0/5")
        self.cycle_label.setObjectName("cycleCountLabel")
        self.cycle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cycle_label)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("breathingButton")
        self.start_btn.clicked.connect(self.toggle_exercise)
        btn_layout.addWidget(self.start_btn)

        self.cycles_spin = QSpinBox()
        self.cycles_spin.setRange(1, 20)
        self.cycles_spin.setValue(5)
        self.cycles_spin.setObjectName("breathingSpinBox")
        btn_layout.addWidget(self.cycles_spin)

        layout.addLayout(btn_layout)

        # Timer for frame updates (~60 FPS)
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(round(1000 / 60))
        self.frame_timer.timeout.connect(self._update_frame)

    # -------------------------
    # Utility: color interpolation
    # -------------------------
    @staticmethod
    def _interp_color_tuple(start, end, progress):
        p = max(0.0, min(1.0, float(progress)))
        r = int(start[0] + (end[0] - start[0]) * p)
        g = int(start[1] + (end[1] - start[1]) * p)
        b = int(start[2] + (end[2] - start[2]) * p)
        return (r, g, b)

    def toggle_exercise(self):
        if not self.active:
            self.start_exercise()
        else:
            self.stop_exercise()

    def start_exercise(self):
        self.active = True
        self.cycle_count = 0
        self.target_cycles = self.cycles_spin.value()
        self.start_btn.setText("Stop")
        self.cycle_label.setText(f"Cycle: 1/{self.target_cycles}")
        self.start_time = time.time()
        self.frame_timer.start()

    def stop_exercise(self):
        self.active = False
        self.frame_timer.stop()
        self.start_btn.setText("Start")
        self.instruction.setText("Exercise stopped. You did great. 🌟")
        # reset sphere to initial small white
        r = self.MIN_RADIUS
        rect = QRectF(200 - r, 200 - r, r * 2, r * 2)
        self.sphere.setRect(rect)
        self.sphere.setBrush(QBrush(QColor(*self.COLOR_WHITE_T)))
        self.sphere.setPen(QPen(QColor(255, 255, 255, 100), 3))

    def _update_frame(self):
        """Called ~60FPS to compute current phase, radius and color then update the QGraphicsEllipseItem"""
        if not self.active or self.start_time is None:
            return

        now = time.time()
        elapsed = now - self.start_time
        cycle_pos = elapsed % self.TOTAL_CYCLE_TIME

        # default values
        new_radius = self.MIN_RADIUS
        color_t = self.COLOR_WHITE_T
        phase_name = "hold2"

        # Phase 1: Inflate (Inhale): 0 -> INFLATE_TIME
        if 0.0 <= cycle_pos < self.INFLATE_TIME:
            phase_name = "inhale"
            t = cycle_pos
            progress = t / self.INFLATE_TIME
            new_radius = self.MIN_RADIUS + (self.MAX_RADIUS - self.MIN_RADIUS) * progress
            color_t = self._interp_color_tuple(self.COLOR_WHITE_T, self.COLOR_GREEN_T, progress)

        # Phase 2: Hold after inhale
        elif self.INFLATE_TIME <= cycle_pos < (self.INFLATE_TIME + self.HOLD_1_TIME):
            phase_name = "hold1"
            new_radius = self.MAX_RADIUS
            color_t = self.COLOR_GREEN_T

        # Phase 3: Deflate (Exhale)
        elif (self.INFLATE_TIME + self.HOLD_1_TIME) <= cycle_pos < (
                self.INFLATE_TIME + self.HOLD_1_TIME + self.DEFLATE_TIME):
            phase_name = "exhale"
            start_deflate = self.INFLATE_TIME + self.HOLD_1_TIME
            t = cycle_pos - start_deflate
            progress = t / self.DEFLATE_TIME
            new_radius = self.MAX_RADIUS - (self.MAX_RADIUS - self.MIN_RADIUS) * progress

            # Color transition: Green -> Orange (first half), Orange -> White (second half)
            if progress < 0.5:
                seg_p = progress * 2.0
                color_t = self._interp_color_tuple(self.COLOR_GREEN_T, self.COLOR_ORANGE_T, seg_p)
            else:
                seg_p = (progress - 0.5) * 2.0
                color_t = self._interp_color_tuple(self.COLOR_ORANGE_T, self.COLOR_WHITE_T, seg_p)

        # Phase 4: Hold after exhale
        else:
            phase_name = "hold2"
            new_radius = self.MIN_RADIUS
            color_t = self.COLOR_WHITE_T

        # Update instruction text quickly according to phase
        if phase_name == "inhale":
            self.instruction.setText("Breathe in deeply... Expand and Fill 🌿")
        elif phase_name == "hold1":
            self.instruction.setText("Hold gently... Stay full 💚")
        elif phase_name == "exhale":
            self.instruction.setText("Breathe out slowly... Release and Let Go 🌊")
        else:
            self.instruction.setText("Hold empty... Rest in stillness 🤍")

        # If we've wrapped to the start (i.e., started a new cycle), update cycle_count
        completed_cycles = int(elapsed // self.TOTAL_CYCLE_TIME)
        if completed_cycles + 1 > self.cycle_count:
            self.cycle_count = completed_cycles + 1
            if self.cycle_count > self.target_cycles:
                self.stop_exercise()
                return
            self.cycle_label.setText(f"Cycle: {self.cycle_count}/{self.target_cycles}")

        # Apply visual updates to the sphere
        rect = QRectF(200 - new_radius, 200 - new_radius, new_radius * 2, new_radius * 2)
        self.sphere.setRect(rect)

        qcol = QColor(color_t[0], color_t[1], color_t[2])
        self.sphere.setBrush(QBrush(qcol))
        self.sphere.setPen(QPen(QColor(255, 255, 255, 120), 3))


# ============================================================================
# NEW: CALMING GAMES MODULE (SENSORY REWORK) - UPDATED FOR ZEN FLOW
# ============================================================================

class CalmingGamesWidget(QTabWidget):
    """Container for simple, mindful calming games."""

    def __init__(self):
        super().__init__()
        self.setObjectName("calmingGames")

        # --- NEW INTEGRATION: Zen Flow Launcher ---
        self.zen_flow_canvas = ZenFlowCanvas()
        self.zen_flow_settings = SettingsPanel(self.zen_flow_canvas)

        zen_flow_container = QWidget()
        zen_flow_layout = QHBoxLayout(zen_flow_container)
        zen_flow_layout.setContentsMargins(10, 10, 10, 10)

        zen_flow_layout.addWidget(self.zen_flow_canvas, 3)
        self.zen_flow_settings.setMaximumWidth(220)
        self.zen_flow_settings.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        zen_flow_layout.addWidget(self.zen_flow_settings, 1)

        self.addTab(zen_flow_container, "✨ Zen Flow Launcher (Physics)")
        # --- END NEW INTEGRATION ---

        self.addTab(ForestSoundscapeMixer(), "🌿 Soundscape Mixer")


# ============================================================================
# FOREST SOUNDSCAPE MIXER
# ============================================================================

class ForestSoundscapeMixer(QWidget):
    """Game 2: Interactive mixer for relaxing ambient sounds."""

    def __init__(self):
        super().__init__()
        self.sound_levels = {
            'Rain': 0,
            'Stream': 0,
            'Wind': 0,
            'Birds': 0
        }
        self.instructions = QLabel("")
        self.channels = {}

        if PYGAME_AVAILABLE:
            self._load_sounds()

        self._init_ui()
        self._check_audio_status()

    def _load_sounds(self):
        """Loads sound files into Pygame Mixer channels."""
        file_map = {
            'Rain': 'rain.wav',
            'Stream': 'stream.wav',
            'Wind': 'wind.wav',
            'Birds': 'birds.wav'
        }

        for name, filename in file_map.items():
            try:
                sound = pygame.mixer.Sound(filename)
                channel = pygame.mixer.find_channel(True)
                channel.play(sound, loops=-1)
                channel.set_volume(0.0)

                self.channels[name] = {'sound': sound, 'channel': channel}
            except pygame.error as e:
                pass

    def _check_audio_status(self):
        if PYGAME_AVAILABLE and all(name in self.channels for name in self.sound_levels):
            self.instructions.setText(
                "Adjust the sliders to create your perfect calming forest mix. (Audio **ACTIVE**)")
        else:
            self.instructions.setText(
                "Adjust the sliders to create your perfect calming forest mix. (Audio **DISABLED** - Pygame or required sound files missing.)")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = QLabel("🌿 Forest Soundscape Mixer")
        self.title.setObjectName("gameTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.instructions.setObjectName("gameInstructions")
        layout.addWidget(self.instructions)

        grid = QGridLayout()
        self.mix_display = QLabel("Current Mix: Silent")
        self.mix_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mix_display)

        for i, (name, _) in enumerate(self.sound_levels.items()):
            icon = self._get_sound_icon(name)

            label = QLabel(f"{icon} {name}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, i, 1, 1)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(0, 100)
            slider.setValue(0)
            slider.name = name
            slider.valueChanged.connect(self._update_mix)
            grid.addWidget(slider, 1, i, 1, 1)

            level_label = QLabel("0%")
            level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            level_label.setObjectName(name + "Level")

            grid.addWidget(level_label, 2, i, 1, 1)

        layout.addLayout(grid)
        layout.addSpacing(20)

        self.stop_button = QPushButton("Stop All Sounds")
        self.stop_button.setObjectName("stopAllSoundsButton")
        self.stop_button.clicked.connect(self._stop_all)
        layout.addWidget(self.stop_button)

    def _get_sound_icon(self, name):
        icons = {
            'Rain': '🌧️', 'Stream': '💧', 'Wind': '💨', 'Birds': '🐦'
        }
        return icons.get(name, '')

    def _update_mix(self, value):
        sender = self.sender()
        name = sender.name
        self.sound_levels[name] = value

        for child in self.findChildren(QLabel):
            if child.objectName() == name + "Level":
                child.setText(f"{value}%")

        self._update_mix_display()
        self._apply_audio_mix(value)

    def _update_mix_display(self):
        active_mix = [f"{name}: {level}%" for name, level in self.sound_levels.items() if level > 0]
        if active_mix:
            self.mix_display.setText(" | ".join(active_mix))
        else:
            self.mix_display.setText("Current Mix: Silent")

    def _apply_audio_mix(self, volume):
        """Controls sound volume based on slider values using Pygame."""
        if not PYGAME_AVAILABLE:
            return

        for name, level in self.sound_levels.items():
            if name in self.channels:
                volume = level / 100.0
                self.channels[name]['channel'].set_volume(volume)

    def _stop_all(self):
        for child in self.findChildren(QSlider):
            child.setValue(0)
        self._update_mix_display()

        if PYGAME_AVAILABLE:
            for item in self.channels.values():
                item['channel'].set_volume(0.0)

    def closeEvent(self, event):
        if PYGAME_AVAILABLE:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        super().closeEvent(event)


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """SQLite database for session storage and analytics"""

    def __init__(self, db_path="emocare_sessions.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration INTEGER,
                dominant_emotion TEXT,
                average_mood_score REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TIMESTAMP,
                emotion TEXT,
                confidence REAL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TIMESTAMP,
                role TEXT,
                message TEXT,
                emotion TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TIMESTAMP,
                alert_type TEXT,
                description TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        conn.commit()
        conn.close()

    def create_session(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO sessions (start_time) VALUES (?)
        ''', (timestamp,))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    def end_session(self, session_id, dominant_emotion, avg_mood):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        end_time = datetime.now().isoformat()

        cursor.execute('SELECT start_time FROM sessions WHERE id = ?', (session_id,))
        start_time_str = cursor.fetchone()[0]

        duration = 0
        try:
            start_dt = datetime.fromisoformat(start_time_str)
            end_dt = datetime.fromisoformat(end_time)
            duration = (end_dt - start_dt).seconds
        except ValueError:
            pass

        cursor.execute('''
            UPDATE sessions 
            SET end_time = ?, dominant_emotion = ?, average_mood_score = ?, duration = ?
            WHERE id = ?
        ''', (end_time, dominant_emotion, avg_mood, duration, session_id))

        conn.commit()
        conn.close()

    def log_emotion(self, session_id, emotion, confidence):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO emotions (session_id, timestamp, emotion, confidence)
            VALUES (?, ?, ?, ?)
        ''', (session_id, datetime.now().isoformat(), emotion, confidence))
        conn.commit()
        conn.close()

    def log_message(self, session_id, role, message, emotion):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (session_id, timestamp, role, message, emotion)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, datetime.now().isoformat(), role, message, emotion))
        conn.commit()
        conn.close()

    def log_alert(self, session_id, alert_type, description):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (session_id, timestamp, alert_type, description)
            VALUES (?, ?, ?, ?)
        ''', (session_id, datetime.now().isoformat(), alert_type, description))
        conn.commit()
        conn.close()

    def get_session_analytics(self, session_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT emotion, confidence, timestamp FROM emotions 
            WHERE session_id = ? ORDER BY timestamp
        ''', (session_id,))
        emotions = cursor.fetchall()

        cursor.execute('''
            SELECT role, message, timestamp FROM messages 
            WHERE session_id = ? ORDER BY timestamp
        ''', (session_id,))
        messages = cursor.fetchall()

        cursor.execute('''
            SELECT alert_type, description, timestamp FROM alerts 
            WHERE session_id = ? ORDER BY timestamp
        ''', (session_id,))
        alerts = cursor.fetchall()

        conn.close()

        return {
            'emotions': emotions,
            'messages': messages,
            'alerts': alerts
        }


# ============================================================================
# ANALYTICS DASHBOARD
# ============================================================================

class AnalyticsDashboard(QWidget):
    """Session analytics and visualization"""

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("📊 Session Analytics")
        title.setObjectName("dashboardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        stats_frame = QFrame()
        stats_frame.setObjectName("statsFrame")
        stats_layout = QVBoxLayout(stats_frame)

        self.session_time = QLabel("Session Duration: 0 min")
        self.session_time.setObjectName("statLabel")
        stats_layout.addWidget(self.session_time)

        self.dominant_emotion = QLabel("Dominant Emotion: --")
        self.dominant_emotion.setObjectName("statLabel")
        stats_layout.addWidget(self.dominant_emotion)

        self.mood_score = QLabel("Average Mood: --")
        self.mood_score.setObjectName("statLabel")
        stats_layout.addWidget(self.mood_score)

        self.total_messages = QLabel("Total Messages: 0")
        self.total_messages.setObjectName("statLabel")
        stats_layout.addWidget(self.total_messages)

        self.alert_count = QLabel("Alerts Triggered: 0")
        self.alert_count.setObjectName("statLabel")
        stats_layout.addWidget(self.alert_count)

        layout.addWidget(stats_frame)

        if PLOT_AVAILABLE:
            self.figure = Figure(figsize=(8, 4))
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setStyleSheet("background-color: transparent;")
            layout.addWidget(self.canvas)
        else:
            chart_placeholder = QLabel("📈 Install matplotlib and PyQt6-Charts for emotion timeline")
            chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(chart_placeholder)

        export_layout = QHBoxLayout()

        export_pdf_btn = QPushButton("📄 Export PDF Report")
        export_pdf_btn.setObjectName("exportButton")
        export_pdf_btn.clicked.connect(self.export_pdf_report)
        export_layout.addWidget(export_pdf_btn)

        export_csv_btn = QPushButton("📊 Export CSV Data")
        export_csv_btn.setObjectName("exportButton")
        export_csv_btn.clicked.connect(self.export_csv_data)
        export_layout.addWidget(export_csv_btn)

        layout.addLayout(export_layout)

    def update_stats(self, session_id, start_time, emotions, messages, alerts):
        duration = (datetime.now() - start_time).seconds // 60
        self.session_time.setText(f"Session Duration: {duration} min")

        if emotions:
            emotion_counts = Counter([e[0] for e in emotions])
            dominant = emotion_counts.most_common(1)[0][0]
            self.dominant_emotion.setText(f"Dominant Emotion: {dominant.capitalize()}")

        emotion_scores = {
            'happy': 95, 'surprise': 65, 'neutral': 50,
            'disgust': 25, 'angry': 30, 'fear': 15, 'sad': 5
        }
        if emotions:
            scores = [emotion_scores.get(e[0], 50) for e in emotions]
            avg_score = sum(scores) / len(scores) if scores else 50
            self.mood_score.setText(f"Average Mood: {avg_score:.1f}/100")

        self.total_messages.setText(f"Total Messages: {len(messages)}")
        self.alert_count.setText(f"Alerts Triggered: {len(alerts)}")

        if PLOT_AVAILABLE:
            self.update_emotion_chart(emotions)

    def update_emotion_chart(self, emotions):
        if not emotions:
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        emotion_map = {'happy': 5.5, 'surprise': 4.5, 'neutral': 3.5,
                       'disgust': 2.5, 'angry': 1.5, 'fear': 1.5, 'sad': 0.5}
        timestamps = []
        values = []

        for emotion, confidence, timestamp in emotions:
            try:
                ts = datetime.fromisoformat(timestamp)
                timestamps.append(ts)
                values.append(emotion_map.get(emotion, 3.5))
            except:
                pass

        if timestamps:
            ax.plot(timestamps, values, linewidth=2, color='#7F5EFA', marker='o',
                    markersize=3)
            ax.fill_between(timestamps, values, alpha=0.3, color='#7F5EFA')
            ax.set_xlabel('Time', fontsize=10)
            ax.set_ylabel('Emotion Valence', fontsize=10)
            ax.set_title('Emotion Timeline', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)

            ax.set_yticks([0.5, 1.5, 2.5, 3.5, 4.5, 5.5])
            ax.set_yticklabels(['Sad', 'Fear/Angry', 'Disgust', 'Neutral', 'Surprise', 'Happy'])
            ax.set_ylim(0, 6)

            self.figure.tight_layout()
            self.canvas.draw()

    def export_pdf_report(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "emocare_report.txt", "Text Files (*.txt)"
        )

        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("EMOCARE SESSION REPORT\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"{self.session_time.text()}\n")
                f.write(f"{self.dominant_emotion.text()}\n")
                f.write(f"{self.mood_score.text()}\n")
                f.write(f"{self.total_messages.text()}\n")
                f.write(f"{self.alert_count.text()}\n\n")
                f.write("=" * 60 + "\n")

    def export_csv_data(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV Data", "emocare_data.csv", "CSV Files (*.csv)"
        )

        if filename:
            import csv
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(id) FROM sessions')
            current_session_id = cursor.fetchone()[0]
            conn.close()

            if not current_session_id:
                return

            analytics = self.db.get_session_analytics(current_session_id)
            emotions_data = analytics['emotions']

            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Emotion', 'Confidence'])
                for emotion, confidence, timestamp in emotions_data:
                    writer.writerow([timestamp, emotion, confidence])


# ============================================================================
# VOICE ASSISTANT
# ============================================================================

class VoiceAssistant:
    """Text-to-Speech and Speech-to-Text handler"""

    def __init__(self):
        self.tts_enabled = False
        self.stt_enabled = False

        if VOICE_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 0.9)

                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break

                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                self.tts_enabled = True
                self.stt_enabled = True
            except Exception as e:
                pass

    def speak(self, text):
        """Convert text to speech"""
        if self.tts_enabled:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                pass

    def listen(self):
        """Convert speech to text"""
        if not self.stt_enabled:
            return None

        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)

            text = self.recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as e:
            return None


# ============================================================================
# ENHANCED EMOTION DETECTOR
# ============================================================================

class EmotionDetector:
    """Enhanced emotion detection with stabilization via filtering and smoothing."""

    def __init__(self):
        self.detector = FER(mtcnn=True) if FER_AVAILABLE else None
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )

        self.current_emotion = "neutral"
        self.emotion_history = deque(maxlen=200)
        self.face_history = deque(maxlen=50)
        self.eye_contact_history = deque(maxlen=30)
        self.frame_count = 0

        self.recent_confident_emotions = deque(maxlen=10)

        self.last_emotion_change = time.time()
        self.crying_frames = 0
        self.no_eye_contact_frames = 0

    def detect_emotions(self, frame):
        """Detect emotions from multiple faces, applying confidence filter."""
        faces_data = []

        if self.detector and FER_AVAILABLE:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.detector.detect_emotions(rgb_frame)

                for result in results:
                    emotions = result['emotions']
                    emotion = max(emotions, key=emotions.get)
                    confidence = emotions[emotion]
                    box = result['box']

                    if emotion != 'neutral' and confidence < CONFIDENCE_THRESHOLD:
                        emotion = 'neutral'
                        confidence = 0.5

                    if confidence > 0.3:
                        faces_data.append({
                            'emotion': emotion,
                            'confidence': confidence,
                            'box': box
                        })
                        if emotion != 'neutral':
                            self.recent_confident_emotions.append(emotion)

            except Exception as e:
                pass

        if not faces_data:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # FIX: Removed erroneous cv2.findNonContourRects(gray) call

            faces = self.face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(50, 50))

            for (x, y, w, h) in faces:
                self.frame_count += 1
                emotions_list = ['neutral', 'neutral', 'happy', 'sad', 'neutral']
                emotion = emotions_list[int(time.time() * 10) % len(emotions_list)]

                faces_data.append({
                    'emotion': emotion,
                    'confidence': 0.75,
                    'box': [x, y, w, h]
                })

        if faces_data:
            primary_emotion = faces_data[0]['emotion']
            self.emotion_history.append(primary_emotion)
            self.face_history.append(len(faces_data))

            if primary_emotion != self.current_emotion:
                self.last_emotion_change = time.time()
                self.current_emotion = primary_emotion

        return faces_data

    def detect_eye_contact(self, frame, face_box):
        """Detect eye contact/avoidance"""
        x, y, w, h = face_box
        if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return False

        roi_gray = cv2.cvtColor(frame[y:y + h // 2, x:x + w], cv2.COLOR_BGR2GRAY)
        eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 5)

        has_eye_contact = len(eyes) >= 2
        self.eye_contact_history.append(has_eye_contact)

        if not has_eye_contact:
            self.no_eye_contact_frames += 1
        else:
            self.no_eye_contact_frames = 0

        return has_eye_contact

    def detect_crying(self, frame, face_box):
        """Detect potential crying (simplified)"""
        x, y, w, h = face_box
        if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return False

        roi = frame[y:y + h, x:x + w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_bright = np.array([0, 0, 200])
        upper_bright = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower_bright, upper_bright)

        bright_pixels = np.sum(mask > 0)
        total_pixels = roi.shape[0] * roi.shape[1]

        if bright_pixels / total_pixels > 0.05:
            self.crying_frames += 1
        else:
            self.crying_frames = max(0, self.crying_frames - 1)

        return self.crying_frames > 10

    def detect_unusual_behavior(self):
        """Enhanced behavioral pattern detection"""
        alerts = []
        if len(self.emotion_history) < 30: return alerts
        recent = list(self.emotion_history)[-50:]

        # Prolonged Sadness
        sad_count = sum(1 for e in recent if e == 'sad')
        if sad_count / len(recent) > 0.7:
            alerts.append({'type': 'prolonged_sadness', 'message': '⚠️ Prolonged sadness detected', 'severity': 'high'})

        # High Stress/Fear
        fear_count = sum(1 for e in recent if e == 'fear')
        if fear_count / len(recent) > 0.6:
            alerts.append({'type': 'high_stress', 'message': '⚠️ High stress levels detected', 'severity': 'high'})

        # Mood Swings (high volatility in last 15 frames)
        if len(set(list(self.emotion_history)[-15:])) >= 5:
            alerts.append({'type': 'mood_swings', 'message': '⚠️ Rapid mood fluctuation', 'severity': 'medium'})

        # Eye Avoidance
        if len(self.eye_contact_history) >= 30:
            eye_contact_ratio = sum(self.eye_contact_history) / len(self.eye_contact_history)
            if eye_contact_ratio < 0.3:
                alerts.append(
                    {'type': 'eye_avoidance', 'message': '⚠️ Prolonged eye contact avoidance', 'severity': 'medium'})

        # Crying
        if self.crying_frames > 15:
            alerts.append({'type': 'crying', 'message': '⚠️ Signs of crying detected', 'severity': 'high'})

        # Emotional Flatness
        if len(recent) >= 40:
            neutral_count = sum(1 for e in recent if e == 'neutral')
            if neutral_count / len(recent) > 0.9:
                alerts.append(
                    {'type': 'emotional_flat', 'message': '⚠️ Emotional flatness detected', 'severity': 'medium'})

        return alerts

    def get_mood_score(self):
        """Calculate mood score (0-100) using a larger rolling average for strong stabilization."""
        if len(self.emotion_history) < 5: return 50
        recent = list(self.emotion_history)[-SMOOTHING_WINDOW_SIZE:]
        emotion_scores = {
            'happy': 95, 'surprise': 65, 'neutral': 50,
            'disgust': 25, 'angry': 30, 'fear': 15, 'sad': 5
        }
        scores = [emotion_scores.get(e, 50) for e in recent]
        if len(scores) == 0: return 50
        return sum(scores) / len(scores)


# ============================================================================
# LLAMA 3.2 PSYCHOLOGIST
# ============================================================================

class Llama32Psychologist:
    """AI Psychologist powered by Llama 3.2"""

    def __init__(self):
        self.conversation_history = []
        self.api_endpoint = "http://localhost:11434/api/generate"
        self.model = "llama3.2"
        self.session_context = {
            'start_time': datetime.now(),
            'emotions_seen': set(),
            'concerns': [],
            'mood_trend': 'stable'
        }

    def generate_response(self, user_message, current_emotion, alerts, mood_score, suggest_game):

        prompt = self._build_therapeutic_prompt(
            user_message, current_emotion, alerts, mood_score, suggest_game
        )

        self.conversation_history.append({
            'role': 'user',
            'message': user_message,
            'emotion': current_emotion,
            'timestamp': datetime.now().strftime("%H:%M")
        })

        response = self._call_llama(prompt)

        if not response:
            response = self._fallback_response(user_message, current_emotion, alerts, suggest_game)

        self.conversation_history.append({
            'role': 'assistant',
            'message': response,
            'timestamp': datetime.now().strftime("%H:%M")
        })

        self.session_context['emotions_seen'].add(current_emotion)

        return response

    def _safety_guardrail_response(self):
        """Provides a compassionate, yet non-negotiable safety message."""
        return """
I hear the **deep pain** in your words, and I want you to know you are **not alone** in this moment. 
I am an AI, and I cannot provide the immediate clinical support you need right now, but **there are compassionate, trained people who can help immediately.**

**Please contact the Suicide & Crisis Lifeline right now by calling or texting 988 (US/Canada).** They are available 24/7 and trained to listen without judgment. You deserve to be safe. Is there anything else I can help you find, like breathing exercises, while you connect with them?
        """

    def _build_therapeutic_prompt(self, message, emotion, alerts, mood_score, suggest_game):
        alert_context = ""
        if alerts:
            alert_types = [a['type'] for a in alerts]
            alert_context = f"\n\nIMPORTANT ALERTS: {', '.join(alert_types)}. User may be showing signs of distress or avoidance."

        mood_context = ""
        if mood_score < 30:
            mood_context = "\n\nUser's mood score is VERY LOW (critical distress). Respond with extra caution and suggest grounding/breathing."
        elif mood_score < 50:
            mood_context = "\n\nUser's mood score is below average (mild distress). Offer deep empathy."

        # --- Game Suggestion Integration (Updated Game Names) ---
        game_suggestion = ""
        if suggest_game:
            game_suggestion = (
                "\n\n**Actionable Suggestion:** The user's mood is low/stressed. "
                "Suggest they take a 3-minute break and try one of the **Calming Games** in the Games tab. "
                "Recommend the 'Zen Flow Launcher (Physics)' for active sensory engagement or the 'Soundscape Mixer' for auditory comfort."
            )

        strategy_guidance = ""
        if emotion == 'sad' or mood_score < 30:
            strategy_guidance = "Your primary goal is to **validate the user's feelings**, offer deep empathy, and gently guide them toward emotional regulation (e.g., grounding, breathing, self-compassion). Do not try to 'fix' the problem. Ask: 'What does this sadness feel like in your body?'"
        elif emotion == 'fear':
            strategy_guidance = "Your primary goal is **de-escalation and safety**. Use short, calm sentences. Ask them to name three things they see, or suggest a grounding technique immediately. Focus on the present moment. Ask: 'What is one small thing you can control right now?'"
        elif emotion == 'angry':
            strategy_guidance = "Your primary goal is to **explore the root cause** (usually hurt or injustice). Validate the feeling of anger but gently steer toward understanding the underlying emotion. Use reflective listening. Ask: 'What is the feeling underneath this anger?'"
        elif emotion == 'surprise':
            strategy_guidance = "Your primary goal is to **assess valence** (is it good or bad surprise?). Show genuine curiosity and encourage them to share the news. Ask: 'That sounds like something significant! Is this a positive or negative surprise?'"
        elif emotion == 'happy':
            strategy_guidance = "Your primary goal is to **savor the positive experience** and explore its origins to reinforce positive coping mechanisms. Use open-ended questions about the joy. Ask: 'What is the best part of this feeling, and how can you hold onto it a little longer?'"
        else:
            strategy_guidance = "Your primary goal is to **gently invite deeper conversation**. Acknowledge the calm, but check if they are holding back. Ask: 'While you seem neutral, I'm wondering if anything is beneath the surface today?'"

        prompt = f"""You are an empathetic, professional AI psychologist named EmoCare, utilizing the Llama 3.2 model. Your role is to provide supportive, non-judgemental mental health guidance based on the user's input AND their detected emotional state.

CURRENT CONTEXT:
- User's detected emotion: {emotion}
- Mood score: {mood_score:.1f}/100
- Session duration: {(datetime.now() - self.session_context['start_time']).seconds // 60} minutes{alert_context}{mood_context}{game_suggestion}

**THERAPEUTIC STRATEGY:**
{strategy_guidance}

USER MESSAGE: "{message}"

GUIDELINES:
1. Respond with warmth, empathy, and validation.
2. If the **Actionable Suggestion** is present, gently weave the game suggestion into your reply.
3. Directly reference the **detected emotion** (e.g., "I see you're feeling {emotion}...") to show awareness.
4. Apply the specific therapeutic strategy outlined above.
5. **Keep response brief, under 70 words.**
6. Be conversational, not clinical.

Respond as a caring therapist would:"""

        return prompt

    def _call_llama(self, prompt):
        """Call Llama 3.2 via Ollama API"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_ctx": 4096,
                    "num_predict": 100
                }
            }

            response = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                return None

        except requests.exceptions.ConnectionError:
            return None
        except Exception as e:
            return None

    def _fallback_response(self, message, emotion, alerts, suggest_game):
        """Fallback therapeutic responses when API unavailable"""

        message_lower = message.lower()

        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return f"Hello! I'm EmoCare. The AI is offline, but I can still support you. I see you're feeling {emotion}. What's on your mind today?"

        if any(a['severity'] == 'high' for a in alerts) or emotion in ['sad', 'fear']:
            if suggest_game:
                return "I recognize this is a difficult moment. I see signs of distress. Your feelings are real, and you are not alone. Let's focus on one small step forward. You could try the **Zen Flow Launcher (Physics)** in the Games tab for a quick break and distraction."
            return "I recognize this is a difficult moment. I see signs of distress. Your feelings are real, and you are not alone. Lets focus on one small step forward. What do you feel comfortable talking about right now?"

        if emotion == "sad":
            if suggest_game:
                return "It sounds like a heavy weight you're carrying. I see you're feeling sad. It's okay to slow down. Would you like to try the **Soundscape Mixer** in the Games tab for a few minutes of calming auditory control?"
            return "It sounds like a heavy weight you're carrying. I see you're feeling sad, and that is a valid emotion. Please know that it's okay to slow down. What is one small act of self-kindness you can offer yourself right now?"

        elif emotion == "angry":
            if suggest_game:
                return "I can sense your frustration. Let's explore that together. In the meantime, the **Zen Flow Launcher (Physics)** in the Games tab might help channel some of that energy into focused activity."
            return "I can sense your frustration. Anger often comes from feeling hurt or unheard. What triggered these feelings? Let's explore that together."

        elif emotion == "happy":
            return "It's wonderful to see you feeling positive! These moments are precious. Tell me more about what's bringing you joy and how we can keep this feeling going."

        elif emotion == "surprise":
            return "I see a look of surprise! Is this a good surprise or perhaps something that has you feeling uncertain? I'm here if you want to share what happened."

        else:
            return "I'm listening with my full attention. Thank you for trusting me with your thoughts. How are you really feeling beneath the surface?"

    def get_greeting(self):
        """Generate warm greeting"""
        return "Welcome to EmoCare. I'm your AI psychologist powered by Llama 3.2. This is a safe, confidential space. How are you feeling today?"


# ============================================================================
# VIDEO CAPTURE THREAD
# ============================================================================

class VideoThread(QThread):
    """Enhanced video thread with detection rate limiting."""
    change_pixmap_signal = pyqtSignal(np.ndarray)
    emotion_signal = pyqtSignal(str, float, list)

    def __init__(self):
        super().__init__()
        self.running = True
        self.detector = EmotionDetector()

        self.frame_counter = 0
        self.detection_interval = DETECTION_INTERVAL

    def get_emotion_color(self, emotion):
        """Get color for emotion (Using Bright Primary Colors for visibility over video feed)"""
        colors = {
            'happy': (119, 237, 107), 'sad': (255, 100, 100), 'angry': (255, 165, 0),
            'fear': (127, 255, 212), 'surprise': (255, 255, 102), 'disgust': (216, 191, 216),
            'neutral': (150, 150, 150), 'contempt': (255, 192, 203)
        }
        return colors.get(emotion, (255, 255, 255))

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self.running:
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)

                faces_data = []

                if self.frame_counter % self.detection_interval == 0:
                    faces_data = self.detector.detect_emotions(frame)

                self.frame_counter += 1

                for face_data in faces_data:
                    x, y, w, h = face_data['box']
                    emotion = face_data['emotion']
                    confidence = face_data['confidence']

                    x, y, w, h = int(x), int(y), int(w), int(h)

                    color = self.get_emotion_color(emotion)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

                    label = f"{emotion.capitalize()} ({confidence:.2f})"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                    cv2.rectangle(frame, (x, y - 30), (x + label_size[0] + 10, y), color, -1)
                    cv2.putText(frame, label, (x + 5, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                    if face_data == faces_data[0]:
                        has_eyes = self.detector.detect_eye_contact(frame, face_data['box'])
                        if not has_eyes and self.detector.no_eye_contact_frames > 5:
                            cv2.putText(frame, "No Eye Contact", (x, y + h + 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                self.change_pixmap_signal.emit(frame)

                if faces_data:
                    primary = faces_data[0]
                    self.emotion_signal.emit(
                        primary['emotion'],
                        primary['confidence'],
                        faces_data
                    )

            time.sleep(0.01)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()


# ============================================================================
# MAIN APPLICATION CLASSES
# ============================================================================

class EmoCareApp(QMainWindow):
    """The main window and GUI application logic."""

    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.emotion_detector = EmotionDetector()
        self.ai_psychologist = Llama32Psychologist()
        self.db_manager = DatabaseManager()
        self.voice_assistant = VoiceAssistant() if VOICE_AVAILABLE else None

        self.current_emotion = "neutral"
        self.session_id = self.db_manager.create_session()
        self.session_start = datetime.now()

        self.tts_enabled = False
        self.stt_enabled = False

        self.custom_app_name = "VenomMind Lab"

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Made by Krish 🔧")
        self.setGeometry(50, 50, 1600, 900)

        preferred_font_name = "Segoe UI"
        app_font = QFont(preferred_font_name, 10)

        if preferred_font_name not in app_font.family():
            app_font = QFont("Arial", 10)

        self.setFont(app_font)

        self.setStyleSheet(self.get_light_stylesheet())

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.header_widget = QLabel(self.custom_app_name)
        self.header_widget.setObjectName("mainHeaderTitle")
        self.header_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_widget.setFixedHeight(50)
        main_layout.addWidget(self.header_widget)

        self.theme_btn = QPushButton("🌚", self)
        self.theme_btn.setObjectName("themeButtonCircle")
        self.theme_btn.setFixedSize(QSize(40, 40))
        self.theme_btn.clicked.connect(self.toggle_theme)

        self.theme_btn.move(self.width() - 60, 5)

        QTimer.singleShot(100, self.reposition_global_elements)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")

        therapy_tab = QWidget()
        therapy_layout = QHBoxLayout(therapy_tab)
        therapy_layout.setSpacing(0)
        therapy_layout.setContentsMargins(0, 0, 0, 0)

        self.create_left_panel(therapy_layout)
        self.create_right_panel(therapy_layout)

        self.tabs.addTab(therapy_tab, "💬 Therapy Session")

        self.analytics_tab = AnalyticsDashboard(self.db_manager)
        self.tabs.addTab(self.analytics_tab, "📊 Analytics")

        self.breathing_tab = BreathingExercise()
        self.tabs.addTab(self.breathing_tab, "🧘 Breathing Exercise")

        self.games_tab = CalmingGamesWidget()
        self.tabs.addTab(self.games_tab, "🎮 Calming Games")

        main_layout.addWidget(self.tabs)

        self.video_thread = VideoThread()
        self.video_thread.change_pixmap_signal.connect(self.update_image)
        self.video_thread.emotion_signal.connect(self.update_emotion)
        self.video_thread.start()

        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(5000)

        self.analytics_timer = QTimer()
        self.analytics_timer.timeout.connect(self.update_analytics)
        self.analytics_timer.start(10000)

        QTimer.singleShot(1000, self.send_greeting)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_global_elements()

    def reposition_global_elements(self):
        button_size = self.theme_btn.width()
        right_margin = 20
        top_margin = 5

        new_x = self.width() - button_size - right_margin
        new_y = top_margin

        self.theme_btn.move(new_x, new_y)

    def create_left_panel(self, parent_layout):
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setMaximumWidth(550)
        left_panel.setMinimumWidth(500)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)

        title = QLabel("🎥 Live Emotion Analysis")
        title.setObjectName("panelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        camera_container = QFrame()
        camera_container.setObjectName("cameraContainer")
        camera_container.setFixedHeight(360)
        camera_layout = QVBoxLayout(camera_container)
        camera_layout.setContentsMargins(5, 5, 5, 5)

        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setScaledContents(False)
        camera_layout.addWidget(self.camera_label)

        left_layout.addWidget(camera_container)

        self.face_count_label = QLabel("👤 Faces Detected: 0")
        self.face_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_count_label.setObjectName("faceCountLabel")
        left_layout.addWidget(self.face_count_label)

        emotion_frame = QFrame()
        emotion_frame.setObjectName("emotionFrame")
        emotion_layout = QVBoxLayout(emotion_frame)

        emotion_title = QLabel("Current Emotion")
        emotion_title.setObjectName("sectionTitle")
        emotion_layout.addWidget(emotion_title)

        self.emotion_display = QLabel("😐 Neutral")
        self.emotion_display.setObjectName("emotionDisplay")
        self.emotion_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emotion_layout.addWidget(self.emotion_display)

        self.confidence_label = QLabel("Confidence: --")
        self.confidence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emotion_layout.addWidget(self.confidence_label)

        self.mood_score_bar = QProgressBar()
        self.mood_score_bar.setObjectName("moodScoreBar")
        self.mood_score_bar.setRange(0, 100)
        self.mood_score_bar.setValue(50)
        emotion_layout.addWidget(self.mood_score_bar)

        left_layout.addWidget(emotion_frame)

        alerts_frame = QFrame()
        alerts_frame.setObjectName("alertsFrame")
        alerts_layout = QVBoxLayout(alerts_frame)

        alerts_title = QLabel("⚠️ Behavioral Alerts")
        alerts_title.setObjectName("sectionTitle")
        alerts_layout.addWidget(alerts_title)

        self.alerts_scroll = QScrollArea()
        self.alerts_scroll.setWidgetResizable(True)
        self.alerts_scroll.setMaximumHeight(150)
        self.alerts_scroll.setObjectName("alertsScroll")

        self.alerts_widget = QWidget()
        self.alerts_layout = QVBoxLayout(self.alerts_widget)
        self.alerts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.alerts_scroll.setWidget(self.alerts_widget)
        alerts_layout.addWidget(self.alerts_scroll)

        left_layout.addWidget(alerts_frame)

        # Quick Links
        quick_links_layout = QHBoxLayout()

        breath_btn = QPushButton("🧘 Breath")
        breath_btn.setObjectName("quickLinkButton")
        breath_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        quick_links_layout.addWidget(breath_btn)

        games_btn = QPushButton("🎮 Games")
        games_btn.setObjectName("quickLinkButton")
        games_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        quick_links_layout.addWidget(games_btn)

        left_layout.addLayout(quick_links_layout)

        parent_layout.addWidget(left_panel)

    def create_right_panel(self, parent_layout):
        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(10)

        top_bar = QHBoxLayout()

        chat_title = QLabel("🤖 AI Psychologist (Llama 3.2)")
        chat_title.setObjectName("chatTitle")
        top_bar.addWidget(chat_title)

        top_bar.addStretch()

        if VOICE_AVAILABLE:
            self.tts_checkbox = QCheckBox("🔊 TTS")
            self.tts_checkbox.setObjectName("voiceCheckbox")
            self.tts_checkbox.toggled.connect(self.toggle_tts)
            top_bar.addWidget(self.tts_checkbox)

            self.stt_btn = QPushButton("🎤 Voice Input")
            self.stt_btn.setObjectName("voiceButton")
            self.stt_btn.clicked.connect(self.voice_input)
            top_bar.addWidget(self.stt_btn)

        export_btn = QPushButton("💾 Export")
        export_btn.setObjectName("exportButton")
        export_btn.clicked.connect(self.export_chat)
        top_bar.addWidget(export_btn)

        right_layout.addSpacing(40)
        right_layout.addLayout(top_bar)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setObjectName("chatScroll")

        self.chat_widget = QWidget()
        self.chat_widget.setObjectName("chatWidget")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(10)

        self.chat_scroll.setWidget(self.chat_widget)
        right_layout.addWidget(self.chat_scroll)

        self.typing_indicator = QLabel("AI is typing...")
        self.typing_indicator.setObjectName("typingIndicator")
        self.typing_indicator.hide()
        right_layout.addWidget(self.typing_indicator)

        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)

        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Type your message or use voice input...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)

        send_btn = QPushButton("Send ➤")
        send_btn.setObjectName("sendButton")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)

        right_layout.addWidget(input_frame)

        parent_layout.addWidget(right_panel, stretch=1)

    def update_image(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            480, 340, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.camera_label.setPixmap(scaled_pixmap)

    def update_emotion(self, emotion, confidence, faces_data):
        self.current_emotion = emotion

        self.face_count_label.setText(f"👤 Faces Detected: {len(faces_data)}")

        emoji_map = {
            'happy': '😊', 'sad': '😢', 'angry': '😠',
            'fear': '😨', 'surprise': '😲', 'disgust': '🤢', 'neutral': '😐', 'contempt': '😒'
        }

        emoji = emoji_map.get(emotion, '😐')
        self.emotion_display.setText(f"{emoji} {emotion.capitalize()}")
        self.confidence_label.setText(f"Confidence: {confidence:.1%}")

        mood_score = self.video_thread.detector.get_mood_score()
        self.mood_score_bar.setValue(int(mood_score))

        if mood_score < 30:
            self.mood_score_bar.setStyleSheet(
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F08080, stop:1 #FF6347); border-radius: 8px; }")
        elif mood_score < 60:
            self.mood_score_bar.setStyleSheet(
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFD700, stop:1 #6495ED); border-radius: 8px; }")
        else:
            self.mood_score_bar.setStyleSheet(
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3CB371, stop:1 #7F5EFA); border-radius: 8px; }")

        self.db_manager.log_emotion(self.session_id, emotion, confidence)
        self.animate_widget(self.emotion_display)

    def check_alerts(self):
        alerts = self.video_thread.detector.detect_unusual_behavior()

        for i in reversed(range(self.alerts_layout.count())):
            item = self.alerts_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        if alerts:
            for alert in alerts:
                alert_label = QLabel(alert['message'])
                alert_label.setWordWrap(True)

                if alert['severity'] == 'high':
                    alert_label.setStyleSheet("color: #FF6347; font-weight: bold; padding: 5px;")
                elif alert['severity'] == 'medium':
                    alert_label.setStyleSheet("color: #FFD700; font-weight: bold; padding: 5px;")

                self.alerts_layout.addWidget(alert_label)

                self.db_manager.log_alert(self.session_id, alert['type'], alert['message'])

                if alert['type'] in ['high_stress', 'elevated_anger'] and not self.breathing_tab.active:
                    QTimer.singleShot(2000, lambda: self.suggest_breathing_exercise())
        else:
            no_alerts = QLabel("✓ No concerning patterns")
            no_alerts.setStyleSheet("color: #3CB371; padding: 5px;")
            self.alerts_layout.addWidget(no_alerts)

    def suggest_breathing_exercise(self):
        suggestion = "I notice you might be feeling stressed. Taking a few minutes for a breathing exercise can really help regulate your system. Please check the **Breathing Exercise** tab!"
        self.add_message(suggestion, is_user=False)

    def send_greeting(self):
        greeting = self.ai_psychologist.get_greeting()
        self.add_message(greeting, is_user=False)

        if self.tts_enabled and self.voice_assistant:
            self.voice_assistant.speak(greeting)

    def send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return

        self.add_message(message, is_user=True)
        self.message_input.clear()

        self.db_manager.log_message(self.session_id, 'user', message, self.current_emotion)

        self.typing_indicator.show()

        QTimer.singleShot(1000, lambda: self.get_ai_response(message))

    def get_ai_response(self, message):

        message_lower = message.lower()
        if any(phrase in message_lower for phrase in
               ['i want to die', 'suicide', 'kill myself', 'i am done', 'end it all']):
            response = self.ai_psychologist._safety_guardrail_response()
        else:
            alerts = self.video_thread.detector.detect_unusual_behavior()
            mood_score = self.video_thread.detector.get_mood_score()

            suggest_game = mood_score < 40 or self.current_emotion in ['sad', 'fear', 'angry']

            response = self.ai_psychologist.generate_response(
                message, self.current_emotion, alerts, mood_score, suggest_game
            )

        self.typing_indicator.hide()

        self.add_message(response, is_user=False)

        self.db_manager.log_message(self.session_id, 'assistant', response, self.current_emotion)

        if self.tts_enabled and self.voice_assistant:
            self.voice_assistant.speak(response)

    def voice_input(self):
        if not self.voice_assistant:
            return

        self.stt_btn.setText("🎤 Listening...")
        self.stt_btn.setEnabled(False)

        QTimer.singleShot(100, self._process_voice_input)

    def _process_voice_input(self):
        text = self.voice_assistant.listen()

        self.stt_btn.setText("🎤 Voice Input")
        self.stt_btn.setEnabled(True)

        if text:
            self.message_input.setText(text)
            self.send_message()
        else:
            self.add_message("I couldn't hear you clearly. Please try again.", is_user=False)

    def toggle_tts(self, checked):
        self.tts_enabled = checked

    def add_message(self, text, is_user=False):
        message_frame = QFrame()
        message_frame.setObjectName("userMessage" if is_user else "aiMessage")
        message_frame.setMaximumWidth(550)

        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(15, 10, 15, 10)

        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setObjectName("messageText")
        message_layout.addWidget(message_label)

        timestamp = QLabel(datetime.now().strftime("%H:%M:%S"))
        timestamp.setObjectName("timestamp")
        timestamp.setAlignment(Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft)
        message_layout.addWidget(timestamp)

        container = QHBoxLayout()
        if is_user:
            container.addStretch()
            container.addWidget(message_frame)
        else:
            container.addWidget(message_frame)
            container.addStretch()

        self.chat_layout.addLayout(container)

        QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

        self.animate_widget(message_frame)

    def animate_widget(self, widget):
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(300)
        animation.setStartValue(0.3)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()

    def update_analytics(self):
        analytics = self.db_manager.get_session_analytics(self.session_id)

        self.analytics_tab.update_stats(
            self.session_id,
            self.session_start,
            analytics['emotions'],
            analytics['messages'],
            analytics['alerts']
        )

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.setStyleSheet(self.get_dark_stylesheet())
            self.theme_btn.setText("🌝")
        else:
            self.setStyleSheet(self.get_light_stylesheet())
            self.theme_btn.setText("🌚")

        self.reposition_global_elements()

    def export_chat(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Chat", "emocare_chat.json", "JSON Files (*.json)")

        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.ai_psychologist.conversation_history, f, indent=2, ensure_ascii=False)

            confirmation = QLabel("✓ Chat exported!")
            confirmation.setStyleSheet("color: #3CB371; font-weight: bold;")
            self.chat_layout.addWidget(confirmation)
            QTimer.singleShot(3000, confirmation.deleteLater)

    def get_light_stylesheet(self):
        PRIMARY_ACCENT = "#7F5EFA"
        SOFT_BACKGROUND = "#F5F6FA"
        PANEL_BACKGROUND = "#FFFFFF"
        TEXT_COLOR = "#2F2F4F"

        return f"""
            QMainWindow {{ background-color: {SOFT_BACKGROUND}; }}

            #mainHeaderTitle {{
                background-color: transparent;  
                color: {PRIMARY_ACCENT};  
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 28px;
                font-weight: 900;  
                padding: 10px;
                letter-spacing: 2px;
                border-bottom: 3px solid {PRIMARY_ACCENT};  
            }}

            #themeButtonCircle {{
                background: {PRIMARY_ACCENT};
                color: white;  
                border: none;  
                border-radius: 20px;
                font-size: 18px;
            }}
            #themeButtonCircle:hover {{
                background: #9B70FF;  
            }}

            #mainTabs::pane {{ border: none; background-color: {PANEL_BACKGROUND}; }}
            QTabBar::tab {{
                background: {SOFT_BACKGROUND};
                color: {TEXT_COLOR}; padding: 12px 30px; margin: 2px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 14px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PRIMARY_ACCENT}AA, stop:1 {PRIMARY_ACCENT});
                color: white;
            }}
            QTabBar::tab:hover {{ background: #EBE9F5; }}

            #leftPanel {{
                background-color: {PANEL_BACKGROUND};  
                border-right: 2px solid #EBE9F5;
            }}
            #rightPanel {{ background-color: {PANEL_BACKGROUND}; }}
            #panelTitle, #chatTitle {{ font-size: 22px; font-weight: bold; color: {PRIMARY_ACCENT}; padding: 10px; }}
            #chatTitle {{ color: {TEXT_COLOR}; }}

            #cameraContainer {{
                background-color: #352D45;
                border-radius: 15px;  
                border: 3px solid #EBE9F5;
            }}
            #faceCountLabel {{ font-size: 14px; color: {TEXT_COLOR}; font-weight: bold; padding: 5px; }}

            #emotionFrame, #alertsFrame, #statsFrame {{
                background-color: #FFFFFF;  
                border-radius: 12px;  
                padding: 15px;  
                border: 1px solid #EBE9F5;
            }}
            #sectionTitle {{ font-size: 16px; font-weight: bold; color: {PRIMARY_ACCENT}; margin-bottom: 5px; }}
            #emotionDisplay {{ font-size: 32px; font-weight: bold; color: {TEXT_COLOR}; padding: 10px; }}

            #moodScoreBar {{ height: 25px; border-radius: 12px; text-align: center; background-color: #EBE9F5; border: 1px solid #CCC; }}

            #alertsScroll {{ background-color: transparent; border: none; }}
            #chatScroll {{ background-color: {SOFT_BACKGROUND}; border: none; border-radius: 10px; }}

            #userMessage {{
                background: {PRIMARY_ACCENT};
                border-radius: 15px; border: none;
            }}
            #aiMessage {{ background-color: #EBE9F5; border-radius: 15px; border: 1px solid #CCC; }}
            #userMessage #messageText {{ color: white; font-size: 14px; }}
            #aiMessage #messageText {{ color: {TEXT_COLOR}; font-size: 14px; }}
            #timestamp {{ font-size: 10px; color: rgba(0, 0, 0, 0.5); }}
            #userMessage #timestamp {{ color: rgba(255, 255, 255, 0.7); }}
            #typingIndicator {{ color: #A9A9A9; font-style: italic; padding: 5px 15px; }}

            #inputFrame {{ background-color: {PANEL_BACKGROUND}; border-radius: 25px; border: 1px solid #CCC; }}
            #messageInput {{  
                border: none; font-size: 14px; padding: 10px; background-color: transparent;
                color: {TEXT_COLOR};  
            }}

            #sendButton, #exportButton, #voiceButton {{  
                background: {PRIMARY_ACCENT};
                color: white; border: none; padding: 10px 20px; border-radius: 20px; font-weight: bold; font-size: 13px;
            }}
            #sendButton:hover, #exportButton:hover, #voiceButton:hover {{
                background: #9B70FF;
            }}

            #quickLinkButton {{
                background-color: {PANEL_BACKGROUND};  
                color: {PRIMARY_ACCENT};  
                border: 2px solid {PRIMARY_ACCENT};  
                padding: 8px 15px;  
                border-radius: 15px;  
                font-weight: bold;  
                font-size: 13px;
            }}
            #quickLinkButton:hover {{ background-color: #EBE9F5; }}

            #voiceCheckbox {{ color: {TEXT_COLOR}; font-size: 13px; spacing: 5px; }}

            #breathingFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,  
                    stop:0 #E0E0FF, stop:0.5 #F0F0FF, stop:1 #E0E0FF);  
                border-radius: 20px;  
                padding: 30px;  
                margin: 50px;
                min-height: 600px;
            }}
            #breathingTitle {{ font-size: 28px; font-weight: bold; color: {PRIMARY_ACCENT}; margin-bottom: 20px; }}
            #breathingInstruction {{ font-size: 20px; min-height: 50px; color: {TEXT_COLOR}; }}
            #cycleCountLabel {{ font-size: 16px; color: {TEXT_COLOR}; }}
            #breathingView {{ background: transparent; border: none; }}

            #breathingButton {{
                background-color: {PRIMARY_ACCENT};  
                color: white;  
                border: none;  
                padding: 15px 40px;  
                border-radius: 25px;  
                font-weight: bold;  
                font-size: 16px;  
                margin: 10px;
            }}
            #breathingButton:hover {{ background-color: #9B70FF; }}

            /* ⭐ NEW STYLING FOR LIGHT THEME SPIN BOX ⭐ */
            #breathingSpinBox {{  
                border: 2px solid {TEXT_COLOR}; /* Dark border */
                border-radius: 8px; 
                padding: 10px; /* Increased padding */
                color: white; 
                background-color: #2F2F4F; /* Dark navy background */
                font-size: 16px; /* Larger font */
                font-weight: bold;
                min-width: 60px; /* Ensure a minimum size */
                min-height: 40px;
            }}

            #calmingGames {{ padding: 0px; background-color: {SOFT_BACKGROUND}; }}
            #calmingGames QWidget {{ background-color: {PANEL_BACKGROUND}; border-radius: 10px; }}
            #calmingGames QLabel {{ color: {TEXT_COLOR}; }}

            #stopAllSoundsButton {{
                background: #FF6347;
                color: {TEXT_COLOR};  
                border: none;  
                padding: 10px 20px;  
                border-radius: 15px;  
                font-weight: bold;
            }}
            #stopAllSoundsButton:hover {{
                background: #FF4747;
            }}

            .ZenFlowCanvas {{ background-color: #000510; border: none; }}

            QSlider::groove:vertical {{ border: 1px solid #CCC; background: #EBE9F5; width: 10px; border-radius: 4px; }}
            QSlider::handle:vertical {{ background: {PRIMARY_ACCENT}; border: 1px solid #9B70FF; height: 16px; width: 16px; margin: -4px 0; border-radius: 8px; }}

            QSpinBox {{  
                border: 1px solid #CCC; border-radius: 8px; padding: 5px; color: {TEXT_COLOR}; background-color: white;
            }}

            #dashboardTitle {{ font-size: 26px; font-weight: bold; color: {PRIMARY_ACCENT}; margin: 20px; }}
            #statLabel {{ font-size: 16px; color: {TEXT_COLOR}; padding: 10px; background-color: #EBE9F5; border-radius: 8px; margin: 5px 0; }}
            QLabel {{ color: {TEXT_COLOR}; }}
        """

    def get_dark_stylesheet(self):
        PRIMARY_ACCENT = "#9B70FF"
        SOFT_BACKGROUND = "#1A1523"
        PANEL_BACKGROUND = "#282038"
        TEXT_COLOR = "#EBE9F5"

        return f"""
            QMainWindow {{ background-color: {SOFT_BACKGROUND}; }}

            #mainHeaderTitle {{
                background-color: transparent;  
                color: {PRIMARY_ACCENT};  
                font-family: 'Impact', 'Arial Black', sans-serif;
                font-size: 28px;
                font-weight: 900;
                padding: 10px;
                letter-spacing: 2px;
                border-bottom: 3px solid {PRIMARY_ACCENT};  
            }}

            #themeButtonCircle {{
                background: {PRIMARY_ACCENT};
                color: {TEXT_COLOR};  
                border: none;  
                border-radius: 20px;  
                font-size: 18px;
            }}
            #themeButtonCircle:hover {{
                background: #7F5EFA;
            }}

            #mainTabs::pane {{ border: none; background-color: {PANEL_BACKGROUND}; }}
            QTabBar::tab {{
                background: #352D45;
                color: {TEXT_COLOR}; padding: 12px 30px; margin: 2px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 14px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7F5EFA, stop:1 {PRIMARY_ACCENT});
                color: white;
            }}

            #leftPanel {{
                background-color: {PANEL_BACKGROUND};  
                border-right: 2px solid {SOFT_BACKGROUND};
            }}
            #rightPanel {{ background-color: {PANEL_BACKGROUND}; }}
            #panelTitle, #chatTitle {{ font-size: 22px; font-weight: bold; color: {PRIMARY_ACCENT}; padding: 10px; }}
            #chatTitle {{ color: {TEXT_COLOR}; }}

            #cameraContainer {{
                background-color: #1A1523;
                border-radius: 15px;  
                border: 3px solid #352D45;
            }}
            #faceCountLabel {{ font-size: 14px; color: {TEXT_COLOR}; font-weight: bold; padding: 5px; }}

            #emotionFrame, #alertsFrame, #statsFrame {{
                background-color: #352D45;  
                border-radius: 12px;  
                padding: 15px;  
                border: 1px solid #453A5A;
            }}
            #sectionTitle {{ font-size: 16px; font-weight: bold; color: {PRIMARY_ACCENT}; margin-bottom: 5px; }}
            #emotionDisplay {{ font-size: 32px; font-weight: bold; color: {TEXT_COLOR}; padding: 10px; }}

            #moodScoreBar {{ height: 25px; border-radius: 12px; text-align: center; background-color: #352D45; color: white; border: 1px solid #453A5A; }}

            #chatScroll {{ background-color: #352D45; border: none; border-radius: 10px; }}

            #userMessage {{
                background: {PRIMARY_ACCENT};
                border-radius: 15px; border: none;
            }}
            #aiMessage {{ background-color: #352D45; border-radius: 15px; border: 1px solid #453A5A; }}
            #userMessage #messageText, #aiMessage #messageText {{ color: white; font-size: 14px; }}
            #timestamp {{ font-size: 10px; color: rgba(255, 255, 255, 0.5); }}
            #typingIndicator {{ color: #A9A9A9; font-style: italic; padding: 5px 15px; }}

            #inputFrame {{ background-color: {PANEL_BACKGROUND}; border-radius: 25px; border: 1px solid {PRIMARY_ACCENT}; }}
            #messageInput {{  
                border: none; font-size: 14px; padding: 10px; background-color: transparent; color: white;  
            }}

            #sendButton, #exportButton, #voiceButton {{
                background: {PRIMARY_ACCENT};
                color: white; border: none; padding: 10px 20px; border-radius: 20px; font-weight: bold; font-size: 13px;
            }}
            #sendButton:hover, #exportButton:hover, #voiceButton:hover {{
                background: #7F5EFA;
            }}

            #quickLinkButton {{
                background-color: {PANEL_BACKGROUND};  
                color: {PRIMARY_ACCENT};  
                border: 2px solid {PRIMARY_ACCENT};  
                padding: 8px 15px;  
                border-radius: 15px;  
                font-weight: bold;  
                font-size: 13px;
            }}
            #quickLinkButton:hover {{ background-color: #352D45; }}

            #voiceCheckbox {{ color: {TEXT_COLOR}; font-size: 13px; }}

            #breathingFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,  
                    stop:0 #7F5EFA, stop:0.5 #9B70FF, stop:1 #7F5EFA);  
                border-radius: 20px;  
                padding: 30px;  
                margin: 50px;
                min-height: 600px;
            }}
            #breathingTitle {{ font-size: 28px; font-weight: bold; color: white; margin-bottom: 20px; }}
            #breathingInstruction {{ font-size: 20px; min-height: 50px; color: {TEXT_COLOR}; }}
            #cycleCountLabel {{ font-size: 16px; color: {TEXT_COLOR}; }}
            #breathingView {{ background: transparent; border: none; }}

            #breathingButton {{
                background-color: white;  
                color: {PRIMARY_ACCENT};  
                border: none;  
                padding: 15px 40px;  
                border-radius: 25px;  
                font-weight: bold;  
                font-size: 16px;  
                margin: 10px;
            }}
            #breathingButton:hover {{ background-color: #EBE9F5; }}

            /* DARK THEME SPIN BOX: Uses contrast for visibility */
            #breathingSpinBox {{
                border: 1px solid #453A5A; 
                border-radius: 8px; 
                padding: 10px; /* Increased padding */
                color: white; 
                background-color: #1A1523; /* Very dark background */
                font-size: 16px;
                font-weight: bold;
                min-width: 60px;
                min-height: 40px;
            }}

            #calmingGames {{ padding: 0px; background-color: {SOFT_BACKGROUND}; }}
            #calmingGames QWidget {{ background-color: {PANEL_BACKGROUND}; border-radius: 10px; }}
            #calmingGames QLabel {{ color: {TEXT_COLOR}; }}

            #stopAllSoundsButton {{
                background: #FF6347;
                color: white;  
                border: none;  
                padding: 10px 20px;  
                border-radius: 15px;  
                font-weight: bold;
            }}
            #stopAllSoundsButton:hover {{
                background: #FF4747;
            }}

            .ZenFlowCanvas {{ background-color: #000510; border: none; }}

            QSlider::groove:vertical {{ border: 1px solid #453A5A; background: {SOFT_BACKGROUND}; width: 10px; border-radius: 4px; }}
            QSlider::handle:vertical {{ background: {PRIMARY_ACCENT}; border: 1px solid #7F5EFA; height: 16px; width: 16px; margin: -4px 0; border-radius: 8px; }}

            QSpinBox {{
                border: 1px solid #453A5A; border-radius: 8px; padding: 5px; color: white; background-color: #1A1523;
            }}

            #dashboardTitle {{ font-size: 26px; font-weight: bold; color: {PRIMARY_ACCENT}; margin: 20px; }}
            #statLabel {{ font-size: 16px; color: {TEXT_COLOR}; padding: 10px; background-color: #352D45; border-radius: 8px; margin: 5px 0; }}
            QLabel {{ color: {TEXT_COLOR}; }}
        """

    def closeEvent(self, event):
        mood_score = self.video_thread.detector.get_mood_score()
        emotion_counts = Counter([e for e in self.video_thread.detector.emotion_history])
        dominant = emotion_counts.most_common(1)[0][0] if emotion_counts else "neutral"

        self.db_manager.end_session(self.session_id, dominant, mood_score)

        self.video_thread.stop()

        event.accept()


# ============================================================================
# ULTIMATE FIX CLASS: EmoCareApplication (subclassing QApplication)
# ============================================================================

class EmoCareApplication(QApplication):
    """
    Custom QApplication subclass to intercept key events
    BEFORE they are processed by the main window or any widget,
    providing a GUARANTEED fix for the macOS backspace focus loss.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self.message_input = None

    def notify(self, receiver, event):
        """Intercepts all events generated by the system."""

        if platform.system() == "Darwin" and event.type() == event.Type.KeyPress:
            key_event = event

            if self.message_input and isinstance(self.message_input, QLineEdit):

                if not self.message_input.hasFocus():

                    key = key_event.key()
                    if key == Qt.Key.Key_Backspace or key == Qt.Key.Key_Delete or key == Qt.Key.Key_Return:

                        if self.message_input.isVisible() and self.message_input.isEnabled():
                            self.message_input.setFocus(Qt.FocusReason.ActiveWindow)

                            QApplication.sendEvent(self.message_input, key_event)

                            return True

        return super().notify(receiver, event)


# ============================================================================
# APPLICATION ENTRY POINT (Modified to use EmoCareApplication)
# ============================================================================

def main():
    """Main application entry point"""
    app = EmoCareApplication(sys.argv)

    app.setApplicationName("EmoCare")
    app.setApplicationVersion("2.10.10")
    app.setOrganizationName("EmoCare AI")

    print("=" * 60)
    print("🎯 EmoCare - VenomMind Lab (Style Fix Edition - v2.10.10)")
    print(
        "Version 2.10.10: **Breathing Cycle SpinBox** style updated to be dark/bold in the Light Theme.")
    print("-" * 60)
    print(f"Configuration:")
    print(f"  - Smoothing Window: {SMOOTHING_WINDOW_SIZE} frames (approx 2.5s)")
    print(f"  - Detection Rate: 1 frame every {DETECTION_INTERVAL} (reduced CPU)")
    print(f"  - Zen Flow Gravity: {ZEN_FLOW_GRAVITY} (New Game)")
    print(f"  - Global Sound Cooldown: {GLOBAL_SOUND_COOLDOWN}s")
    print("=" * 60)

    if PYGAME_AVAILABLE and NUMPY_AVAILABLE:
        print("✓ Pygame Mixer Initialized. Audio is now active (Requires sound files: rain.wav, etc.)")
    else:
        print("⚠️ Pygame/NumPy not found. Sound mixing is visual only.")

    if VOICE_AVAILABLE:
        print("✓ Voice features enabled")
    else:
        print("⚠️ Voice features disabled.")

    if FER_AVAILABLE:
        print("✓ Advanced emotion detection (FER)")
    else:
        print("⚠️ Using basic emotion detection (install: pip install fer)")

    if PLOT_AVAILABLE:
        print("✓ Matplotlib/Charts enabled for Analytics")
    else:
        print("⚠️ Charts disabled (install: pip install matplotlib PyQt6-Charts)")

    print("\n🤖 Llama 3.2 Integration Status:")
    print("Backend: http://localhost:11434/api/generate")
    print("Model: llama3.2")
    print("\n✓ Application starting...")
    print("=" * 60 + "\n")

    window = EmoCareApp()

    window.message_input.setFocus()
    app.message_input = window.message_input

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
