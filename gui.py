import speech_recognition as sr
import os
import webbrowser
import datetime
import threading
import time
import subprocess
import requests
import json
import urllib.parse
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import math
import random
import google.generativeai as genai
from google.generativeai import types
import re
import platform
import glob
import cv2
from PIL import Image, ImageTk


# --- Dynamic Entry Field Class for Glow Effect ---
class DynamicEntry(tk.Entry):
    def __init__(self, master=None, glow_color='#00ffff', default_color='#7048e8', **kwargs):
        super().__init__(master, **kwargs)
        self.glow_color = glow_color
        self.default_color = default_color
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        # Apply initial highlight colors and thickness
        self.config(highlightbackground=self.default_color, highlightcolor=self.glow_color, highlightthickness=3)

    def _on_enter(self, event):
        self.config(highlightthickness=4)  # Increased glow thickness on hover

    def _on_leave(self, event):
        self.config(highlightthickness=3)  # Default thickness


# --- END NEW CLASS ---


class VenomAssistantGUI:
    def __init__(self, master):
        self.master = master
        master.title("Made by Krish 🔧")
        master.geometry("1400x1000")
        master.resizable(True, True)
        master.configure(bg='#000000')

        # Full screen and transparency
        try:
            master.attributes('-fullscreen', True)
            master.attributes('-alpha', 0.98)
            master.attributes('-topmost', False)
        except:
            pass

        # --- Constants for Visuals & Performance ---
        self.FRAME_RATE_MS = 40
        self.PARTICLE_COUNT = 80
        self.ORB_RADIUS = 60
        self.BASE_GLOW_RADIUS = 80
        self.VOICE_BARS = 48
        self.VIDEO_STREAM_DELAY = 10
        self.NEON_FONT = ("Orbitron", 16, "bold")
        self.BODY_FONT = ("Consolas", 10)
        self.CODE_FONT = ("Consolas", 10)
        self.DATA_STREAM_COUNT = 150

        # ---- Configuration ----
        # NOTE: Using a placeholder key for demonstration. Users must replace this.
        self.gemini_api_key = "AIzaSyAgVb6kApTaE-PtbfJkmadwjojYKjT1BF8" # REPLACE WITH YOUR KEY

        if not self.gemini_api_key or self.gemini_api_key == "YOUR_HARDCODED_GEMINI_API_KEY_HERE":
            print("FATAL: Gemini API key is the placeholder. Gemini features will be disabled or limited.")
            self.gemini_api_key = ""

        try:
            if self.gemini_api_key:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
                self.gemini_chat = self.gemini_model.start_chat(history=[])
            else:
                self.gemini_model = None
                self.gemini_chat = None
        except Exception as e:
            print(f"Gemini configuration failed: {e}")
            self.gemini_model = None
            self.gemini_chat = None

        # New: Dedicated chat for code context
        self.gemini_code_chat = None

        # ---- Theme Palettes (Finalized) ----
        self.dark_palette = {
            'bg_deep_space': '#0a0a0f',
            'bg_dark_void': '#1a1a2e',
            'bg_panel': '#2c2c54',
            'primary_blue': '#4a9eff',
            'electric_cyan': '#00ffff',
            'neon_purple': '#ff00ff',
            'plasma_pink': '#ff4a9e',
            'energy_white': '#ffffff',
            'ghost_white': '#f0f8ff',
            'warning_orange': '#ff6b35',
            'danger_red': '#ff3366',
            'success_green': '#00ff7f',
            'accent_gold': '#ffc107',
            'accent_deep_purple': '#673ab7'
        }

        # --- ENHANCED LIGHT PALETTE (Frosted Glass/High-Tech Look) ---
        self.light_palette = {
            'bg_deep_space': '#f1f3f5',
            'bg_dark_void': '#ffffff',
            'bg_panel': '#e9ecef',
            'primary_blue': '#495057',
            'electric_cyan': '#1c7ed6',
            'neon_purple': '#7048e8',
            'plasma_pink': '#ff2d55',
            'energy_white': '#ffffff',
            'ghost_white': '#212529',
            'warning_orange': '#f76707',
            'danger_red': '#fa5252',
            'success_green': '#37b24d',
            'accent_gold': '#ff9500',
            'accent_deep_purple': '#7048e8'
        }
        # -----------------------------------------------------

        self.current_theme = 'dark'
        self.is_dark_mode = True
        self._load_current_palette()
        self.setup_ttk_styles()

        # ---- Face Scanner State Variables (UPDATED: Now Vision Query) ----
        self.is_face_scanner_active = False
        self.face_scanner_window = None
        self.face_scanner_label = None
        self.video_capture = None
        self.video_frame_id = None
        self.webcam_image = None
        self.last_query = ""

        # ---- Animation State Variables ---
        self.animation_time = 0
        self.ring_rotations = [0, 0, 0, 0, 0]
        self.ring_speeds = [0.5, -0.3, 0.7, -0.4, 0.6]
        self.pulse_phase = 0
        self.orb_glow = 0
        self.particle_systems = []
        self.energy_waves = []

        self.data_streams = []

        self.is_active_state = False
        self.voice_amplitude = 0
        self.voice_frequency_data = [0] * self.VOICE_BARS
        self.mouse_pos = (0, 0)
        self.mouse_trail = []
        self.blink_timer = 0
        self.is_blinking = False
        self.neural_nodes = []
        self.neural_links = []

        # ---- System State ----
        self.is_listening = False
        self.is_speaking = False
        self.listening_thread = None
        self.say_process = None
        self.recognizer = sr.Recognizer()

        # ---- CODE CONTEXT STATE ----
        self.awaiting_code_followup = False
        self.current_project_path = None

        # ---- Modal Window States ----
        self.response_window = None
        self.toolbox_window = None

        # References to buttons/widgets in the modal
        self.listen_btn = None
        self.stop_btn = None
        self.mute_btn = None
        self.input_entry = None

        # --- NEW REFERENCES FOR RESPONSE WINDOW INPUT ---
        self.response_entry = None
        self.response_send_btn = None
        # --- END NEW REFERENCES ---

        # Initialize UI
        self.setup_main_interface()
        self.initialize_particles()
        self.initialize_neural_network()
        self.initialize_data_streams()  # Initialize background streams

        # Start all animations
        self.start_master_animation()

        # Event bindings
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.bind("<F11>", self.toggle_fullscreen)
        self.master.bind("<Escape>", lambda e: self.on_closing())
        self.master.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # --- Spacebar Hotkey Binding (Robust) ---
        self.master.bind("<Key-space>", self.on_space_key, add="+")
        # ----------------------------------------

        # System initialization
        self.master.after(1000, self.boot_sequence)

    # --- NEW KEYBINDING HANDLER ---
    def on_space_key(self, event):
        """
        Handles the spacebar key press globally, but prevents activation
        if an entry widget or scrolled text area has focus.
        """
        # Get the currently focused widget
        focused_widget = self.master.focus_get()

        # Check if the focused widget is a subclass of tk.Entry or scrolledtext
        if isinstance(focused_widget, (tk.Entry, scrolledtext.ScrolledText, DynamicEntry)):
            # Allow the spacebar to function normally (insert a space)
            return

        # If no text field has focus, or focus is on a non-text widget, start listening
        self.start_listening_gui()
        # Prevent the spacebar event from propagating further or adding a literal space
        return "break"
        # --- END NEW KEYBINDING HANDLER ---

    def _load_current_palette(self):
        """Loads the colors from the current theme dictionary into instance attributes."""
        palette = self.dark_palette if self.is_dark_mode else self.light_palette
        for key, value in palette.items():
            setattr(self, key, value)

    def setup_ttk_styles(self):
        """
        Initializes and configures the custom TTK styles.
        """
        self.style = ttk.Style()
        theme_name = "venom_cyberpunk"

        # 1. Theme Creation (Only runs once per session)
        if theme_name not in self.style.theme_names():
            try:
                self.style.theme_create(theme_name, parent="alt", settings={
                    "TButton": {
                        "configure": {
                            "font": ("Orbitron", 10, "bold"),
                            "relief": "flat",
                            "borderwidth": 2,
                            "focuscolor": ''
                        }
                    }
                })
            except tk.TclError:
                pass

        # 2. Theme Use
        self.style.theme_use(theme_name)

        # 3. Individual Style Configurations (Runs every time the palette changes)

        # Base Widget Configuration (TFrame/TLabel)
        self.style.configure("TFrame", background=self.bg_dark_void)
        self.style.configure("TLabel", background=self.bg_dark_void, foreground=self.ghost_white, font=self.BODY_FONT)

        # --- Default TButton Configuration (High-Contrast Light/Cyberpunk Dark) ---
        self.style.configure("TButton",
                             background=self.primary_blue,
                             foreground=self.energy_white,
                             bordercolor=self.electric_cyan if self.is_dark_mode else self.primary_blue)

        # Dynamic Mapping for TButton (Crucial for Light Theme Hover Effect)
        self.style.map("TButton",
                       # Background changes on active state
                       background=[("active", self.electric_cyan),
                                   ("!disabled", self.primary_blue)],
                       # Foreground changes: White on dark buttons, but use the *accent* on active light buttons
                       foreground=[("active", self.bg_deep_space if self.is_dark_mode else self.ghost_white),
                                   ("!disabled", self.energy_white)],
                       relief=[("pressed", "flat"), ("!disabled", "flat")],
                       bordercolor=[("active", self.electric_cyan), ("!disabled", self.primary_blue)]
                       )

        # --- Custom Neon Button Style (Used for Clear Chat) ---
        self.style.configure("Neon.TButton",
                             background=self.neon_purple,
                             foreground=self.energy_white,
                             bordercolor=self.neon_purple)
        self.style.map("Neon.TButton",
                       background=[("active", self.electric_cyan)],
                       foreground=[("active", self.bg_deep_space)])  # Keep foreground black/deep space on active

        # --- Custom Warning Button Style ---
        self.style.configure("Warning.TButton",
                             background=self.warning_orange,
                             foreground=self.energy_white,  # Use white/light text on the colored button
                             bordercolor=self.warning_orange)
        self.style.map("Warning.TButton",
                       background=[("active", self.accent_gold)])

        # --- Custom Danger Button Style ---
        self.style.configure("Danger.TButton",
                             background=self.danger_red,
                             foreground=self.energy_white,
                             bordercolor=self.danger_red)
        self.style.map("Danger.TButton",
                       background=[("active", self.neon_purple)])

        # --- Custom Success Button Style ---
        self.style.configure("Success.TButton",
                             background=self.success_green,
                             foreground=self.energy_white,
                             bordercolor=self.success_green)
        self.style.map("Success.TButton",
                       background=[("active", self.electric_cyan)])

    def apply_theme(self, theme_name):
        """Applies the selected theme colors and recreates windows if necessary."""
        self.current_theme = theme_name
        self.is_dark_mode = (theme_name == 'dark')
        self._load_current_palette()
        self.setup_ttk_styles()  # Re-apply styles/configs with new palette

        self.master.configure(bg=self.bg_deep_space)
        self.main_frame.configure(bg=self.bg_deep_space)
        self.canvas.configure(bg=self.bg_deep_space)

        # Status label (always use a high-contrast color)
        self.status_label.configure(
            fg=self.neon_purple,
            bg=self.bg_deep_space
        )

        self.setup_text_tags()
        self.initialize_particles()
        self.initialize_neural_network()
        self.initialize_data_streams()  # Re-initialize streams with new dimensions/colors
        self.draw_ai_visualization()

        # Re-create Toplevel windows to apply new colors
        if self.toolbox_window and self.toolbox_window.winfo_exists():
            # Destroy and recreate to apply new theme colors to Toplevel and widgets
            self.toolbox_window.destroy()
            self.master.after(100, self.create_toolbox_interface)

        if self.response_window and self.response_window.winfo_exists():
            # Destroy and recreate to apply new theme colors
            response_text_buffer = "Theme Updated. Please regenerate response."
            # Attempt to grab current response text if possible before destroying
            try:
                # Assuming the main text widget in the response window is the first child of the main frame
                text_widget = next(c for c in self.response_window.winfo_children()[0].winfo_children() if
                                   isinstance(c, scrolledtext.ScrolledText))
                # Only use the existing content if it's substantial and not a default message
                if len(text_widget.get("1.0", tk.END).strip()) > 50:
                    response_text_buffer = text_widget.get("1.0", tk.END)
            except Exception:
                pass

            self.response_window.destroy()
            self.master.after(100, lambda: self.create_response_interface(response_text_buffer))

    # --- GUI SETUP METHODS ---

    def center_window(self, win, width, height):
        """Helper to center any tkinter window/toplevel with set size"""
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')

    def setup_main_interface(self):
        """Create the main visual interface (minimalist: just canvas and status)"""
        self.main_frame = tk.Frame(self.master, bg=self.bg_deep_space)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg=self.bg_deep_space, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Status display (Positioned at 92% height)
        self.status_label = tk.Label(self.main_frame,
                                     text="◆ INITIALIZING ◆",
                                     font=("Orbitron", 18, "bold"),  # Slightly larger
                                     fg=self.electric_cyan,
                                     bg=self.bg_deep_space,
                                     anchor='s')

        self.status_label.place(relx=0.5, rely=0.92, anchor=tk.CENTER)

        # Hidden log for chat history and fine-tuning data source
        self.output_text = scrolledtext.ScrolledText(self.main_frame, width=1, height=1,
                                                     bg=self.bg_panel, fg=self.ghost_white)
        self.setup_text_tags()

    def create_toolbox_interface(self):
        """
        Creates the Modal Toolbox window with **Enhanced Frosted Glass** look
        using ttk buttons and enhanced entry styles.
        """
        if self.toolbox_window and self.toolbox_window.winfo_exists():
            self.toolbox_window.lift()
            return

        self.toolbox_window = tk.Toplevel(self.master)
        self.toolbox_window.title("VENOM TOOLS")
        self.toolbox_window.attributes('-alpha', 0.95)
        self.toolbox_window.config(bg=self.bg_dark_void)
        self.toolbox_window.transient(self.master)
        self.toolbox_window.focus_set()

        # Set specific size
        win_w, win_h = 600, 380  # Increased height and padding
        self.center_window(self.toolbox_window, win_w, win_h)

        self.toolbox_window.protocol("WM_DELETE_WINDOW", lambda: self.destroy_toolbox())

        # Main frame with Frosted Glass BG
        main_frame = tk.Frame(self.toolbox_window, bg=self.bg_dark_void, padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Title (Larger font, Accent color)
        tk.Label(main_frame, text="◇ MANUAL INPUT & UTILITIES ◇",
                 font=self.NEON_FONT,
                 fg=self.neon_purple, bg=self.bg_dark_void).pack(pady=(0, 25))

        # 2. Input Area (Styled Entry and TTK Button)
        input_frame = tk.Frame(main_frame, bg=self.bg_dark_void)
        input_frame.pack(fill=tk.X, pady=(0, 30))

        # --- Dynamic Entry Field ---
        self.input_entry = DynamicEntry(input_frame,
                                        font=("Consolas", 14),
                                        bg=self.bg_panel,
                                        fg=self.ghost_white,
                                        insertbackground=self.electric_cyan,
                                        relief=tk.FLAT, bd=1, highlightthickness=3,
                                        glow_color=self.electric_cyan,
                                        default_color=self.accent_deep_purple)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        self.input_entry.bind("<Return>", self.process_typed_command_event)

        # Send Button (Using TTK)
        self.send_btn = ttk.Button(input_frame, text="SEND",
                                   style="TButton",  # Default TTK Button Style
                                   command=self.process_typed_command,
                                   cursor="hand2")
        self.send_btn.pack(side=tk.RIGHT, ipady=3)

        # 3. Utility Buttons (Row 1 - TTK Neon/Danger)
        control_frame1 = tk.Frame(main_frame, bg=self.bg_dark_void)
        control_frame1.pack(fill=tk.X, pady=(0, 10))
        for i in range(3): control_frame1.columnconfigure(i, weight=1)

        def create_ttk_control_button(parent, text, command, style, row, col):
            btn = ttk.Button(parent, text=text, command=command, style=style, cursor="hand2")
            btn.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            return btn

        create_ttk_control_button(control_frame1, "⟲ CLEAR CHAT",
                                  self.clear_output, "Neon.TButton", 0, 0)

        theme_text = f"💡 SWITCH TO {'DARK' if not self.is_dark_mode else 'LIGHT'}"
        # Use a Warning style button for Theme switch
        create_ttk_control_button(control_frame1, theme_text,
                                  self.toggle_theme, "Warning.TButton", 0, 1)

        create_ttk_control_button(control_frame1, "⚡ POWER OFF",
                                  self.on_closing, "Danger.TButton", 0, 2)

        # 4. Utility Buttons (Row 2 - VISION Button and Load Project Button)
        control_frame2 = tk.Frame(main_frame, bg=self.bg_dark_void)
        control_frame2.pack(fill=tk.X)
        control_frame2.columnconfigure(0, weight=1)
        control_frame2.columnconfigure(1, weight=1)

        # VISION SCANNER
        scanner_text = "👁️ VISION SCANNER: OFF" if not self.is_face_scanner_active else "👁️ VISION SCANNER: ON"
        # Use a custom style for the scanner button (Success or Default)
        scanner_style = "Success.TButton" if self.is_face_scanner_active else "TButton"

        self.scanner_btn = create_ttk_control_button(control_frame2, scanner_text,
                                                     self.toggle_face_scanner, scanner_style, 0, 0)
        # Manually update style color if active (TTK Map is not always reactive enough for state change)
        if self.is_face_scanner_active:
            self.scanner_btn.configure(style="Success.TButton")
        else:
            self.scanner_btn.configure(style="TButton")

        # LOAD PROJECT BUTTON (NEW)
        create_ttk_control_button(control_frame2, "📁 LOAD PROJECT",
                                  self.select_and_load_project, "TButton", 0, 1)  # Default TButton

    def destroy_toolbox(self):
        """Cleans up the toolbox window reference."""
        if self.toolbox_window:
            # Clear input entry reference
            if self.input_entry:
                self.input_entry.destroy()
            self.toolbox_window.destroy()
            self.toolbox_window = None
            self.input_entry = None
            self.scanner_btn = None  # Clear reference

    def create_response_interface(self, response_text):
        """
        Creates the Modal response window with **Enhanced Frosted Glass/High-Tech**
        and updated TTK controls.
        """

        # Close any existing response window before creating a new one
        if self.response_window and self.response_window.winfo_exists():
            self.stop_speaking_gui(kill_only=True)
            # Destroy and clear entry references before recreating
            if self.response_entry:
                self.response_entry.destroy()
            self.response_window.destroy()

        self.response_window = tk.Toplevel(self.master)
        self.response_window.title("VENOM RESPONSE")
        self.response_window.attributes('-alpha', 0.95)
        self.response_window.config(bg=self.bg_dark_void)
        self.response_window.transient(self.master)
        self.response_window.focus_set()

        # Set specific size
        win_w, win_h = 850, 550
        self.center_window(self.response_window, win_w, win_h)

        self.response_window.protocol("WM_DELETE_WINDOW", self.destroy_response_window)

        main_frame = tk.Frame(self.response_window, bg=self.bg_dark_void, padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Title (Accent color for a successful response)
        tk.Label(main_frame, text="◇ NEURAL RESPONSE ◇",
                 font=self.NEON_FONT,
                 fg=self.success_green, bg=self.bg_dark_void).pack(pady=(0, 20))

        # 2. Scrolled Text Output (Panel background)
        output_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            font=self.CODE_FONT,
            bg=self.bg_panel,
            fg=self.ghost_white,
            insertbackground=self.electric_cyan,
            selectbackground=self.neon_purple,
            relief=tk.FLAT, bd=3, highlightthickness=3,
            highlightbackground=self.accent_deep_purple,
            highlightcolor=self.success_green
        )
        output_text.pack(fill=tk.BOTH, expand=True)

        output_text.tag_config('venom', foreground=self.success_green, font=("Consolas", 10, "bold"))
        output_text.insert(tk.END, response_text, 'venom')
        output_text.see(tk.END)

        # 3. Follow-up Command Bar (Styled Entry and TTK Button)
        search_frame = tk.Frame(main_frame, bg=self.bg_dark_void)
        search_frame.pack(fill=tk.X, pady=(20, 10))

        # --- Dynamic Entry Field ---
        self.response_entry = DynamicEntry(search_frame,
                                           font=("Consolas", 13),
                                           bg=self.bg_panel,
                                           fg=self.ghost_white,
                                           insertbackground=self.electric_cyan,
                                           relief=tk.FLAT, bd=1, highlightthickness=3,
                                           glow_color=self.electric_cyan,
                                           default_color=self.accent_deep_purple)
        self.response_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        self.response_entry.bind("<Return>", self.process_typed_command_event)

        # Send Button (Using TTK)
        self.response_send_btn = ttk.Button(search_frame, text="SEND CMD",
                                            style="TButton",
                                            command=self.process_response_typed_command,
                                            cursor="hand2")
        self.response_send_btn.pack(side=tk.RIGHT, ipady=3)

        # 4. Voice Controls (TTK Buttons)
        voice_control_frame = tk.Frame(main_frame, bg=self.bg_dark_void, pady=10)
        voice_control_frame.pack(fill=tk.X)
        for i in range(3): voice_control_frame.columnconfigure(i, weight=1)

        def create_ttk_voice_button(parent, text, command, style, col):
            btn = ttk.Button(parent, text=text, command=command, style=style, cursor="hand2")
            btn.grid(row=0, column=col, padx=10, pady=5, sticky="ew")
            return btn

        # Assign control references (LISTEN, STOP, MUTE)
        self.listen_btn = create_ttk_voice_button(voice_control_frame, "◉ LISTEN", self.start_listening_gui,
                                                  "Success.TButton", 0)
        self.stop_btn = create_ttk_voice_button(voice_control_frame, "◼ STOP LISTENING", self.stop_listening_gui,
                                                "Danger.TButton", 1)
        self.mute_btn = create_ttk_voice_button(voice_control_frame, "🔇 MUTE TTS", self.stop_speaking_gui,
                                                "Warning.TButton", 2)

        self._update_response_button_states()

        # 5. Close Button (Default TTK Style)
        ttk.Button(main_frame, text="CLOSE WINDOW", command=self.destroy_response_window,
                   style="TButton", cursor="hand2").pack(pady=(15, 0))

    def destroy_response_window(self):
        """Stops speaking and safely closes the response window."""
        self.stop_speaking_gui(kill_only=True)
        if self.response_window:
            if self.response_entry:
                self.response_entry.destroy()  # Clear DynamicEntry field reference
            self.response_window.destroy()
            self.response_window = None
            self.listen_btn = None
            self.stop_btn = None
            self.mute_btn = None
            self.response_entry = None  # CLEAR NEW REFERENCE
            self.response_send_btn = None  # CLEAR NEW REFERENCE

    # --- VISION SCANNER METHODS (CORRECTED) ---

    def toggle_face_scanner(self):
        # Renamed logic, still using the same method name for button compatibility
        if self.is_face_scanner_active:
            self.deactivate_face_scanner()
            self.say("Vision scanner deactivated.")
        else:
            self.activate_face_scanner()

        # Update toolbox button immediately if it's open
        if self.toolbox_window and self.scanner_btn:
            scanner_text = "👁️ VISION SCANNER: OFF" if not self.is_face_scanner_active else "👁️ VISION SCANNER: ON"
            scanner_style = "Success.TButton" if self.is_face_scanner_active else "TButton"
            self.scanner_btn.config(text=scanner_text, style=scanner_style)

    def activate_face_scanner(self):
        if self.is_face_scanner_active: return

        self.create_face_scanner_window()

        # Try to open the default camera (index 0)
        try:
            self.video_capture = cv2.VideoCapture(0)
            if not self.video_capture.isOpened():
                raise IOError("Cannot open webcam. Check device index or permissions.")

            self.is_face_scanner_active = True
            self.say("Vision scanner activated. Ready for a query.")
            self.master.after(self.VIDEO_STREAM_DELAY, self.update_video_stream)
            self.display_message("Webcam stream started in dedicated window.", 'system')

        except Exception as e:
            self.is_face_scanner_active = False
            self.display_message(f"Vision Scanner Error: {e}", 'error')
            self.say("Failed to start the vision scanner.")
            self.destroy_face_scanner_window()  # Ensure cleanup

    def create_face_scanner_window(self):
        """Creates the dedicated Toplevel window for the video feed (Updated Style)."""
        if self.face_scanner_window and self.face_scanner_window.winfo_exists():
            self.face_scanner_window.lift()
            return

        self.face_scanner_window = tk.Toplevel(self.master)
        self.face_scanner_window.title("VENOM VISION QUERY")
        self.face_scanner_window.attributes('-alpha', 0.98)
        self.face_scanner_window.config(bg=self.bg_dark_void)
        self.face_scanner_window.transient(self.master)
        self.face_scanner_window.focus_set()

        # Determine target video size (e.g., 640x480 standard webcam)
        video_width, video_height = 640, 480
        self.center_window(self.face_scanner_window, video_width + 40, video_height + 80)

        self.face_scanner_window.protocol("WM_DELETE_WINDOW", self.deactivate_face_scanner)

        # Frame for padding and structure
        main_frame = tk.Frame(self.face_scanner_window, bg=self.bg_dark_void, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title/Status Label (NEON STYLE)
        self.scanner_status_label = tk.Label(main_frame, text="◈ VISION ACTIVE ◈",
                                             font=self.NEON_FONT, fg=self.success_green, bg=self.bg_dark_void)
        self.scanner_status_label.pack(pady=(0, 10))

        # Label to display the video frame (Cyberpunk border effect)
        self.face_scanner_label = tk.Label(main_frame, bg=self.bg_deep_space, width=video_width, height=video_height,
                                           relief=tk.SOLID, bd=3, highlightthickness=3,
                                           highlightbackground=self.neon_purple)  # Neon Border
        self.face_scanner_label.pack(expand=True, fill=tk.BOTH)

        # Close Button (TTK Danger Style)
        ttk.Button(main_frame, text="CLOSE SCANNER", command=self.deactivate_face_scanner,
                   style="Danger.TButton", cursor="hand2").pack(pady=(10, 0))

    def destroy_face_scanner_window(self):
        """Safely destroys the face scanner Toplevel window and clears references."""
        if self.face_scanner_window and self.face_scanner_window.winfo_exists():
            self.face_scanner_window.destroy()
        self.face_scanner_window = None
        self.face_scanner_label = None
        self.scanner_status_label = None

    def deactivate_face_scanner(self):
        self.is_face_scanner_active = False

        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None

        # Stop the Tkinter loop update
        if self.video_frame_id:
            self.master.after_cancel(self.video_frame_id)
            self.video_frame_id = None

        self.destroy_face_scanner_window()

        # Update the toolbox button if it's open
        if self.toolbox_window and self.scanner_btn:
            self.scanner_btn.config(text="👁️ VISION SCANNER: OFF", style="TButton")

    def update_video_stream(self):
        if not self.is_face_scanner_active or not self.video_capture or not self.face_scanner_label:
            return

        ret, frame = self.video_capture.read()
        if ret:
            detection_status = "READY FOR QUERY"
            detection_color = self.success_green

            # 2. Convert to Tkinter PhotoImage
            # Convert BGR to RGB (OpenCV standard to PIL standard)
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(cv2image)

            # The label's size should match the frame size (640x480)
            self.webcam_image = ImageTk.PhotoImage(image=pil_image)

            # Update the Label in the dedicated window
            self.face_scanner_label.config(image=self.webcam_image)
            self.face_scanner_label.image = self.webcam_image  # Keep reference

            # Update the status label in the new window
            if self.scanner_status_label:
                self.scanner_status_label.config(text=f"◈ {detection_status} ◈", fg=detection_color)

        # Reschedule the update
        self.video_frame_id = self.master.after(self.VIDEO_STREAM_DELAY, self.update_video_stream)

    # --- ANIMATION AND VISUALIZATION METHODS ---

    def _safe_hex(self, value):
        clamped_value = max(0, min(255, int(value)))
        return f"{clamped_value:02x}"

    def initialize_particles(self):
        # Retrieve actual canvas size for initial placement
        self.canvas.update_idletasks()  # Ensure canvas dimensions are up-to-date
        canvas_width = self.canvas.winfo_width() or self.master.winfo_screenwidth()
        canvas_height = self.canvas.winfo_height() or self.master.winfo_screenheight()

        self.particle_systems = []  # Clear existing particles
        for i in range(self.PARTICLE_COUNT):  # Increased particle count
            particle = {'x': random.uniform(50, canvas_width - 50), 'y': random.uniform(50, canvas_height - 50),
                        'vx': random.uniform(-0.5, 0.5), 'vy': random.uniform(-0.5, 0.5),
                        'life': random.uniform(0.5, 1.0), 'max_life': random.uniform(0.5, 1.0),
                        'size': random.uniform(1.5, 4)}  # Slightly larger particles
            self.particle_systems.append(particle)

    def initialize_data_streams(self):
        """Initializes the background 'Data Rain' streams."""
        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width() or 1400
        canvas_height = self.canvas.winfo_height() or 1000

        self.data_streams = []
        for _ in range(self.DATA_STREAM_COUNT):
            stream = {
                'x': random.uniform(0, canvas_width),
                'y': random.uniform(0, canvas_height),
                'vy': random.uniform(2, 6),  # Fast downward motion
                'length': random.uniform(10, 30),  # Stream length
                'phase': random.uniform(0, 2 * math.pi)
            }
            self.data_streams.append(stream)

    def draw_data_streams(self, canvas_width, canvas_height):
        """Draws and updates the ambient 'Data Rain' animation."""
        base_color = self.neon_purple  # Use the secondary accent color

        r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)

        for stream in self.data_streams:
            stream['y'] += stream['vy']

            # Wrap around when stream goes off bottom
            if stream['y'] > canvas_height + stream['length']:
                stream['y'] = -stream['length']
                stream['x'] = random.uniform(0, canvas_width)

            # Intensity fades slightly for transparency, less so in light mode
            alpha_mult = 0.1 if self.is_dark_mode else 0.25
            alpha = alpha_mult + 0.1 * math.sin(self.animation_time * 0.5 + stream['phase'])  # Subtle pulse

            # --- COLOR SWITCH FIX ---
            if self.is_dark_mode:
                color = f"#{self._safe_hex(r * alpha)}{self._safe_hex(g * alpha)}{self._safe_hex(b * alpha)}"
            else:
                # Use the dark text color (ghost_white) with low opacity for high contrast against white background
                dark_r, dark_g, dark_b = int(self.ghost_white[1:3], 16), int(self.ghost_white[3:5], 16), int(
                    self.ghost_white[5:7], 16)
                # Keep opacity very low for the subtle rain effect
                color = f"#{self._safe_hex(dark_r * alpha * 0.2)}{self._safe_hex(dark_g * alpha * 0.2)}{self._safe_hex(dark_b * alpha * 0.2)}"
            # ------------------------

            # Draw the stream as a vertical line segment
            self.canvas.create_line(stream['x'], stream['y'],
                                    stream['x'], stream['y'] + stream['length'],
                                    fill=color,
                                    width=1)

    # --- NEW METHOD: DRAW DYNAMIC BACKGROUND WAVES ---
    def draw_dynamic_waves(self, canvas_width, canvas_height):
        """Draws slow-moving sinusoidal waves across the background."""

        # --- CRITICAL FIX: SKIP WAVES IN LIGHT MODE ---
        if not self.is_dark_mode:
            return
        # -----------------------------------------------

        # Use two distinct accent colors for visual depth
        colors = [self.electric_cyan, self.accent_deep_purple]
        base_alpha_mult = 0.05

        for i, color_hex in enumerate(colors):
            r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)

            # Sinusoidal parameters
            amplitude = 50 + i * 20
            frequency = 0.005 + i * 0.002
            speed = 0.02 + i * 0.005
            y_offset = (canvas_height // 2) + 100 * (i - 0.5)

            alpha_mult = base_alpha_mult

            # Dark mode: Use accent colors with low opacity
            alpha_fill_color = f"#{self._safe_hex(r * alpha_mult)}{self._safe_hex(g * alpha_mult)}{self._safe_hex(b * alpha_mult)}"
            line_alpha_mult = alpha_mult * 2
            alpha_line_color = f"#{self._safe_hex(r * line_alpha_mult)}{self._safe_hex(g * line_alpha_mult)}{self._safe_hex(b * line_alpha_mult)}"

            points = []
            for x in range(0, canvas_width, 10):
                # Calculate y based on sine wave, shifted by time for movement
                y = y_offset + amplitude * math.sin(x * frequency + self.animation_time * speed)
                points.append((x, y))

            # Draw the filled polygon area
            if points:
                # Add points to form a closed polygon that is filled and outlined
                poly_points = points + [(canvas_width, canvas_height), (0, canvas_height), points[0]]
                self.canvas.create_polygon(poly_points,
                                           fill=alpha_fill_color,
                                           outline="",
                                           smooth=True)

                # Draw the wave crest as a slightly more opaque line
                self.canvas.create_line(points,
                                        fill=alpha_line_color,
                                        width=2,
                                        smooth=True)

    # --- END NEW METHOD ---

    def initialize_neural_network(self):
        # Retrieve actual canvas size for initial placement
        self.canvas.update_idletasks()  # Ensure canvas dimensions are up-to-date
        canvas_width = self.canvas.winfo_width() or self.master.winfo_screenwidth()
        canvas_height = self.canvas.winfo_height() or self.master.winfo_screenheight()
        center_x, center_y = canvas_width // 2, canvas_height // 2

        self.neural_nodes = []  # Clear existing nodes
        self.neural_links = []  # Clear existing links

        # 10 main nodes randomly placed outside the main orb rings but within a reasonable radius
        node_count = 10
        min_r = 400
        max_r = min(canvas_width, canvas_height) // 2 - 100

        for i in range(node_count):
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(min_r, max_r)
            node = {'x': center_x + r * math.cos(angle),
                    'y': center_y + r * math.sin(angle),
                    'pulse': random.uniform(0, 2 * math.pi)}
            self.neural_nodes.append(node)

        # Connect nodes (simple neighbor/random connections)
        for i in range(node_count):
            # Connect to next node
            self.neural_links.append((i, (i + 1) % node_count, random.uniform(0, 2 * math.pi)))
            # Connect to a random distant node (avoiding self-connection or immediate neighbors)
            j = random.randint(0, node_count - 1)
            while j == i or j == (i + 1) % node_count or j == (i - 1 + node_count) % node_count:
                j = random.randint(0, node_count - 1)
            self.neural_links.append((i, j, random.uniform(0, 2 * math.pi)))

    def update_particles(self):
        # Use current canvas dimensions to wrap particles
        canvas_width = self.canvas.winfo_width() or 1400
        canvas_height = self.canvas.winfo_height() or 1000

        # Update core particles
        for particle in self.particle_systems:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['life'] -= 0.003
            # Wrap around boundaries
            if particle['x'] < 0: particle['x'] = canvas_width
            if particle['x'] > canvas_width: particle['x'] = 0
            if particle['y'] < 0: particle['y'] = canvas_height
            if particle['y'] > canvas_height: particle['y'] = 0
            if particle['life'] <= 0:
                # Reset particle to a new random position
                particle['x'] = random.uniform(50, canvas_width - 50)
                particle['y'] = random.uniform(50, canvas_height - 50)
                particle['life'] = particle['max_life']

    def draw_ai_visualization(self):
        self.canvas.delete("all")
        # Always get current canvas dimensions for drawing
        canvas_width = self.canvas.winfo_width() or 1400
        canvas_height = self.canvas.winfo_height() or 1000
        center_x, center_y = canvas_width // 2, canvas_height // 2

        # --- Draw Ambient Animations FIRST ---
        self.draw_dynamic_waves(canvas_width, canvas_height)  # Draw the slow, deep energy waves (conditional)
        self.draw_data_streams(canvas_width, canvas_height)  # Draw the fast data streams
        # ------------------------------------------

        self.draw_particles()
        self.draw_mouse_trail()
        self.draw_neural_network(center_x, center_y, canvas_width, canvas_height)
        self.draw_energy_rings(center_x, center_y)
        self.draw_ambient_glow(center_x, center_y)
        self.draw_central_orb(center_x, center_y, canvas_width, canvas_height)
        self.draw_energy_waves(center_x, center_y)
        if self.is_listening or self.is_speaking:
            self.draw_voice_visualization(center_x, center_y)

    def draw_particles(self):
        for particle in self.particle_systems:
            alpha = particle['life'] / particle['max_life']
            if alpha > 0:
                if self.is_dark_mode:
                    r, g, b = 0x4a, 0x4a, 0xff  # Default blue for dark mode
                    if self.is_listening:
                        r, g, b = 0x00, 0xff, 0x7f  # Success Green
                    elif self.is_speaking:
                        r, g, b = 0xff, 0x4a, 0x9e  # Plasma Pink
                else:  # Light mode (Using high contrast dark text color for particle core)
                    r, g, b = int(self.ghost_white[1:3], 16), int(self.ghost_white[3:5], 16), int(
                        self.ghost_white[5:7], 16)
                    if self.is_listening:
                        r, g, b = int(self.success_green[1:3], 16), int(self.success_green[3:5], 16), int(
                            self.success_green[5:7], 16)
                    elif self.is_speaking:
                        r, g, b = int(self.plasma_pink[1:3], 16), int(self.plasma_pink[3:5], 16), int(
                            self.plasma_pink[5:7], 16)

                # Particle layer 1 (Core)
                color_core = f"#{self._safe_hex(r * alpha)}{self._safe_hex(g * alpha)}{self._safe_hex(b * alpha)}"
                self.canvas.create_oval(particle['x'] - particle['size'], particle['y'] - particle['size'],
                                        particle['x'] + particle['size'], particle['y'] + particle['size'],
                                        fill=color_core, outline="")

                # Particle layer 2 (Glow)
                glow_size = particle['size'] + 1
                color_glow = f"#{self._safe_hex(r * alpha * 0.3)}{self._safe_hex(g * alpha * 0.3)}{self._safe_hex(b * alpha * 0.3)}"
                self.canvas.create_oval(particle['x'] - glow_size, particle['y'] - glow_size,
                                        particle['x'] + glow_size, particle['y'] + glow_size,
                                        fill=color_glow, outline="")

    def draw_mouse_trail(self):
        if not self.mouse_trail: return

        for i, (x, y) in enumerate(self.mouse_trail):
            # Fades as it gets older
            alpha = (i + 1) / len(self.mouse_trail) * 0.4
            size = 1 + (i + 1) / len(self.mouse_trail) * 2

            r, g, b = int(self.accent_gold[1:3], 16), int(self.accent_gold[3:5], 16), int(self.accent_gold[5:7], 16)
            color = f"#{self._safe_hex(r * alpha)}{self._safe_hex(g * alpha)}{self._safe_hex(b * alpha)}"

            self.canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")

    def draw_neural_network(self, center_x, center_y, canvas_width, canvas_height):
        # Update node positions based on current canvas size
        node_count = len(self.neural_nodes)
        min_r = 400
        max_r = min(canvas_width, canvas_height) // 2 - 100

        for i, node in enumerate(self.neural_nodes):
            angle = (i / node_count) * 2 * math.pi + self.animation_time * 0.005  # Slight rotation
            r_offset = 100 * math.sin(self.animation_time * 0.02 + i)  # Dynamic radius
            r = min_r + (max_r - min_r) * ((i + self.animation_time * 0.01) % node_count / node_count)

            node['x'] = center_x + (r + r_offset) * math.cos(angle)
            node['y'] = center_y + (r + r_offset) * math.sin(angle)

        # 1. Links (Fading lines)
        for i, j, phase in self.neural_links:
            node1 = self.neural_nodes[i]
            node2 = self.neural_nodes[j]
            # Link intensity pulses slowly
            intensity = (math.sin(self.animation_time * 0.01 + phase) + 1) / 2

            # Use deep purple for links
            r, g, b = int(self.accent_deep_purple[1:3], 16), int(self.accent_deep_purple[3:5], 16), int(
                self.accent_deep_purple[5:7], 16)

            # Adjust alpha for visibility in light mode
            alpha_multiplier = 0.5 if self.is_dark_mode else 0.4  # Slightly higher for light mode to show against white
            color = f"#{self._safe_hex(r * intensity * alpha_multiplier)}{self._safe_hex(g * intensity * alpha_multiplier)}{self._safe_hex(b * intensity * alpha_multiplier)}"

            self.canvas.create_line(node1['x'], node1['y'], node2['x'], node2['y'], fill=color, width=1.5)

        # 2. Nodes (Pulsing dots)
        for node in self.neural_nodes:
            # Node size/brightness pulses faster
            pulse_factor = 1 + 0.5 * math.sin(self.animation_time * 0.1 + node['pulse'])
            node_size = 4 * pulse_factor

            # Use electric cyan for nodes
            r, g, b = int(self.electric_cyan[1:3], 16), int(self.electric_cyan[3:5], 16), int(self.electric_cyan[5:7],
                                                                                              16)

            # Adjust alpha for visibility in light mode
            alpha_multiplier = 0.8 if self.is_dark_mode else 0.8  # Keep high contrast
            color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

            self.canvas.create_oval(node['x'] - node_size, node['y'] - node_size,
                                    node['x'] + node_size, node['y'] + node_size,
                                    fill=color, outline="")

    def draw_energy_rings(self, center_x, center_y):
        # 5 Rings with new segment counts
        ring_configs = [
            {'radius': 350, 'width': 1, 'segments': 72},
            {'radius': 300, 'width': 3, 'segments': 60},
            {'radius': 250, 'width': 2, 'segments': 84},
            {'radius': 200, 'width': 4, 'segments': 48},
            {'radius': 150, 'width': 2, 'segments': 36}
        ]

        colors = [self.electric_cyan, self.neon_purple, self.plasma_pink, self.primary_blue, self.accent_gold]

        for i in range(len(ring_configs)):
            config = ring_configs[i]
            rotation = self.ring_rotations[i]
            radius = config['radius']
            segments = config['segments']
            color = colors[i % len(colors)]

            # Adjust color for light mode for better visibility
            if not self.is_dark_mode:
                # In light mode, rings should be less transparent to be visible
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                color = f"#{self._safe_hex(r * 0.9)}{self._safe_hex(g * 0.9)}{self._safe_hex(b * 0.9)}"  # high opacity

            for segment in range(segments):
                angle = (segment / segments) * 2 * math.pi + rotation
                next_angle = ((segment + 1) / segments) * 2 * math.pi + rotation

                # Dynamic intensity based on position and time
                intensity = (math.sin(angle * 5 + self.animation_time * 0.1) + 1) * 0.5

                if intensity > 0.3:
                    x1 = center_x + radius * math.cos(angle)
                    y1 = center_y + radius * math.sin(angle)
                    x2 = center_x + radius * math.cos(next_angle)
                    y2 = center_y + radius * math.sin(next_angle)

                    self.canvas.create_line(x1, y1, x2, y2, fill=color, width=config['width'], smooth=True)

    def draw_ambient_glow(self, center_x, center_y):
        """Draws a subtle, pulsing ambient glow around the orb area."""

        # Breathing effect applied to the ambient pulse
        breathing_scale = (math.sin(self.animation_time * 0.05) * 0.05) + 1

        if self.is_listening:
            base_color = self.success_green
        elif self.is_speaking:
            base_color = self.plasma_pink
        else:
            base_color = self.primary_blue

        for i in range(3):
            # Pulse outwards, resetting every 100 animation steps
            pulse_time = (self.animation_time * 1 + i * 20) % 100

            # Radius expands from 100 to 500
            radius = (100 + pulse_time * 4) * breathing_scale

            # Opacity fades out from 0.4 to 0 as radius increases
            alpha = (1 - pulse_time / 100) * 0.4

            if alpha > 0.05:
                r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)

                # Adjust alpha for visibility in light mode
                alpha_multiplier = alpha if self.is_dark_mode else alpha * 0.5  # Slightly higher opacity on light
                color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

                # Draw outer glow circle
                self.canvas.create_oval(center_x - radius, center_y - radius,
                                        center_x + radius, center_y + radius,
                                        outline=color, width=1, fill="")

    def draw_central_orb(self, center_x, center_y, canvas_width, canvas_height):
        """Draw the central AI orb with breathing, glow, and eyes/blinking."""

        # --- Breathing Effect: Modifies size and glow intensity of the whole orb ---
        breathing_factor = 1 + 0.04 * math.sin(self.animation_time * 0.05)

        # --- State-based Base Color Tinting ---
        if self.is_listening:
            base_color = self.success_green
            glow_color = self.success_green
        elif self.is_speaking:
            base_color = self.plasma_pink
            glow_color = self.plasma_pink
        else:
            base_color = self.primary_blue
            glow_color = self.electric_cyan

        # 1. Outer Multi-layer Glow (3 layers of depth)
        base_glow = self.BASE_GLOW_RADIUS * breathing_factor
        glow_intensity = 0.5 + 0.5 * math.sin(self.orb_glow * 2)

        r, g, b = int(glow_color[1:3], 16), int(glow_color[3:5], 16), int(glow_color[5:7], 16)

        for i in range(1, 4):  # Three layers (i=1, 2, 3)
            layer_alpha = glow_intensity * (4 - i) * 0.1

            # Adjust alpha for visibility in light mode
            alpha_multiplier = layer_alpha if self.is_dark_mode else layer_alpha * 0.5
            color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

            radius = base_glow + i * 15
            self.canvas.create_oval(center_x - radius, center_y - radius,
                                    center_x + radius, center_y + radius,
                                    fill=color, outline="")

        # 2. Main Orb (Inner gradient 30 steps)
        orb_radius = self.ORB_RADIUS * breathing_factor
        gradient_steps = 30

        for i in range(gradient_steps, 0, -1):
            radius = orb_radius * (i / gradient_steps)
            intensity = (i / gradient_steps) * 0.8  # Fades out to the center

            # Deep space center
            base_r, base_g, base_b = int(self.bg_dark_void[1:3], 16), int(self.bg_dark_void[3:5], 16), int(
                self.bg_dark_void[5:7], 16)

            color = f"#{self._safe_hex(base_r * intensity)}{self._safe_hex(base_g * intensity)}{self._safe_hex(base_b * intensity)}"

            self.canvas.create_oval(center_x - radius, center_y - radius,
                                    center_x + radius, center_y + radius,
                                    fill=color, outline="")

        # 3. Eyes with Blinking and Tracking
        eye_y_offset = -10
        eye_separation = 20
        eye_radius = 8
        eye_color = self.energy_white
        # CRITICAL LIGHT THEME FIX: Pupil color must be dark charcoal in light mode
        pupil_color = self.bg_deep_space if self.is_dark_mode else self.ghost_white

        # Blinking Logic
        if self.is_blinking:
            eye_height = 1
            current_eye_color = base_color
        else:
            eye_height = eye_radius
            current_eye_color = eye_color

        # Pupil tracking: Move pupils slightly towards the mouse
        dx = (self.mouse_pos[0] - center_x) / (canvas_width / 2) * 2
        dy = (self.mouse_pos[1] - center_y) / (canvas_height / 2) * 2

        pupil_movement_x = max(-2, min(2, dx))
        pupil_movement_y = max(-2, min(2, dy))

        # Draw eyes (ovals clamped by the eye_height for blinking)
        for side in [-1, 1]:
            eye_left = center_x + side * eye_separation - eye_radius
            eye_right = center_x + side * eye_separation + eye_radius

            # Full eye
            self.canvas.create_oval(eye_left, center_y + eye_y_offset - eye_radius,
                                    eye_right, center_y + eye_y_offset + eye_radius,
                                    fill=current_eye_color, outline="")

            # Blinking lid (covers top/bottom if height is small)
            if self.is_blinking:
                self.canvas.create_rectangle(eye_left, center_y + eye_y_offset - eye_radius,
                                             eye_right, center_y + eye_y_offset + eye_radius,
                                             fill=self.bg_deep_space, outline="")

        # Draw Pupils (only if not fully blinking)
        if not self.is_blinking:
            pupil_radius = 3
            for side in [-1, 1]:
                pupil_center_x = center_x + side * eye_separation + pupil_movement_x
                pupil_center_y = center_y + eye_y_offset + pupil_movement_y

                self.canvas.create_oval(pupil_center_x - pupil_radius, pupil_center_y - pupil_radius,
                                        pupil_center_x + pupil_radius, pupil_center_y + pupil_radius,
                                        fill=pupil_color, outline="")

    def draw_energy_waves(self, center_x, center_y):
        if self.is_active_state:
            # Use deep purple accent for waves
            base_color = self.accent_deep_purple

            for i in range(3):
                wave_radius = 100 + i * 50 + (self.animation_time * 2) % 100
                wave_intensity = 1 - ((self.animation_time * 2 + i * 30) % 100) / 100
                if wave_intensity > 0:
                    r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)

                    # Adjust alpha for visibility in light mode
                    alpha_multiplier = wave_intensity if self.is_dark_mode else wave_intensity * 0.4
                    color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

                    self.canvas.create_oval(center_x - wave_radius, center_y - wave_radius, center_x + wave_radius,
                                            center_y + wave_radius, outline=color, width=2, fill="")

    def draw_voice_visualization(self, center_x, center_y):
        num_bars = self.VOICE_BARS
        base_radius = 120

        # Use a gradient transition for color
        start_color = self.success_green if self.is_listening else self.electric_cyan
        end_color = self.neon_purple

        start_r, start_g, start_b = int(start_color[1:3], 16), int(start_color[3:5], 16), int(start_color[5:7], 16)
        end_r, end_g, end_b = int(end_color[1:3], 16), int(end_color[3:5], 16), int(end_color[5:7], 16)

        for i in range(num_bars):
            angle = (i / num_bars) * 2 * math.pi

            # Smoother height change - Dynamic height based on phase and state
            bar_height = 20 + 30 * math.sin(self.animation_time * 0.2 + i * 0.5)
            # Add randomized amplitude if speaking for a more 'responsive' look
            if self.is_speaking:
                bar_height += 40 * random.random() + 10  # More pronounced effect
            elif self.is_listening:
                bar_height += 15 * math.sin(self.animation_time * 0.3 + i * 0.2) + 5  # Subtle listening ripple

            x1 = center_x + base_radius * math.cos(angle)
            y1 = center_y + base_radius * math.sin(angle)
            x2 = center_x + (base_radius + bar_height) * math.cos(angle)
            y2 = center_y + (base_radius + bar_height) * math.sin(angle)

            # Gradient color based on bar index
            ratio = i / num_bars
            r = int(start_r + (end_r - start_r) * ratio)
            g = int(start_g + (end_g - start_g) * ratio)
            b = int(start_b + (end_b - start_b) * ratio)

            # Adjust alpha for visibility in light mode
            alpha_multiplier = 1.0 if self.is_dark_mode else 0.8  # Higher opacity for sound elements in light mode
            color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3)

    def on_mouse_move(self, event):
        self.mouse_pos = (event.x, event.y)

    def start_master_animation(self):
        def animate():
            self.animation_time += 1
            self.pulse_phase += 0.1
            self.orb_glow += 0.1

            # Blinking logic
            if not self.is_blinking:
                self.blink_timer += 1
                if self.blink_timer > random.randint(150, 400):
                    self.is_blinking = True
                    self.master.after(80, self.end_blink)
                    self.blink_timer = 0

            # Ring rotation
            for i in range(len(self.ring_rotations)):
                self.ring_rotations[i] += self.ring_speeds[i] * 0.02

            # Mouse Trail Management
            if self.mouse_pos != (0, 0):
                self.mouse_trail.append(self.mouse_pos)

            # Limit the trail length to create a fading effect
            trail_max_length = 15
            if len(self.mouse_trail) > trail_max_length:
                self.mouse_trail.pop(0)  # Remove the oldest point
            # End Mouse Trail Management

            self.update_particles()
            self.is_active_state = self.is_listening or self.is_speaking or self.awaiting_code_followup
            self.draw_ai_visualization()
            self.master.after(self.FRAME_RATE_MS, animate)

        animate()

    def end_blink(self):
        self.is_blinking = False

    def on_canvas_click(self, event):
        if event.widget == self.canvas:
            x, y = event.x, event.y
            # Enhanced click ripples: 15 steps with cyan -> purple transition
            for i in range(15):
                self.master.after(i * 30, lambda i=i: self.create_click_effect(x, y, i))

    def create_click_effect(self, x, y, step):
        radius = step * 10
        alpha = 1 - (step / 15)

        # Color transition (Cyan -> Purple)
        r1, g1, b1 = int(self.electric_cyan[1:3], 16), int(self.electric_cyan[3:5], 16), int(self.electric_cyan[5:7],
                                                                                             16)
        r2, g2, b2 = int(self.neon_purple[1:3], 16), int(self.neon_purple[3:5], 16), int(self.neon_purple[5:7], 16)

        ratio = step / 15

        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)

        if alpha > 0:
            # Adjust alpha for visibility in light mode
            alpha_multiplier = alpha if self.is_dark_mode else alpha * 0.5
            color = f"#{self._safe_hex(r * alpha_multiplier)}{self._safe_hex(g * alpha_multiplier)}{self._safe_hex(b * alpha_multiplier)}"

            effect_id = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=2,
                                                fill="")
            if step >= 14:
                self.master.after(100, lambda: self.canvas.delete(effect_id))

    def boot_sequence(self):
        boot_messages = ["Ek min ruk bhai"]

        def show_boot_message(index):
            if index < len(boot_messages):
                self.status_label.config(text=boot_messages[index])
                self.display_message(boot_messages[index], 'system')
                self.master.after(1200, lambda: show_boot_message(index + 1))
            else:
                self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA")
                # Check if Gemini is configured before saying the greeting
                greeting = "Hi, main aapke command ke liye ready hoon. Spacebar dabao aur ek command bolo"
                if not self.gemini_model:
                    greeting += " (Note: Gemini API key is missing. AI features are disabled.)"
                self.say(greeting)

        show_boot_message(0)

    def toggle_fullscreen(self, event):
        try:
            self.master.attributes('-fullscreen', not self.master.attributes('-fullscreen'))
        except:
            pass

    def toggle_theme(self):
        """Switches between dark and light themes."""
        new_theme = 'light' if self.is_dark_mode else 'dark'
        self.apply_theme(new_theme)
        self.say(f"Switched to {new_theme} mode.")

    # --- CORE I/O AND COMMAND PROCESSING METHODS ---

    def _update_response_button_states(self):
        """Updates the state of buttons in the modal response window if it exists."""
        if self.response_window and self.response_window.winfo_exists() and self.listen_btn and self.stop_btn and self.mute_btn:
            try:
                # Use TTK state management
                if self.is_listening:
                    self.listen_btn.state(['disabled'])
                    self.stop_btn.state(['!disabled'])
                else:
                    self.listen_btn.state(['!disabled'])
                    self.stop_btn.state(['disabled'])

                if self.is_speaking:
                    self.mute_btn.state(['!disabled'])
                else:
                    self.mute_btn.state(['disabled'])

            except Exception:
                pass

    def say(self, text):
        """TTS with enhanced visual feedback and control button updates"""
        if not text: return
        self.is_speaking = True
        self.display_message(f"Speaking: {text}", 'venom')
        self._update_response_button_states()

        # CRITICAL FIX: Pass kill_only=True to prevent speaking state from ending prematurely.
        self.stop_speaking_gui(kill_only=True)

        try:
            if platform.system() == "Darwin":
                self.say_process = subprocess.Popen(['say', text])
            elif platform.system() == "Windows":
                # Windows TTS is complex, often requiring external libraries.
                # For this example, we'll disable it on Windows if using 'say'.
                self.say_process = None
                self.is_speaking = False
            else:
                self.say_process = None
                self.is_speaking = False

            if self.say_process:
                self.master.after(100, self._check_say_process)
            else:
                # If 'say' isn't available, report and stop speaking state
                self.display_message("TTS not fully supported on this OS with the current configuration.", 'warning')
                self.is_speaking = False
                self._update_response_button_states()

        except Exception as e:
            self.display_message(f"TTS Error: {e}", 'error')
            self.is_speaking = False

    def _check_say_process(self):
        # FIX: Check if say_process is None (for non-macOS systems)
        if self.say_process is None:
            self.is_speaking = False
            self._update_response_button_states()
            return

        if self.say_process.poll() is None:
            self.master.after(100, self._check_say_process)
        else:
            self.is_speaking = False
            self._update_response_button_states()
            self.say_process = None

    def stop_speaking_gui(self, kill_only=False):
        """Stops the current speaking process and updates the GUI."""
        if self.say_process and self.say_process.poll() is None:
            try:
                self.say_process.terminate()
                time.sleep(0.05)
            except Exception:
                pass
            finally:
                self.is_speaking = False
                self.say_process = None

        if not kill_only:
            self._update_response_button_states()

    def start_listening_gui(self):
        """Starts the listening thread and updates the GUI."""
        if self.is_listening: return

        self.is_listening = True
        self.status_label.config(text="◉ LISTENING FOR COMMANDS")
        self._update_response_button_states()

        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread = None

        self.listening_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listening_thread.start()

    def stop_listening_gui(self):
        """Stops the listening state and updates the GUI."""
        if not self.is_listening: return

        self.is_listening = False
        self.status_label.config(text="◉ VENOM A.I READY")
        self._update_response_button_states()

    def takeCommand(self):
        """Speech recognition - Runs in a separate thread"""
        r = self.recognizer
        with sr.Microphone() as source:
            self.master.after(0, lambda: self.display_message("Listening for voice input...", 'system'))
            r.pause_threshold = 1
            try:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=3, phrase_time_limit=8)
            except sr.WaitTimeoutError:
                # FIX: Report timeout explicitly
                self.master.after(0,
                                  lambda: self.display_message("Listening timed out. No speech detected.", 'warning'))
                return ""
            except Exception as e:
                self.master.after(0, lambda: self.display_message(f"Microphone error: {e}", 'error'))
                return ""

        try:
            self.master.after(0, lambda: self.display_message("Processing speech...", 'system'))
            query = r.recognize_google(audio, language="en-in")
            self.master.after(0, lambda: self.display_message(f"Recognized: {query}", 'user'))
            return query
        except sr.UnknownValueError:
            self.master.after(0, lambda: self.display_message("Could not understand audio", 'warning'))
            return ""
        except sr.RequestError:
            self.master.after(0, lambda: self.display_message("Speech service error (Check internet/API key)", 'error'))
            return ""

    def listen_loop(self):
        """Main listening loop (runs in a thread) - Simplified to one-shot capture."""

        query = self.takeCommand()

        if query:
            # Store the query before processing
            self.last_query = query.lower()
            threading.Thread(target=self.process_command, args=(self.last_query,), daemon=True).start()

        self.master.after(0, self.stop_listening_gui)

    def _safe_web_open(self, url, name):
        """Attempts to open a clean URL using the standard webbrowser module."""
        # Sanitize and extract URL
        clean_url_match = re.search(r'\[(.*?)\]\((.*?)\)', url)
        if clean_url_match:
            clean_url = clean_url_match.group(2).strip()
        else:
            clean_url = url.split('(')[-1].strip(')')

        if not clean_url.startswith(('http://', 'https://')):
            clean_url = 'https://' + clean_url

        try:
            if webbrowser.open_new_tab(clean_url):
                return True
            else:
                raise Exception("Webbrowser failed to launch.")

        except Exception as e:
            if os.name == 'posix':
                try:
                    subprocess.run(['open', clean_url], check=True, timeout=5)
                    return True
                except Exception:
                    pass
            elif os.name == 'nt':
                try:
                    subprocess.run(['start', clean_url], shell=True, check=True, timeout=5)
                    return True
                except Exception:
                    pass

            final_error_msg = (
                f"FATAL ERROR: Failed to open web page for '{name}'.\n"
                f"URL: {clean_url}\nError: {e}"
            )
            # Log the deep failure, and return False for the caller to handle feedback.
            self.master.after(0, lambda: self.display_message(f"Web Open FAILED for {name}: {e}", 'error'))
            self.master.after(0, lambda: self.create_response_interface(f"SYSTEM:\n\n{final_error_msg}"))
            return False

    def process_typed_command(self):
        """Processes command from the modal toolbox input field (No longer auto-destroys toolbox)."""
        if not self.input_entry: return
        command = self.input_entry.get().strip()

        if command:
            self.display_message(f"Manual input (Toolbox): {command}", 'user')
            # Open the response window to provide context before thread starts
            self.master.after(0, lambda: self.create_response_interface(f"USER INPUT:\n\n{command}"))

            self.input_entry.delete(0, tk.END)

            # Store the query before processing
            self.last_query = command.lower()
            threading.Thread(target=self.process_command, args=(self.last_query,), daemon=True).start()

    def process_response_typed_command(self):
        """NEW: Processes command from the response window input field."""
        if not self.response_entry: return
        command = self.response_entry.get().strip()

        if command:
            self.display_message(f"Manual input (Response Window): {command}", 'user')

            # Close and reopen the response window to update with the new command context
            # NOTE: We keep the old response in the buffer for continuity
            old_response = "Context switch..."
            try:
                # Grab content from the response window's text widget before destroying
                text_widget = next(c for c in self.response_window.winfo_children()[0].winfo_children() if
                                   isinstance(c, scrolledtext.ScrolledText))
                old_response = text_widget.get("1.0", tk.END).strip()
            except Exception:
                pass

            self.destroy_response_window()
            # Open new response interface with the new command context added to the old response
            self.master.after(100,
                              lambda: self.create_response_interface(f"{old_response}\n\nUSER FOLLOW-UP:\n\n{command}"))

            # Store the query before processing
            self.last_query = command.lower()
            threading.Thread(target=self.process_command, args=(self.last_query,), daemon=True).start()

    def process_typed_command_event(self, event):
        """Handles <Return> key in either input field (Toolbox or Response Window)."""
        if event.widget == self.input_entry:
            self.process_typed_command()
        elif event.widget == self.response_entry:
            self.process_response_typed_command()

    def take_screenshot_command(self):
        """
        Takes a full-screen screenshot using the macOS 'screencapture' utility
        and saves it to the user's Desktop with a timestamp.
        """
        if platform.system() != "Darwin":
            self.master.after(0, lambda: self.display_message("Screenshot command is macOS-specific and cannot run.",
                                                              'error'))
            self.master.after(0, lambda: self.say("Screenshot command is not supported on this operating system."))
            return

        # Determine the desktop path for saving the file
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

        # Create a unique filename using a timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"Venom_Screenshot_{timestamp}.png"
        file_path = os.path.join(desktop_path, filename)

        self.master.after(0, lambda: self.status_label.config(text="◈ CAPTURING SCREEN ◈"))
        self.master.after(0, lambda: self.display_message("Executing 'screencapture'...", 'system'))

        try:
            # Command to capture the full screen and save to the specified path
            subprocess.run(['screencapture', file_path], check=True, timeout=10)

            # Provide success feedback
            self.master.after(0, lambda: self.create_response_interface(
                f"SYSTEM:\n\nScreenshot captured successfully.\nFile saved to: {filename} on Desktop."
            ))
            self.master.after(0, lambda: self.say(f"Screenshot taken and saved as {filename}"))

        except subprocess.CalledProcessError as e:
            error_msg = f"Screenshot error: Command failed with status {e.returncode}. (Check system permissions for Terminal/Python)."
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
            self.master.after(0, lambda: self.say(
                "Failed to take screenshot. Check system security and privacy settings."))
        except Exception as e:
            error_msg = f"Screenshot error: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
            self.master.after(0, lambda: self.say("An unexpected error occurred while taking the screenshot."))
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    def process_command(self, query):
        """Handles user commands, routing them based on current assistant state."""

        def do_on_main(func, *args):
            self.master.after(0, lambda: func(*args))

        if not query: return

        if "change theme" in query or "toggle theme" in query or "switch to light" in query or "switch to dark" in query:
            do_on_main(self.toggle_theme)
            return

        # --- NEW: LOAD PROJECT COMMAND ---
        if "load project" in query or "reopen project" in query or "continue editing" in query:
            do_on_main(self.say, "Opening file dialogue to select your project folder.")
            do_on_main(self.select_and_load_project)
            return
        # --- END NEW LOGIC ---

        # --- VISION QUERY COMMANDS (CORRECTED TRIGGERS) ---
        is_vision_query = any(trigger in query for trigger in
                              ["debug this error", "translate the text", "find the price of this",
                               "what is this object", "identify this", "scan object"])

        if "start vision scanner" in query or "turn on camera" in query:
            do_on_main(self.activate_face_scanner)
            return

        if "stop vision scanner" in query or "turn off camera" in query:
            do_on_main(self.deactivate_face_scanner)
            return

        if is_vision_query:
            if not self.is_face_scanner_active:
                do_on_main(self.say, "Please activate the vision scanner window first to use that feature.")
                return

            # All vision tasks route to the same core logic
            threading.Thread(target=self.query_gemini_vision, daemon=True).start()
            return
        # --- END VISION QUERY COMMANDS ---

        # --- CRITICAL CODE EDITING LOGIC ---
        if self.awaiting_code_followup:
            if "finished" in query or "exit code mode" in query or "stop editing" in query:
                # FIX: Explicitly clear state and confirm exit
                do_on_main(self.say, "Exiting code editing mode. Context cleared.")
                self.awaiting_code_followup = False
                self.current_project_path = None
                self.gemini_code_chat = None
                return

            do_on_main(self.display_message, "Code modification requested. Sending to editor model...", 'system')
            threading.Thread(target=self.process_code_update_followup, args=(query,), daemon=True).start()
            return
        # --- END CODE EDITING LOGIC ---

        if "toolbox" in query or "show controls" in query or "open keyboard" in query:
            do_on_main(self.say, "Opening system control panel.")
            do_on_main(self.create_toolbox_interface)
            return

        if "stop listening" in query or "cancel listening" in query:
            do_on_main(self.say, "Listening terminated.")
            do_on_main(self.stop_listening_gui)
            return

        if "save chat" in query or "save conversation" in query:
            self.save_chat_to_file()
            return

        # --- PROJECT DOCUMENTATION FEATURE ---
        if "summarize project" in query or "document project" in query or "create readme" in query:
            threading.Thread(target=self.summarize_current_project, daemon=True).start()
            return
        # --- END PROJECT DOCUMENTATION FEATURE ---

        # --------------------------------------------------------------------------------
        # APP LAUNCHER (SPEAKS CONFIRMATION)
        # --------------------------------------------------------------------------------
        apps = {
            "safari": "Safari",
            "vscode": "Visual Studio Code",
            "code": "code",
            "chrome": "Google Chrome",
            "browser": "browser",
            "terminal": "Terminal",
            "whatsapp": "WhatsApp"
        }
        for key, name in apps.items():
            if any(p in query for p in [f"open {key}", f"launch {key}", f"start {key}"]) and "search" not in query:

                command_successful = False
                if os.name == 'posix':
                    try:
                        if name in ["code", "browser"]:
                            subprocess.run(["open", name] if name == "browser" else [name], check=True)
                        else:
                            subprocess.run(["open", "-a", name], check=True)
                        command_successful = True
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        pass

                elif os.name == 'nt':
                    try:
                        subprocess.run(["start", name], shell=True, check=True)
                        command_successful = True
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        pass

                if command_successful:
                    # FIX: Speak the command result
                    do_on_main(self.say, f"Opening {name}")
                    do_on_main(self.create_response_interface, f"LAUNCHED: {name}")
                else:
                    do_on_main(self.say, f"Could not launch {name}. Please check the installation path on your system.")
                    do_on_main(self.create_response_interface, f"ERROR: Could not launch {name}.")
                return
        # --------------------------------------------------------------------------------

        # --------------------------------------------------------------------------------
        # WEBSITE LAUNCHER (SPEAKS CONFIRMATION)
        # --------------------------------------------------------------------------------
        sites = [
            ["youtube", "[https://www.youtube.com](https://www.youtube.com)"],
            ["wikipedia", "[https://www.wikipedia.org](https://www.wikipedia.org)"],
            ["google", "[https://www.google.com](https://www.google.com)"],
            ["github", "[https://www.github.com](https://www.github.com)"],
            ["stackoverflow", "[https://stackoverflow.com](https://stackoverflow.com)"]
        ]
        for site, url in sites:
            # Check for direct site visit command
            if any(p in query for p in [f"open {site}", f"go to {site}", f"visit {site}"]) and "search" not in query:
                # FIX: Speak the command result BEFORE opening the web page
                do_on_main(self.say, f"Opening {site}")
                do_on_main(self.create_response_interface, f"OPENING: {site}")
                if not self._safe_web_open(url, site):
                    do_on_main(self.say, f"Failed to open {site}. Check the system log for details.")
                return
        # --------------------------------------------------------------------------------

        # --------------------------------------------------------------------------------
        # SEARCH LAUNCHER (SPEAKS CONFIRMATION & ROBUST PARSING)
        # --------------------------------------------------------------------------------
        search_triggers = ["search for", "search", "look up", "find", "query"]
        trigger = next((t for t in search_triggers if t in query), None)

        if trigger:
            search_sites = {
                "youtube": "[https://www.youtube.com/results?search_query=](https://www.youtube.com/results?search_query=)",
                "wikipedia": "[https://en.wikipedia.org/w/index.php?search=](https://en.wikipedia.org/w/index.php?search=)",
                "github": "[https://github.com/search?q=](https://github.com/search?q=)",
                "stackoverflow": "[https://stackoverflow.com/search?q=](https://stackoverflow.com/search?q=)"
            }

            search_term = ""
            # FIX: Robustly extract the search term based on the trigger word
            try:
                # Find the index of the trigger word, and everything after it is the term
                term_start_index = query.find(trigger) + len(trigger)
                search_term = query[term_start_index:].strip()
                # Clean up residual words like 'on google'
                search_term = re.sub(r' on (google|youtube|wikipedia|github|stackoverflow)$', '', search_term,
                                     flags=re.IGNORECASE).strip()
            except Exception:
                pass  # search_term remains empty or partially correct

            # Determine the target site (default to Google)
            site_name = "Google"
            base_url = "[https://www.google.com/search?q=](https://www.google.com/search?q=)"

            for site_key, site_url in search_sites.items():
                if site_key in query:
                    site_name = site_key.capitalize()
                    base_url = site_url
                    break

            if search_term:
                full_url = base_url + urllib.parse.quote_plus(search_term)

                # FIX: Speak the command result
                do_on_main(self.say, f"Searching for {search_term} on {site_name}")
                do_on_main(self.create_response_interface, f"SEARCHING: {search_term} on {site_name}")

                if not self._safe_web_open(full_url, site_name):
                    do_on_main(self.say, f"Failed to open the search page for {site_name}.")
            else:
                do_on_main(self.say, "What exactly would you like me to search for?")
            return
        # --------------------------------------------------------------------------------

        code_triggers = ["code me", "write a script", "create a program", "write code", "build me", "develop",
                         "generate code", "make a", "create a website", "build a site"]
        trigger = next((t for t in code_triggers if t in query), None)
        if trigger:
            if not self.gemini_model:
                do_on_main(self.say, "Gemini AI is not configured. Cannot generate code.")
                return

            request = query.split(trigger, 1)[1].strip()
            if request:
                do_on_main(self.create_response_interface,
                           f"CODE REQUEST: {request}\n\nProject creation started in the background.")
                # NOTE: say() call for code generation is handled inside create_code_file/followup
                threading.Thread(target=self.create_code_file, args=(request,), daemon=True).start()
            else:
                do_on_main(self.say, "What would you like me to code?")
            return

        if "time" in query or "clock" in query:
            now = datetime.datetime.now()
            time_str, date_str = now.strftime('%I:%M %p'), now.strftime('%A, %B %d, %Y')
            do_on_main(self.say, f"Current time is {time_str}, {date_str}")
            do_on_main(self.create_response_interface, f"CURRENT TIME:\n\n{time_str} - {date_str}")
            return

        # --- NEW SCREENSHOT FEATURE FOR MACOS ---
        if "take a screenshot" in query or "capture my screen" in query or "screenshot" == query:
            do_on_main(self.create_response_interface, f"SCREENSHOT: Capturing full screen...")
            threading.Thread(target=self.take_screenshot_command, daemon=True).start()
            return
        # --- END NEW FEATURE ---

        if any(cmd in query for cmd in ["ram ram", "quit", "bye", "shutdown", "terminate", "goodbye"]):
            do_on_main(self.say, "Initiating shutdown sequence. Goodbye.")
            self.master.after(2000, self.on_closing)
            return

        # Default fallback to Gemini chat
        threading.Thread(target=self.query_gemini, args=(query,), daemon=True).start()

    # --- UPDATED: FINE-TUNING DATA LOGGING FEATURE ---

    def _log_fine_tuning_data(self, interaction_type: str, user_prompt: str, assistant_response: str,
                              image_path: str = None):
        """
        Saves a single prompt-response pair to a JSONL file inside the project folder
        (Current Working Directory of PyCharm).
        """

        # 1. Define the log folder path relative to the current working directory (project root)
        # os.getcwd() points to the directory from which the script was executed (PyCharm project root)
        log_dir = os.path.join(os.getcwd(), "venom_fine_tune_data")

        try:
            # Attempt to create directory
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            self.master.after(0, lambda: self.display_message(
                f"LOG DIR FAILED: Cannot create folder in project root. Error: {e}", 'error'))
            return  # Stop logging if directory fails

        # Monthly filename: Venom_FT_Log_202510.jsonl
        filename = datetime.datetime.now().strftime("Venom_FT_Log_%Y%m.jsonl")
        log_path = os.path.join(log_dir, filename)

        # 2. Structure the data dictionary
        data_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": interaction_type,
            "instruction": user_prompt.strip(),
            "response": assistant_response.strip(),
            "image_context": image_path if image_path else None
        }

        # 3. Write the JSON object to the file, ensuring it's on a new line (JSONL format)
        try:
            json_line = json.dumps(data_entry, ensure_ascii=False) + '\n'

            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json_line)

            # Success message (thread-safe call)
            self.master.after(0, lambda: self.display_message(f"Logged {interaction_type} interaction to: {log_dir}",
                                                              'system'))

        except TypeError as e:
            error_msg = f"JSON SERIALIZATION FAILED (Type Error): {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
        except IOError as e:
            error_msg = f"FILE WRITE FAILED (IO Error): Check permissions for {log_dir}. Error: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
        except Exception as e:
            self.master.after(0, lambda: self.display_message(f"GENERIC LOGGING ERROR: {e}", 'error'))

    def query_gemini_vision(self):
        """Captures a frame from the live feed and sends it to Gemini for multimodal analysis."""

        if not self.video_capture or not self.is_face_scanner_active:
            self.master.after(0, lambda: self.say("Vision query failed: Camera is not active."))
            return

        ret, frame = self.video_capture.read()
        if not ret:
            self.master.after(0, lambda: self.say("Vision query failed: Could not read frame from camera."))
            return

        self.master.after(0, lambda: self.status_label.config(text="◈ ANALYZING IMAGE ◈"))
        self.master.after(0, lambda: self.say("Analyzing image, one moment."))

        user_query = self.last_query

        # --- NEW: SAVE IMAGE CONTEXT FOR LOGGING (inside the new project data folder) ---
        log_dir = os.path.join(os.getcwd(), "venom_fine_tune_data")
        temp_dir = os.path.join(log_dir, "Vision_Context")
        os.makedirs(temp_dir, exist_ok=True)
        temp_image_filename = f"vision_context_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        temp_image_path = os.path.join(temp_dir, temp_image_filename)
        # ---------------------------------------------

        try:
            # 1. Convert OpenCV frame (BGR) to PIL Image (RGB)
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(cv2image)
            pil_image.save(temp_image_path)  # Save the image locally

            # 2. Determine Intent and Construct Dynamic Prompt
            if "debug this error" in user_query or "fix this error" in user_query:
                context_prompt = (
                    "You are a Senior Debugging AI. Analyze the image for any code, terminal output, "
                    "or error messages. Identify the source of the error, explain what caused it, "
                    "and provide a concrete fix or next steps. Focus only on the text visible in the image."
                )
            elif "translate the text" in user_query or "read this sign" in user_query:
                context_prompt = (
                    "You are a Multilingual OCR Specialist. Read all text visible in the image. "
                    "Provide the original text first, and then translate it into English. If the text is "
                    "already English, just confirm the text and provide a brief summary."
                )
            elif "find the price of this" in user_query or "search for this product" in user_query:
                context_prompt = (
                    "You are a Visual Search Agent. Identify the main product or object in the image. "
                    "Use web grounding to find its name, model number, current market price, and a link "
                    "to a retailer, if possible. DO NOT INVENT INFORMATION. Be concise."
                )
            else:
                context_prompt = "Identify the primary object in the center of the image. Provide a brief description."

            final_prompt = f"{context_prompt}\n\nUser Query: {user_query}"

            # 3. Multimodal API Call
            model = genai.GenerativeModel('gemini-2.5-flash')
            contents = [pil_image, final_prompt]
            response = model.generate_content(contents)
            content = response.text

            # 4. --- LOGGING THE VISION INTERACTION ---
            # NOTE: We log the relative path to the image, which is better for portability
            relative_image_path = os.path.join("venom_fine_tune_data", "Vision_Context", temp_image_filename)
            self._log_fine_tuning_data('vision', user_query, content, image_path=relative_image_path)
            # ----------------------------------------

            # 5. Display and Speak Response
            self.master.after(0, lambda: self.display_message(f"Vision Response: {content}", 'venom'))
            self.master.after(0, lambda: self.create_response_interface(
                f"VISION QUERY: {user_query.title()}\n\n{content}"))
            self.master.after(0, lambda: self.say(content))

        except types.ClientError as e:
            error_msg = f"API Client Error: Your request failed (e.g., rate limit, invalid key). Details: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
            self.master.after(0, lambda: self.say("API client failed. Please check your key or rate limits."))

        except Exception as e:
            error_msg = f"Vision Query Error: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
            self.master.after(0, lambda: self.say("Vision query failed due to an internal error."))

        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    def query_gemini(self, prompt):
        """Query Gemini AI for general chat with thread-safe GUI updates."""
        if not self.gemini_chat:
            self.master.after(0, lambda: self.say("Gemini AI is not configured. Please set your API key."))
            return

        self.master.after(0, lambda: self.display_message("Connecting to neural network...", 'system'))
        self.master.after(0, lambda: self.status_label.config(text="◈ RUK EK MIN SOCH RAHA HU ◈"))

        try:
            response = self.gemini_chat.send_message(prompt)
            content = response.text

            # --- LOGGING THE CHAT INTERACTION ---
            self._log_fine_tuning_data('chat', prompt, content)
            # ------------------------------------

            self.master.after(0, lambda: self.display_message(f"Neural Response: {content}", 'venom'))
            self.master.after(0, lambda: self.create_response_interface(f"VENOM:\n\n{content}"))
            self.master.after(0, lambda: self.say(content))

        except Exception as e:
            error_msg = f"Neural network error: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))
            self.master.after(0, lambda: self.create_response_interface(f"ERROR:\n\n{error_msg}"))
            self.master.after(0, lambda: self.say("Neural network connection failed."))
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    def _get_current_project_code(self, target_path=None):
        """Helper to read all files in the specified project directory."""

        # If a target path is provided (for the new reload feature), use it.
        # Otherwise, use the existing self.current_project_path (for summarization/follow-up).
        base_path = target_path if target_path else self.current_project_path

        if not base_path or not os.path.isdir(base_path):
            return None

        code_content = []
        # Walk through the directory to find all files recursively
        for root, _, files in os.walk(base_path):
            for filename in files:
                # Construct relative path for the Gemini tag
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, base_path)

                # Exclude hidden files and directories like .git or .vscode
                if relative_path.startswith('.') or "__pycache__" in relative_path or relative_path.startswith(
                        "venom_fine_tune_data"):
                    continue

                # Exclude common binaries, large files, etc. (Can be extended)
                if any(relative_path.lower().endswith(ext) for ext in
                       ['.png', '.jpg', '.jpeg', '.gif', '.mp3', '.mp4', '.bin']):
                    continue

                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    code_content.append(f"[--FILE: {relative_path}--]\n{file_content}\n")
                except Exception as e:
                    # ⭐ CRITICAL FIX APPLIED HERE ⭐
                    # Binding 'relative_path' and 'e' to the lambda's default arguments
                    # to prevent the NameError when the callback executes.
                    self.master.after(0, lambda p=relative_path, err=e: self.display_message(
                        f"Could not read file {p}: {err}", 'warning'))
                    # --------------------------------

        return "\n".join(code_content)

    def process_code_update_followup(self, update_query):
        """
        Handles subsequent modification requests when in code context mode,
        RELYING ON THE CHAT HISTORY FOR CONTEXT, which is more robust and efficient.
        """
        self.master.after(0, lambda: self.status_label.config(text="◈ RUK ABHI CODE UPDATE KAR RAHA HU ◈"))

        if not self.gemini_code_chat or not self.current_project_path:
            self.awaiting_code_followup = False
            self.master.after(0, lambda: self.say(
                "Code context was lost. Please start a new code request or load a project."))
            return

        updated_response_content = None  # Initialize outside try for access in finally
        try:
            # 1. CRITICAL FIX: Inject a final, aggressive reminder into the chat before sending the request
            self.gemini_code_chat.history.append({
                "role": "user",
                "parts": [{
                    "text": (
                        "URGENT INSTRUCTION: You MUST use the STRICT format. "
                        "Your response starts NOW with the first **[--FILE: ...--]** tag and contains "
                        "**NO** conversational text, summaries, or markdown blocks **before** or **after** the file tags. "
                        "If you fail this, the code will not save. Implement the requested changes now."
                    )
                }]
            })

            edit_prompt = (
                "Implement the following changes to the project: "
                f"{update_query}"
            )

            # 2. Send the user's request.
            response = self.gemini_code_chat.send_message(edit_prompt)
            updated_response_content = response.text

            # 3. Parse the file chunks from the response
            _, _, updated_file_chunks = self._parse_gemini_project_response(updated_response_content)

            # 4. Reparse and overwrite files in the current project directory
            project_name = os.path.basename(self.current_project_path)
            project_name_title = project_name.replace('-', ' ').title()

            success, created_files, file_info_message = self._parse_and_save_files(
                updated_file_chunks,  # Pass the chunks directly
                project_name
            )

            if success and created_files:
                # --- LOGGING THE CODE MODIFICATION INTERACTION ---
                self._log_fine_tuning_data('code', update_query, updated_response_content)
                # -------------------------------------------------

                # --- CONFIRMATION MODIFIED: ADDED self.say() ---
                self.master.after(0, lambda: self.create_response_interface(
                    f"CODE MODIFICATION APPLIED to {project_name_title}:\n\n{file_info_message}\n\n[Code Context Active] What next?"))

                # *** NEW FEATURE IMPLEMENTATION ***
                self.master.after(0, lambda: self.say("Modification applied."))
                # **********************************

                # -----------------------------------------------------
            else:
                # FIX: Detailed error reporting if parsing fails or save fails
                raw_output_for_display = updated_response_content[:1500] + (
                    '...' if len(updated_response_content) > 1500 else '')

                final_error_message = (
                    "CRITICAL ERROR: Code saving failed.\n"
                    "Reason: Model response was unparseable or file saving was blocked/failed.\n\n"
                    f"{file_info_message}\n\n"
                    f"--- RAW RESPONSE START (Check for missing separators or format break) ---\n\n"
                    f"{raw_output_for_display}"
                )

                self.master.after(0, lambda: self.display_message("Code modification failed. See response window.",
                                                                  'error'))
                self.master.after(0, lambda: self.create_response_interface(
                    f"CODE MODIFICATION FAILURE:\n\n{final_error_message}"))
                self.master.after(0, lambda: self.say(
                    "Failed to apply code changes. Check the response window for details."))


        except Exception as e:
            error_msg = f"Code modification internal error: {e}"
            self.master.after(0, lambda: self.display_message(error_msg, 'error'))

            # FIX: If the full response is available, log it in the error message
            raw_output_for_display = updated_response_content[:1500] + ('...' if updated_response_content and len(
                updated_response_content) > 1500 else ' (No raw response captured)')

            final_error_message = (
                f"INTERNAL ERROR: {error_msg}\n\n"
                f"--- RAW RESPONSE START ---\n\n"
                f"{raw_output_for_display}"
            )

            self.master.after(0, lambda: self.create_response_interface(
                f"CODE MODIFICATION FAILURE:\n\n{final_error_message}"))
            self.master.after(0, lambda: self.say(
                "Failed to apply code changes. Check the response window for details."))
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    # --- NEW PROJECT LOADING METHOD ---

    def select_and_load_project(self):
        """
        Opens a directory selection dialog, loads the code from that project,
        and initializes the Gemini code chat context for iterative editing.
        (Called from main thread by button/voice command)
        """
        if not self.gemini_model:
            self.say("Gemini AI is not configured. Cannot load code context.")
            self.create_response_interface("ERROR:\n\nGemini AI is not configured. Cannot load code context.")
            return

        # Use tkinter's filedialog to select a directory
        # Initial directory set to desktop for convenience
        folder_path = filedialog.askdirectory(
            title="Select Project Folder to Load for Code Editing",
            initialdir=os.path.expanduser("~/Desktop")
        )

        if not folder_path:
            self.say("Project loading cancelled.")
            return

        self.master.after(0, lambda: self.status_label.config(text="◈ LOADING PROJECT CONTEXT ◈"))
        # Offload the heavy work to a thread
        threading.Thread(target=self._load_project_context_thread, args=(folder_path,), daemon=True).start()

    def _load_project_context_thread(self, folder_path):
        """Worker thread to handle reading files and initializing Gemini context."""
        project_name = os.path.basename(folder_path)

        # 1. Read all files in the directory
        code_content = self._get_current_project_code(folder_path)

        if not code_content:
            self.master.after(0, lambda: self.say(
                f"Failed to load project {project_name}. Folder may be empty or unreadable."))
            self.master.after(0, lambda: self.create_response_interface(
                f"ERROR:\n\nProject path: {folder_path}\nCould not read any files."))
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))
            return

        # 2. Set State Variables
        self.awaiting_code_followup = True
        self.current_project_path = folder_path

        # 3. Re-initialize and load the code chat context
        self.gemini_code_chat = self.gemini_model.start_chat(history=[])

        # Reconstruct the history entry with the full file structure
        context_load_message = {
            "role": "user",
            "parts": [
                {
                    "text": (
                        f"CONTEXT RELOADED: The following files represent the current state of the '{project_name}' project. "
                        "You are now in iterative editing mode. "
                        f"--- CURRENT PROJECT FILES ---\n\n{code_content}"
                    )
                },
                {
                    "text": (
                        "FOR ALL FUTURE TURNS: Your ONLY task is to "
                        "respond with the complete, updated file content(s) using the **STRICT** "
                        "[--FILE: path/to/filename.ext--] separator(s) "
                        "for ONLY the files you modify. **DO NOT** include any conversational text, "
                        "markdown blocks (e.g., ```), or file summary text outside of these delimiters. "
                        "Start your response immediately with [--FILE:...]."
                    )
                }
            ]
        }
        self.gemini_code_chat.history.append(context_load_message)

        # 4. Success Feedback and VS Code launch
        project_name_title = project_name.replace('-', ' ').title()
        final_display_message = (
            f"PROJECT RELOADED: {project_name_title}\n"
            f"PATH: {folder_path}\n\n"
            f"[CODE CONTEXT ACTIVE]\n\n"
            f"Opening project in VS Code..."
        )
        follow_up_prompt = f"Project {project_name_title} loaded successfully. What changes would you like to make, or say 'finished' to exit code mode?"

        self.master.after(0, lambda: self.create_response_interface(f"SYSTEM:\n\n{final_display_message}"))
        self.master.after(0, lambda: self.say(follow_up_prompt))

        try:
            # Launch VS Code
            if platform.system() == 'Darwin':
                subprocess.run(['code', folder_path], check=True)
            elif platform.system() == 'Windows':
                subprocess.run(['code', folder_path], check=True, shell=True)
            else:
                subprocess.run(['code', folder_path], check=True)
        except Exception as e:
            self.master.after(0, lambda: self.display_message(
                f"VS Code launch failed. Error: {e}. Proceeding without auto-open.",
                'warning'))
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    # --- OTHER UTILITY METHODS ---

    def summarize_current_project(self):
        """Analyzes the current project, generates a README.md summary, and saves it."""
        if not self.current_project_path:
            self.master.after(0, lambda: self.say("No active code project found to summarize."))
            self.master.after(0, lambda: self.create_response_interface(
                "SYSTEM:\n\nCannot summarize: No active project directory is set."))
            return
        if not self.gemini_model:
            self.master.after(0, lambda: self.say("Gemini AI is not configured. Cannot generate summary."))
            return

        def do_summarization():
            self.master.after(0, lambda: self.status_label.config(text="◈ ANALYZING PROJECT STRUCTURE ◈"))

            # Pass the path to the updated helper function
            code_content = self._get_current_project_code(self.current_project_path)
            project_name = os.path.basename(self.current_project_path)

            if not code_content:
                self.master.after(0, lambda: self.say("Project folder is empty or files are unreadable."))
                return

            summarize_prompt = (
                "You are a technical documentarian. Analyze the following project structure and code. "
                "Your task is to generate a comprehensive `README.md` file in standard Markdown format. "
                "The README must include: a brief project description, key features, technology stack, "
                "and clear instructions for running the project. Do not include any text outside the Markdown content.\n\n"
                f"Project Name: {project_name}\n\n"
                f"{code_content}"
            )

            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(summarize_prompt)
                readme_content = response.text.strip()

                # Clean up any markdown code block fencing that the model might add by mistake
                if readme_content.startswith("```markdown"):
                    readme_content = readme_content.strip("```markdown").strip()
                if readme_content.endswith("```"):
                    readme_content = readme_content.strip("```").strip()

                # Save the README file
                readme_path = os.path.join(self.current_project_path, "README.md")
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(readme_content)

                # Summarize for speech/display
                speech_summary = readme_content.split('\n')[0].replace('#', '').strip()
                speech_summary = f"Summary generated. The project is: {speech_summary}. A new README file has been created."

                self.master.after(0, lambda: self.create_response_interface(
                    f"PROJECT DOCUMENTATION: {project_name.title()}\n\n"
                    f"README.md file successfully generated and saved to the project directory.\n\n"
                    f"--- README PREVIEW ---\n\n{readme_content[:1500]}"
                ))
                self.master.after(0, lambda: self.say(speech_summary))

            except Exception as e:
                error_msg = f"Project summarization error: {e}"
                self.master.after(0, lambda: self.display_message(error_msg, 'error'))
                self.master.after(0, lambda: self.say("Failed to generate project summary."))
            finally:
                self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

        threading.Thread(target=do_summarization, daemon=True).start()

    def display_message(self, message, tag='system'):
        """Enhanced message display (Now logs to the hidden ScrolledText for history)"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        prefixes = {'user': "USER", 'venom': "VENOM", 'system': "SYSTEM",
                    'warning': "⚠ WARNING", 'error': "✗ ERROR"}
        prefix = prefixes.get(tag, "◦")
        formatted_message = f"[{timestamp}] {prefix}: {message}\n"

        self.output_text.insert(tk.END, formatted_message, tag)
        self.output_text.see(tk.END)

        if int(self.output_text.index('end-1c').split('.')[0]) > 5000:
            self.output_text.delete(1.0, "2500.0")

    def setup_text_tags(self):
        """Configure text styling tags - used by display_message in the hidden log."""
        if not hasattr(self, 'output_text') or not self.output_text: return

        # Updated fonts to be consistent with new theme
        self.output_text.tag_config('user', foreground=self.electric_cyan,
                                    font=self.CODE_FONT + ("bold",))
        self.output_text.tag_config('venom', foreground=self.success_green,
                                    font=self.CODE_FONT + ("bold",))
        self.output_text.tag_config('system', foreground=self.neon_purple,
                                    font=self.CODE_FONT)
        self.output_text.tag_config('warning', foreground=self.warning_orange,
                                    font=self.CODE_FONT + ("bold",))
        self.output_text.tag_config('error', foreground=self.danger_red,
                                    font=self.CODE_FONT + ("bold",))

    def clear_output(self):
        """Clears the hidden chat log and resets Gemini history."""
        self.output_text.delete(1.0, tk.END)
        if self.gemini_model:
            self.gemini_chat = self.gemini_model.start_chat(history=[])
        self.gemini_code_chat = None
        self.awaiting_code_followup = False
        self.current_project_path = None
        self.master.after(0, lambda: self.create_response_interface("SYSTEM:\n\nNeural interface cleared"))
        self.master.after(0, lambda: self.say("Neural interface cleared"))

        self.destroy_toolbox()

    def save_chat_to_file(self):
        """Saves the chat history from the hidden log."""
        try:
            chat_content = self.output_text.get("1.0", tk.END).strip()
            if not chat_content:
                self.master.after(0, lambda: self.say("Chat history is empty. Nothing to save."))
                return

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"Venom_Chat_Log_{timestamp}.txt"
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            file_path = os.path.join(desktop_path, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("=== VENOM A.I CHAT LOG ===\n")
                f.write(datetime.datetime.now().strftime("Log Date: %A, %B %d, %Y %I:%M:%S %p\n"))
                f.write("==========================\n\n")
                f.write(chat_content)
                f.write("\n\n==========================")

            self.master.after(0, lambda: self.create_response_interface(
                f"SYSTEM:\n\nChat saved successfully to: {filename}"))
            self.master.after(0,
                              lambda: self.say(f"Chat history saved successfully to file {filename} on your desktop."))

        except Exception as e:
            self.master.after(0, lambda: self.display_message(f"Error saving chat: {e}", 'error'))
            self.master.after(0, lambda: self.say("Error saving chat history."))

    def get_code_from_gemini(self, code_prompt):
        if not self.gemini_model:
            self.master.after(0, lambda: self.say("Gemini AI is not configured. Cannot generate code."))
            return

        self.master.after(0, lambda: self.display_message(f"Generating code: {code_prompt}", 'system'))
        self.master.after(0, lambda: self.status_label.config(text="◈ RUK CODE LIKHNE DE ◈"))

        # ------------------------------------------------------------------------------------------
        # REFINED SYSTEM PROMPT FOR PROFESSIONAL CODE
        # ------------------------------------------------------------------------------------------
        system_prompt = """You are an elite, production-level software architect. Your goal is to generate *complete*, *functional*, and *highly professional* multi-file projects from a single user request.

**PROFESSIONAL CODE STANDARDS (NON-NEGOTIABLE):**
1.  **Modularity & Structure:** Separate concerns cleanly (e.g., HTML, CSS, JS; components, services, utils).
2.  **Modern Syntax:** Use modern standards like **Python PEP8**, **ES6+ JavaScript**, and **Semantic HTML5**.
3.  **Documentation:** Include **docstrings or header comments** for all major functions, classes, and file headers explaining their purpose and usage.
4.  **Security & Best Practices:** Avoid inline styles or scripts. Use descriptive variable and function names.
5.  **Run Instructions:** Include clear, concise comments in the main execution file (e.g., `app.py`, `index.html`) on how to run or deploy the project.

**STRICT FORMAT RULES (MUST BE ADHERED TO):**
1.  You MUST use the **[--PROJECT_NAME: concise-name-here--]** separator first (use only lowercase letters and hyphens/underscores).
2.  Follow with a brief, high-quality **1-2 sentence project summary** (after the PROJECT_NAME tag and before the first file).
3.  Structure your ENTIRE output using **[--FILE: path/to/filename.ext--]** separator for each file.
4.  **CRITICAL:** Your output must contain ONLY the separators and the raw code. DO NOT include any conversational text, markdown blocks (e.g., ```), or file summary text outside the specified delimiters. If you fail to use this format, the system will discard your response.
"""
        # ------------------------------------------------------------------------------------------

        try:
            model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
            response = model.generate_content(code_prompt)
            content = response.text
            return content.strip()
        except Exception as e:
            self.master.after(0, lambda: self.display_message(f"Code generation error: {e}", 'error'))
            return None
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    def _parse_gemini_project_response(self, response_text):
        """
        Parses the raw Gemini response for project name, summary, and file chunks.

        *** CRITICAL FIX IMPLEMENTED: Ultimate Tolerance for leading text/format breaks ***

        Returns: (project_name, project_summary, file_chunks)
        """
        project_name = "untitled-project"
        project_summary = "A project generated by Venom AI (Summary unparseable)."
        file_chunks = []

        # 0. Strip leading/trailing whitespace
        response_text = response_text.strip()

        # 1. Extract Project Name (Non-greedy match for the content)
        name_match = re.search(r"\[--PROJECT_NAME:\s*(.+?)--\]", response_text)
        if name_match:
            suggested_name = name_match.group(1).strip()
            # Sanitize name: lowercase, replace non-alphanumeric/hyphen/underscore with hyphen
            project_name = "".join(c if c.isalnum() or c in ('-', '_') else '-' for c in suggested_name).lower().strip(
                '-')
            if not project_name: project_name = "untitled-project"

        # 2. Find the index of the first file separator to clean up any leading conversation/comments
        # Use a non-greedy search to find the *first* file tag
        first_file_tag_match = re.search(r"\[--FILE:", response_text)

        # If no file tags are found, we fail early.
        if not first_file_tag_match:
            return project_name, project_summary, file_chunks  # Returns empty file_chunks

        # Discard everything before the first recognized file tag
        start_index = first_file_tag_match.start()
        clean_response_text = response_text[start_index:]

        # 3. Extract Project Summary (from original text, between PROJECT_NAME and file start)
        # This uses the original response text but relies on the structure up to the first file tag
        summary_pattern = r"\[--PROJECT_NAME:.+?--\]\s*(.*?)(?=\[--FILE:|$)"
        summary_match = re.search(summary_pattern, response_text, re.DOTALL)

        if summary_match and summary_match.group(1).strip():
            raw_summary = summary_match.group(1).strip()
            # Take the first 1-2 sentences as the summary
            sentences = re.split(r'(?<=[.?!])\s+', raw_summary)
            project_summary = ' '.join(sentences[:2]).strip()
            if project_summary and not project_summary.endswith('.'):
                project_summary += '.'
            if not project_summary:
                project_summary = "A project generated by Venom AI (Summary not provided)."  # Fallback
        else:
            project_summary = "A project generated by Venom AI (Summary missing or format broken)."

        # 4. Extract File Chunks (Applied to the cleaned text)
        # We start the match using the tag found in step 2.
        # This pattern MUST be non-greedy for the filename and content.
        file_pattern = r"\[--FILE:\s*(.+?)--\]\s*(.*?)(?=\[--FILE:|$)"
        matches = re.findall(file_pattern, clean_response_text, re.DOTALL)

        for filename, content in matches:
            filename = filename.strip()
            content = content.strip()
            # Security: Basic check to ensure filename is not empty (prevents empty folder creation)
            if filename and content:
                file_chunks.append((filename, content))

        return project_name, project_summary, file_chunks

    def _parse_and_save_files(self, file_chunks, project_name):
        """
        Saves the file chunks to the project directory, with CRITICAL PATH SANITIZATION.

        Args:
            file_chunks (list): A list of (filename, content) tuples.
            project_name (str): The name of the project directory.

        Returns: (success_bool, created_files_list, display_message)
        """
        # Determine the base path (for new creation or follow-up)
        if self.awaiting_code_followup and self.current_project_path:
            base_path = self.current_project_path
        else:
            base_path = os.path.join(os.path.expanduser("~/Desktop"), project_name)

        # CRITICAL: Get the canonical, absolute path of the intended base directory
        try:
            abs_base_path = os.path.realpath(base_path)
            os.makedirs(abs_base_path, exist_ok=True)  # Ensure base directory is created
        except Exception as e:
            self.master.after(0, lambda: self.display_message(
                f"File System Error: Failed to create project directory '{base_path}'. {e}", 'error'))
            return False, [], "Failed to create project directory. Check permissions."

        created_files = []
        failed_files = []

        if not file_chunks:
            # FIX: More specific message for parsing failure
            final_display_message = "ERROR: Model failed to generate file content with correct [--FILE:...] separators."
            return False, [], final_display_message

        for filename, content in file_chunks:
            # 1. Join base path with the *relative* filename
            tentative_path = os.path.join(abs_base_path, filename)

            # 2. Get the canonical, real path (resolves '..', symlinks, etc.)
            try:
                final_path = os.path.realpath(tentative_path)
            except Exception:
                failed_files.append(f"{filename} (Invalid Path)")
                continue

            # 3. CRITICAL SECURITY CHECK: Ensure the resolved path remains *inside* the project directory
            if not final_path.startswith(abs_base_path + os.sep) and final_path != abs_base_path:
                self.master.after(0, lambda: self.display_message(
                    f"SECURITY ALERT: Directory traversal attempt blocked for file: '{filename}'.", 'error'))
                failed_files.append(f"{filename} (Traversal Blocked)")
                continue

            # 4. Proceed with writing: Directory Creation
            try:
                # Ensure the containing directory for the file exists
                os.makedirs(os.path.dirname(final_path), exist_ok=True)
            except Exception as e:
                self.master.after(0, lambda: self.display_message(f"Failed to create directory for '{filename}': {e}",
                                                                  'error'))
                failed_files.append(filename)
                continue

            # 5. Proceed with writing: File Write
            try:
                with open(final_path, "w", encoding="utf-8") as f:
                    f.write(content)
                created_files.append(filename)
            except Exception as e:
                self.master.after(0, lambda: self.display_message(f"Failed to write file '{filename}': {e}", 'error'))
                failed_files.append(filename)
                # Continue trying to save other files

        file_list_str = "\n".join(f"- {f}" for f in created_files)

        if failed_files:
            file_list_str += "\n\n--- FAILED TO WRITE/BLOCKED ---\n" + "\n".join(f"- {f}" for f in failed_files)
            final_display_message = f"PARTIAL SUCCESS. Some files failed to write or were blocked. Check console and permissions.\n\n{file_list_str}"
            # Even on partial success, treat as failure to trigger error feedback in caller
            return False, created_files, final_display_message

        final_display_message = f"FILES AFFECTED:\n{file_list_str}"

        return True, created_files, final_display_message

    def create_code_file(self, request):
        """
        Handles the initial code generation request and sets up the code context.
        """
        response_text = self.get_code_from_gemini(request)
        if not response_text:
            return

        # --- REFACTORED: Use centralized parser ---
        project_name, project_summary, file_chunks = self._parse_gemini_project_response(response_text)

        if not file_chunks:
            # FIX: Detailed error message for unparseable raw response
            raw_output_for_display = response_text[:1500] + ('...' if len(response_text) > 1500 else '')
            final_error_message = (
                "CRITICAL ERROR: Project creation failed.\n"
                "Reason: Model response was unparseable. The AI did not use the strict format.\n\n"
                f"--- RAW RESPONSE START (Check for missing separators or format break) ---\n\n"
                f"{raw_output_for_display}"
            )
            self.master.after(0, lambda: self.say("Project creation failed. The AI provided an unparseable response."))
            self.master.after(0, lambda: self.create_response_interface(
                f"CODE GENERATION FAILURE:\n\n{final_error_message}"))
            return

        success, created_files, file_info_message = self._parse_and_save_files(file_chunks, project_name)
        # --- END REFACTORED ---

        if not success:
            # FIX: Detailed error message for file system or partial save failure
            self.master.after(0, lambda: self.say("Project creation failed due to a file system error."))
            self.master.after(0, lambda: self.create_response_interface(
                f"CODE GENERATION FAILURE:\n\n{file_info_message}"))
            return

        # Set the current project path to the newly created folder
        self.current_project_path = os.path.join(os.path.expanduser("~/Desktop"), project_name)
        self.awaiting_code_followup = True

        if self.gemini_model:
            # --- LOGGING THE INITIAL CODE GENERATION ---
            self._log_fine_tuning_data('code', request, response_text)
            # -------------------------------------------

            # Reconstruct the full code content string for the initial context load
            initial_code_content = "\n".join([f"[--FILE: {f}--]\n{c}\n" for f, c in file_chunks])

            # Re-initialize code chat history for the new project
            self.gemini_code_chat = self.gemini_model.start_chat(history=[])

            # Pre-load the chat history with the project context (Same logic as the new load function)
            context_load_message = {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "CONTEXT LOADED: The following files represent the current state of the '{project_name}' project. "
                            "You are now in iterative editing mode. "
                            f"--- INITIAL PROJECT FILES ---\n\n{initial_code_content}"
                        )
                    },
                    {
                        "text": (
                            "FOR ALL FUTURE TURNS: Your ONLY task is to "
                            "respond with the complete, updated file content(s) using the **STRICT** "
                            "[--FILE: path/to/filename.ext--] separator(s) "
                            "for ONLY the files you modify. **DO NOT** include any conversational text, "
                            "markdown blocks (e.g., ```), or file summary text outside of these delimiters. "
                            "Start your response immediately with [--FILE:...]."
                        )
                    }
                ]
            }
            # Manually set the history *before* the first real interaction
            self.gemini_code_chat.history.append(context_load_message)

        project_name_title = project_name.replace('-', ' ').title()
        final_display_message = (
            f"PROJECT: {project_name_title}\n"
            f"SUMMARY: {project_summary}\n\n"
            f"{file_info_message}\n\n"
            f"[CODE CONTEXT ACTIVE]\n\n"
            f"Opening project in VS Code..."
        )
        # Suppressing TTS for successful code generation
        follow_up_prompt = f"Project {project_name_title} created successfully and files are ready. What changes would you like to make, or say 'finished' to exit code mode?"

        self.master.after(0, lambda: self.create_response_interface(f"SYSTEM:\n\n{final_display_message}"))

        try:
            # Use platform-independent way to open the folder/project in VS Code
            if platform.system() == 'Darwin':
                subprocess.run(['code', self.current_project_path], check=True)
            elif platform.system() == 'Windows':
                subprocess.run(['code', self.current_project_path], check=True, shell=True)
            else:
                subprocess.run(['code', self.current_project_path], check=True)

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            self.master.after(0, lambda: self.display_message(
                f"VS Code launch failed (Is 'code' in your PATH?). Error: {e}. Proceeding without auto-open.", 'error'))
            self.master.after(0, lambda: self.say("VS Code failed to launch automatically."))
        except Exception as e:
            self.master.after(0, lambda: self.display_message(
                f"VS Code launch failed. Error: {e}. Proceeding without auto-open.",
                'error'))
        finally:
            self.master.after(0, lambda: self.status_label.config(text="◉ PUCH BHAI KYA PUCHNA HA"))

    def on_closing(self):
        """Enhanced shutdown with animation and scanner cleanup"""
        if messagebox.askokcancel("VENOM A.I Shutdown", "Shutdown VENOM A.I."):
            self.display_message("Initiating VENOM A.I shutdown...", 'system')
            self.is_listening = False
            self.is_speaking = False
            self.stop_speaking_gui()
            self.deactivate_face_scanner()  # NEW: Clean up webcam

            if self.toolbox_window: self.toolbox_window.destroy()
            if self.response_window: self.response_window.destroy()

            def fade_shutdown():
                try:
                    alpha = self.master.attributes('-alpha')
                    if alpha > 0.1:
                        self.master.attributes('-alpha', alpha - 0.05)
                        self.master.after(50, fade_shutdown)
                    else:
                        self.master.destroy()
                except:
                    self.master.destroy()

            self.master.after(1000, fade_shutdown)


if __name__ == '__main__':
    root = tk.Tk()
    app = VenomAssistantGUI(root)
    root.mainloop() 
