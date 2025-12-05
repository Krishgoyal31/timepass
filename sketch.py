# venom_sketch_conceptualizer_feature_rich_professional_ui.py
import os
import sys
import json
import math
import random
import io
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QPushButton, QLabel, QSplitter, QMessageBox,
    QLineEdit, QFileDialog, QInputDialog, QMenu, QTabWidget,
    QHeaderView, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import (
    Qt, QSize, QThreadPool, QRunnable, pyqtSignal, QObject,
    QRect, QPointF, QPoint, pyqtSlot
)
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont, QPolygonF, QPixmap, QPainterPath
)

# try importing QtSvg for SVG export
try:
    from PyQt6.QtSvg import QSvgGenerator

    SVG_AVAILABLE = True
except Exception:
    SVG_AVAILABLE = False

# generative API (best-effort import — usage may need SDK-specific adjustments)
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

# Gemini key and model (read from environment, set dummy default)
# IMPORTANT: REPLACE THIS STRING WITH YOUR ACTUAL KEY BEFORE RUNNING
GEMINI_API_KEY = "AIzaSyDiR-L5H2uRq3x5lbrbrsGUjfMp22PUQk0"  # <--- REPLACE THIS STRING
LLM_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------- Schema ----------------
DIAGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "type": {"type": "string"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["id", "text", "type", "x", "y"]
            }
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "label": {"type": "string"}
                },
                "required": ["from", "to"]
            }
        }
    },
    "required": ["title", "nodes", "links"]
}


# ---------------- Utility: Auto-layout ----------------
def auto_layout(diagram, width=1000, height=1000, iterations=300, dist=250):
    """
    Simple force-based layout to reduce overlaps.
    Modifies node x,y in-place, keeping values 0..1000.
    """
    nodes = diagram.get("nodes", [])
    n = len(nodes)
    if n <= 1:
        return diagram

    # initialize positions to current or centered default if missing
    pos = {}
    for i, node in enumerate(nodes):
        x = int(node.get("x", -1))
        y = int(node.get("y", -1))

        # If coordinates are missing (x == -1 or y == -1), start near the center (500, 500)
        if x == -1 or y == -1:
            # Small random jitter around center X
            x = 500 + random.randint(-50, 50)
            # Stagger initial vertical positions slightly for better starting separation
            y = 500 + (i - n / 2) * 80 + random.randint(-30, 30)

        pos[node["id"]] = [float(x), float(y)]

    # iterative repulsion + mild spring to original positions
    for it in range(iterations):
        forces = {nid: [0.0, 0.0] for nid in pos.keys()}
        # repulsive force between every pair
        ids = list(pos.keys())
        for i in range(len(ids)):
            xi, yi = pos[ids[i]]
            for j in range(i + 1, len(ids)):
                xj, yj = pos[ids[j]]
                dx = xi - xj
                dy = yi - yj
                d2 = dx * dx + dy * dy + 1e-6
                d = math.sqrt(d2)
                # repulsion magnitude
                if d < dist:
                    force = (dist - d) / dist
                    # scaled by 10 so moves are noticeable
                    fx = (dx / d) * force * 10.0
                    fy = (dy / d) * force * 10.0
                    forces[ids[i]][0] += fx
                    forces[ids[i]][1] += fy
                    forces[ids[j]][0] -= fx
                    forces[ids[j]][1] -= fy

        # apply small attraction to keep layout from exploding, and keep within bounds
        for nid in ids:
            fx, fy = forces[nid]
            # small damping
            fx *= 0.5
            fy *= 0.5
            pos[nid][0] += fx
            pos[nid][1] += fy

            # Stronger center pull to ensure the final mass is centered
            center_pull_strength = 0.005
            pos[nid][0] += (width / 2 - pos[nid][0]) * center_pull_strength
            pos[nid][1] += (height / 2 - pos[nid][1]) * center_pull_strength

            # clamp
            pos[nid][0] = max(20, min(width - 20, pos[nid][0]))
            pos[nid][1] = max(20, min(height - 20, pos[nid][1]))

    # write back
    for node in nodes:
        p = pos[node["id"]]
        node["x"] = int(max(0, min(1000, int(p[0]))))
        node["y"] = int(max(0, min(1000, int(p[1]))))

    return diagram


# ---------------- Canvas with Drag & Drop and Link Creation ----------------
class DiagramCanvas(QWidget):
    # Emits when the internal diagram data changes (dict)
    diagram_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.diagram_data = None
        self.setMinimumSize(QSize(700, 450))
        self.setMouseTracking(True)
        self.font = QFont("Arial", 10)
        self.dragging = None  # node id being dragged
        self.panning = False  # True if panning the entire canvas
        self.pan_start_pos = QPoint()  # position where panning started
        self.diagram_offset = QPoint(0, 0)  # Global offset for diagram rendering
        self.drag_offset = (0, 0)
        self.dark_mode = False

        # New state for adding links/nodes
        self.add_link_mode = False
        self.add_link_source = None  # node id when creating a link
        self.highlight_node = None  # node id to highlight (for selection)
        self.curved_links = True  # default to curved
        self.node_w = 150
        self.node_h = 50

    def set_diagram_data(self, data):
        self.diagram_data = data
        # emit one-time update so parent can sync JSON/logs
        if self.diagram_data is not None:
            # send a shallow copy to avoid accidental external mutation
            self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
        self.update()

    def toggle_dark(self, on: bool):
        self.dark_mode = on
        if on:
            # Canvas dark theme color
            self.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333;")
        else:
            # Canvas light theme color
            self.setStyleSheet("background-color: #F4F4F4; border: 1px solid #CCCCCC;")
        self.update()

    # ---------- Node/Link helper methods ----------
    def _find_node_at_pos(self, px, py):
        """Return node dict under widget coords px,py or None. Takes widget coords."""
        if not self.diagram_data:
            return None
        w = self.width()
        h = self.height()

        # Adjust click position by current pan offset
        px = px - self.diagram_offset.x()
        py = py - self.diagram_offset.y()

        for node in reversed(self.diagram_data.get('nodes', [])):
            # Convert node 0..1000 coordinate to widget coordinates, then offset by pan
            x = int(node['x'] * w / 1000 - self.node_w / 2)
            y = int(node['y'] * h / 1000 - self.node_h / 2)

            rect = QRect(x, y, self.node_w, self.node_h)
            if rect.contains(QPoint(int(px), int(py))):
                return node
        return None

    def add_node_at(self, x_widget, y_widget, typ="process", text=None):
        """Place a new node at widget coordinates and emit change."""
        if self.diagram_data is None:
            return
        w = self.width()
        h = self.height()

        # Convert widget coordinates to 0..1000, compensating for pan offset
        nx = int(max(0, min(1000, (x_widget - self.diagram_offset.x()) * 1000 / w)))
        ny = int(max(0, min(1000, (y_widget - self.diagram_offset.y()) * 1000 / h)))

        nid = f"n{int(datetime.utcnow().timestamp() * 1000)}{random.randint(0, 999)}"
        if text is None:
            text = typ.capitalize()
        new_node = {"id": nid, "text": text, "type": typ, "x": nx, "y": ny}
        self.diagram_data.setdefault('nodes', []).append(new_node)
        # ensure links list exists
        self.diagram_data.setdefault('links', [])
        self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
        self.update()

    def add_node_center(self, typ="process", text=None):
        """Add node at center of canvas, respecting the current pan offset."""
        center_x = self.width() / 2
        center_y = self.height() / 2
        self.add_node_at(center_x, center_y, typ, text)

    def add_link_between(self, from_id, to_id, label=""):
        if self.diagram_data is None:
            return
        if from_id == to_id:
            return
        links = self.diagram_data.setdefault('links', [])
        # avoid duplicates
        for l in links:
            if l.get('from') == from_id and l.get('to') == to_id:
                return
        links.append({"from": from_id, "to": to_id, "label": label})
        self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
        self.update()

    def remove_link_between(self, from_id, to_id):
        if self.diagram_data is None:
            return
        links = self.diagram_data.get('links', [])
        self.diagram_data['links'] = [l for l in links if not (l.get('from') == from_id and l.get('to') == to_id)]
        self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
        self.update()

    def toggle_add_link_mode(self, on: bool):
        self.add_link_mode = on
        self.add_link_source = None
        self.highlight_node = None
        self.update()

    def set_curved_links(self, on: bool):
        self.curved_links = on
        self.update()

    # ---------- Paint ----------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)

        # Determine base colors for canvas content
        if self.dark_mode:
            instruction_color = QColor(100, 100, 100)
            link_color = QColor("#5A9BD6")
            node_text_color = QColor("#FFFFFF")
            canvas_bg = QColor(26, 26, 26)
        else:
            instruction_color = QColor(150, 150, 150)
            link_color = QColor("#34495E")
            node_text_color = QColor("#FFFFFF")
            canvas_bg = QColor(244, 244, 244)

        # Fill background
        painter.fillRect(self.rect(), canvas_bg)

        # Apply global pan offset to the painter transformation
        painter.translate(self.diagram_offset)

        # background instruction text
        if not self.diagram_data or not self.diagram_data.get('nodes'):
            painter.setPen(QPen(instruction_color))
            # Adjust drawing position to stay centered relative to canvas, not offset
            painter.drawText(self.rect().translated(-self.diagram_offset), Qt.AlignmentFlag.AlignCenter,
                             "Conceptualizer Ready.\nEnter a prompt and click Generate or add nodes.")
            return

        # map 0..1000 coords to widget
        w = self.width()
        h = self.height()

        nodes = self.diagram_data.get("nodes", [])
        links = self.diagram_data.get("links", [])
        node_map = {n['id']: n for n in nodes}

        # --- Pre-calculate link geometry for collision avoidance ---
        link_geometry: List[Dict] = []
        for link in links:
            s = node_map.get(link['from'])
            t = node_map.get(link['to'])
            if not s or not t:
                continue
            x1 = int(s['x'] * w / 1000)
            y1 = int(s['y'] * h / 1000)
            x2 = int(t['x'] * w / 1000)
            y2 = int(t['y'] * h / 1000)

            # Use link key for deterministic hashing
            key = tuple(sorted((link['from'], link['to'])))

            link_geometry.append({
                'link': link,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'key': key,
                'offset_index': 0  # Index to determine how far to offset from center
            })

        # --- Simple Link Collision Avoidance Heuristic ---
        # This checks for links sharing the same source/target pair (e.g., A->B and B->A)
        # and assigns a simple separation index based on link ID order.

        # 1. Group links by their non-directional (sorted) pair key
        link_groups: Dict[Tuple[str, str], List[Dict]] = {}
        for geo in link_geometry:
            pair = geo['key']
            if pair not in link_groups:
                link_groups[pair] = []
            link_groups[pair].append(geo)

        # 2. Assign offset indices within groups
        for pair, group in link_groups.items():
            if len(group) > 1:
                # Calculate required offsets for separation
                mid_index = (len(group) - 1) / 2
                for i, geo in enumerate(group):
                    # Offsets: 0, 1, -1, 2, -2, ... (center, then alternating sides)
                    geo['offset_index'] = (i - mid_index)

        # --- Draw links (behind nodes) ---
        painter.setPen(QPen(link_color, 2))
        for geo in link_geometry:
            x1, y1, x2, y2 = geo['x1'], geo['y1'], geo['x2'], geo['y2']
            link = geo['link']

            # Base offset magnitude for separation
            link_sep_mag = 10 * geo['offset_index']

            # Initialize separation offsets to float 0.0 before conditional assignment
            px, py = 0.0, 0.0

            # compute control point for curved or straight line
            if self.curved_links:
                # midpoint
                mx = (x1 + x2) / 2
                my = (y1 + y2) / 2
                # perpendicular offset based on distance
                dx = x2 - x1
                dy = y2 - y1
                dist = math.hypot(dx, dy) + 1e-6

                # BASE curve offset magnitude (independent of separation)
                base_curve_mag = min(80, max(20, dist * 0.12))

                # perpendicular vector (unit vector)
                px_unit = -dy / dist
                py_unit = dx / dist

                # Use a deterministic sign for base curve offset
                sign = 1 if (hash(link['from']) - hash(link['to'])) % 2 == 0 else -1

                # Total control point coordinates (cx, cy)
                cx = mx + px_unit * (base_curve_mag * sign + link_sep_mag)
                cy = my + py_unit * (base_curve_mag * sign + link_sep_mag)

                path = QPainterPath(QPointF(x1, y1))
                path.quadTo(QPointF(cx, cy), QPointF(x2, y2))
                painter.drawPath(path)

                # arrowhead calculation...
                tval = 0.98
                A = QPointF(x1, y1)
                B = QPointF(cx, cy)
                C = QPointF(x2, y2)
                dx_d = 2 * (1 - tval) * (B.x() - A.x()) + 2 * tval * (C.x() - B.x())
                dy_d = 2 * (1 - tval) * (B.y() - A.y()) + 2 * tval * (C.y() - B.y())
                ex = x2
                ey = y2
                self._draw_arrowhead(painter, ex - dx_d, ey - dy_d, ex, ey)
                # px and py remain 0.0 for labels (center position)

            else:
                # Straight line (apply perpendicular offset for separation)

                # perpendicular vector (unit vector)
                dx = x2 - x1
                dy = y2 - y1
                dist = math.hypot(dx, dy) + 1e-6
                px = -dy / dist * link_sep_mag
                py = dx / dist * link_sep_mag

                x1_off = x1 + px
                y1_off = y1 + py
                x2_off = x2 + px
                y2_off = y2 + py

                painter.drawLine(QPointF(x1_off, y1_off), QPointF(x2_off, y2_off))

                # Arrowhead uses the slightly offset line segment
                self._draw_arrowhead(painter, x1_off, y1_off, x2_off, y2_off)

            if link.get('label'):
                # place label near midpoint
                painter.setPen(QPen(QColor("#FFD166")))

                # Apply separation offset (px, py) to the label position.
                label_x = (x1 + x2) // 2 + 6 + px
                label_y = (y1 + y2) // 2 - 10 + py

                painter.drawText(int(label_x), int(label_y), link['label'])
                painter.setPen(QPen(link_color, 2))

        # draw nodes
        for node in nodes:
            x = int(node['x'] * w / 1000 - self.node_w / 2)
            y = int(node['y'] * h / 1000 - self.node_h / 2)
            typ = node.get('type', 'process').lower()
            text = node.get('text', '')

            # --- Node Color Logic (Consistent logic, theme-specific final colors) ---
            is_generic = typ in ['process', 'box', 'text', 'rectangle', '']

            # Base Colors (neutral)
            if typ in ['start', 'end', 'terminator', 'ellipse'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['start', 'end', 'exit'])):
                base_color = QColor("#3498DB")
            elif typ in ['decision', 'rhombus', 'diamond'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['?', 'if', 'decision', 'loop'])):
                base_color = QColor("#E74C3C")
            elif typ in ['data', 'input', 'output', 'parallelogram'] or (
                    is_generic and any(
                keyword in text.lower() for keyword in ['explore', 'data', 'read', 'get', 'input'])):
                base_color = QColor("#9B59B6")
            elif typ in ['database', 'db', 'storage'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['sql', 'database', 'store', 'storage'])):
                base_color = QColor("#F39C12")  # Deep Orange
            elif typ in ['document', 'report', 'output_file'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['document', 'report', 'file', 'pdf'])):
                base_color = QColor("#8E44AD")  # Purple
            else:
                base_color = QColor("#2ECC71")

            # Apply theme adjustment
            if self.dark_mode:
                # Slightly desaturated colors for dark theme (Professional)
                if base_color == QColor("#3498DB"):
                    color = QColor("#4A8ECF")
                elif base_color == QColor("#E74C3C"):
                    color = QColor("#C25446")
                elif base_color == QColor("#9B59B6"):
                    color = QColor("#8A67B2")
                elif base_color == QColor("#F39C12"):
                    color = QColor("#D88500")  # Darker Orange
                elif base_color == QColor("#8E44AD"):
                    color = QColor("#7B3D9D")  # Darker Purple
                else:
                    color = QColor("#3DAF6C")
                border_color = QColor("#CCCCCC")  # Light border
                node_text_color = QColor("#FFFFFF")
            else:
                # Slightly stronger colors for light theme
                color = base_color
                border_color = QColor("#2C3E50")  # Dark border
                node_text_color = QColor("#FFFFFF")  # White text still works best on strong colors

            # Highlighting for selection / add-link-mode
            if node.get('id') == self.highlight_node:
                # bright border to indicate selection
                highlight_border = QColor("#FFD166")
                painter.setPen(QPen(highlight_border, 3))
            else:
                painter.setPen(QPen(border_color, 2))

            painter.setBrush(QBrush(color))

            # Draw shape based on type
            if typ in ['decision', 'rhombus', 'diamond'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['?', 'if', 'decision', 'loop'])):
                pts = [
                    QPointF(x + self.node_w / 2, y),
                    QPointF(x + self.node_w, y + self.node_h / 2),
                    QPointF(x + self.node_w / 2, y + self.node_h),
                    QPointF(x, y + self.node_h / 2)
                ]
                painter.drawPolygon(QPolygonF(pts))
            elif typ in ['start', 'end', 'terminator', 'ellipse'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['start', 'end', 'exit'])):
                painter.drawEllipse(x, y, self.node_w, self.node_h)
            elif typ in ['data', 'input', 'output', 'parallelogram'] or (
                    is_generic and any(
                keyword in text.lower() for keyword in ['explore', 'data', 'read', 'get', 'input'])):
                # Draw parallelogram (Input/Output)
                pts = [
                    QPointF(x + 10, y),
                    QPointF(x + self.node_w, y),
                    QPointF(x + self.node_w - 10, y + self.node_h),
                    QPointF(x, y + self.node_h)
                ]
                painter.drawPolygon(QPolygonF(pts))
            elif typ in ['database', 'db', 'storage'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['sql', 'database', 'store', 'storage'])):
                # Draw Database (Cylinder shape)
                cy_h = self.node_h * 0.8  # Body height
                cy_e = self.node_h * 0.2  # Ellipse height

                # Bottom ellipse (filled body color)
                painter.drawRect(x, int(y + cy_e / 2), self.node_w, int(cy_h))
                painter.drawEllipse(x, int(y + cy_h), self.node_w, int(cy_e))

                # Top ellipse (filled body color)
                painter.drawEllipse(x, y, self.node_w, int(cy_e))
            elif typ in ['document', 'report', 'output_file'] or (
                    is_generic and any(keyword in text.lower() for keyword in ['document', 'report', 'file', 'pdf'])):
                # Draw Document (Rectangle with folded corner)
                fold_size = 15
                pts = [
                    QPointF(x, y),
                    QPointF(x + self.node_w - fold_size, y),
                    QPointF(x + self.node_w, y + fold_size),
                    QPointF(x + self.node_w, y + self.node_h),
                    QPointF(x, y + self.node_h),
                ]
                painter.drawPolygon(QPolygonF(pts))

                # Draw the corner fold line
                original_brush = painter.brush()
                painter.setBrush(QBrush(QColor(0, 0, 0, 0)))  # Transparent fill for the corner fold lines
                painter.drawLine(x + self.node_w - fold_size, y, x + self.node_w - fold_size, y + fold_size)
                painter.drawLine(x + self.node_w - fold_size, y + fold_size, x + self.node_w, y + fold_size)
                painter.setBrush(original_brush)  # Restore fill brush
            else:
                # Default to rounded rectangle (Process/Action)
                painter.drawRoundedRect(x, y, self.node_w, self.node_h, 12, 12)

            painter.setPen(QPen(node_text_color))
            text_rect = QRect(x + 6, y + 6, self.node_w - 12, self.node_h - 12)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, node.get('text', ''))

    def _draw_arrowhead(self, painter, x1, y1, x2, y2):
        """Draws a directional arrowhead at the (x2, y2) endpoint using tangent vector from (x1,y1)->(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        angle = math.atan2(dy, dx)
        arrow_size = 12
        p1 = QPointF(x2, y2)
        p2 = QPointF(x2 - arrow_size * math.cos(angle - math.pi / 6),
                     y2 - arrow_size * math.sin(angle - math.pi / 6))
        p3 = QPointF(x2 - arrow_size * math.cos(angle + math.pi / 6),
                     y2 - arrow_size * math.sin(angle + math.pi / 6))

        # Use filled triangle for a solid arrowhead
        painter.setBrush(QBrush(painter.pen().color()))
        poly = QPolygonF([p1, p2, p3])
        painter.drawPolygon(poly)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    # ---------- Mouse interactions ----------
    def mousePressEvent(self, event):
        pos = event.position()
        x = pos.x()
        y = pos.y()

        # Right-click behavior
        if event.button() == Qt.MouseButton.RightButton:
            # If click is on a node -> show node menu
            node = self._find_node_at_pos(x, y)
            if node:
                self.show_node_menu(node, event.globalPosition().toPoint())
            else:
                # empty canvas right-click -> show add node menu at point
                self.show_canvas_menu(event.globalPosition().toPoint(), x, y)
            return

        # Left-click behavior
        if event.button() == Qt.MouseButton.LeftButton:
            # If in add link mode: handle source/target selection
            if self.add_link_mode:
                clicked_node = self._find_node_at_pos(x, y)
                if clicked_node:
                    if self.add_link_source is None:
                        # select source
                        self.add_link_source = clicked_node['id']
                        self.highlight_node = self.add_link_source
                        self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
                        self.update()
                    else:
                        # select target — create link
                        target_id = clicked_node['id']
                        self.add_link_mode = True  # remain in mode unless toggled off
                        # add link and reset source
                        self.add_link_between(self.add_link_source, target_id)
                        # clear selection
                        self.add_link_source = None
                        self.highlight_node = None
                        self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
                        self.update()
                    return
                else:
                    # clicked empty while in link mode — cancel selection
                    self.add_link_source = None
                    self.highlight_node = None
                    self.update()
                    return

            # Not in link mode: check for dragging nodes
            if not self.diagram_data:
                return

            # Check for node drag first (node drag takes priority)
            node_to_drag = self._find_node_at_pos(x, y)
            if node_to_drag:
                # Start dragging node
                self.dragging = node_to_drag['id']
                # Calculate drag offset relative to the node's top-left corner (un-panned)
                node_x = int(node_to_drag['x'] * self.width() / 1000 - self.node_w / 2)
                node_y = int(node_to_drag['y'] * self.height() / 1000 - self.node_h / 2)
                # Calculate offset in widget coordinates (which includes the pan offset)
                self.drag_offset = (pos.x() - self.diagram_offset.x() - node_x,
                                    pos.y() - self.diagram_offset.y() - node_y)
                self.highlight_node = node_to_drag['id']
                self.panning = False
                return

            # If no node found, start panning the canvas
            if not self.dragging:
                self.panning = True
                self.pan_start_pos = pos.toPoint()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self.dragging and self.diagram_data:
            # --- Node Dragging ---
            w = self.width()
            h = self.height()

            # Target position relative to the un-panned canvas
            target_x_unpanned = pos.x() - self.diagram_offset.x()
            target_y_unpanned = pos.y() - self.diagram_offset.y()

            # New center position (compensating for the drag offset)
            new_x_center = target_x_unpanned - self.drag_offset[0] + self.node_w / 2
            new_y_center = target_y_unpanned - self.drag_offset[1] + self.node_h / 2

            # convert to 0..1000 normalized coordinates
            nx = int(max(0, min(1000, new_x_center * 1000 / w)))
            ny = int(max(0, min(1000, new_y_center * 1000 / h)))

            changed = False
            for node in self.diagram_data['nodes']:
                if node['id'] == self.dragging:
                    if node.get('x') != nx or node.get('y') != ny:
                        node['x'] = nx
                        node['y'] = ny
                        changed = True
                    break
            if changed:
                # emit copy to avoid external mutation
                self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
            self.update()

        elif self.panning:
            # --- Canvas Panning ---
            delta = pos.toPoint() - self.pan_start_pos
            self.diagram_offset += delta
            self.pan_start_pos = pos.toPoint()  # Reset start position to current mouse position
            self.update()

        else:
            # --- Link Mode Highlight/Cursor Update ---
            if self.add_link_mode:
                node = self._find_node_at_pos(pos.x(), pos.y())
                nid = node['id'] if node else None
                # Only update highlight if link source is not already selected, OR
                # if we are selecting the target and the mouse is over a different node
                if self.add_link_source is None:
                    if nid != self.highlight_node:
                        self.highlight_node = nid
                        self.update()
                else:
                    if nid and nid != self.add_link_source:
                        # Target mode: highlight potential target
                        if nid != self.highlight_node:
                            self.highlight_node = nid
                            self.update()
                    elif not nid and self.highlight_node != self.add_link_source:
                        # If mouse leaves a node, revert highlight to source node
                        self.highlight_node = self.add_link_source
                        self.update()
                    elif nid == self.add_link_source and self.highlight_node != self.add_link_source:
                        # If mouse is back on source, keep it highlighted
                        self.highlight_node = self.add_link_source
                        self.update()

            # Set hover cursor if over a draggable node (only when not in link mode)
            elif not self.add_link_mode:
                node = self._find_node_at_pos(pos.x(), pos.y())
                if node:
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            # final notify (emit current diagram)
            if self.diagram_data is not None:
                self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
            # Do not clear highlight until new press if we were in link mode
            if not self.add_link_mode:
                self.highlight_node = None
            self.update()

        if self.panning:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def show_node_menu(self, node, global_pos):
        # ensure dragging/panning is off when menu shows
        self.dragging = False
        self.panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        menu = QMenu(self)
        # Styled context menu based on current theme
        if self.dark_mode:
            menu_style = """
                QMenu { background-color: #333; border: 1px solid #555; color: #e0e0e0; }
                QMenu::item { padding: 5px 20px 5px 20px; }
                QMenu::item:selected { background-color: #555; }
            """
        else:
            menu_style = """
                QMenu { background-color: #FFFFFF; border: 1px solid #999; color: #111111; }
                QMenu::item { padding: 5px 20px 5px 20px; }
                QMenu::item:selected { background-color: #D9E8F3; }
            """
        menu.setStyleSheet(menu_style)

        edit_text = menu.addAction("Edit Text")
        add_arrow_from = menu.addAction("Add Arrow From This Node")
        delete_node = menu.addAction("Delete Node")
        action = menu.exec(global_pos)
        if action == edit_text:
            text, ok = QInputDialog.getText(self, "Edit Node Text", "Text:", text=node.get('text', ''))
            if ok:
                node['text'] = text
                self.update()
                if self.diagram_data is not None:
                    self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))
        elif action == add_arrow_from:
            # enter link creation with this node as source
            self.toggle_add_link_mode(True)
            self.add_link_source = node['id']
            self.highlight_node = node['id']
            self.update()
        elif action == delete_node:
            # remove node and related links
            nid = node['id']
            self.diagram_data['nodes'] = [n for n in self.diagram_data['nodes'] if n['id'] != nid]
            self.diagram_data['links'] = [l for l in self.diagram_data['links'] if l['from'] != nid and l['to'] != nid]
            self.update()
            if self.diagram_data is not None:
                self.diagram_changed.emit(json.loads(json.dumps(self.diagram_data)))

    def show_canvas_menu(self, global_pos, x_widget, y_widget):
        # ensure dragging/panning is off when menu shows
        self.dragging = False
        self.panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        menu = QMenu(self)
        if self.dark_mode:
            menu.setStyleSheet("QMenu { background-color: #333; color: #e0e0e0; }")
        else:
            menu.setStyleSheet("QMenu { background-color: #FFF; color: #111; }")

        add_process = menu.addAction("Add Process")
        add_decision = menu.addAction("Add Decision")
        add_io = menu.addAction("Add Input/Output")
        add_db = menu.addAction("Add Database")
        add_term = menu.addAction("Add Terminator")
        add_doc = menu.addAction("Add Document")
        action = menu.exec(global_pos)
        typ_map = {
            add_process: ("process", "Process"),
            add_decision: ("decision", "Decision"),
            add_io: ("data", "Input/Output"),
            add_db: ("database", "Database"),
            add_term: ("terminator", "Terminator"),
            add_doc: ("document", "Document")
        }
        if action in typ_map:
            typ, label = typ_map[action]
            self.add_node_at(x_widget, y_widget, typ=typ, text=label)


# ---------------- Tab Widget for Single Diagram ----------------
class DiagramTabWidget(QWidget):
    """Container for a single diagram: canvas and its JSON log."""

    def __init__(self, parent=None, dark_mode=False):
        super().__init__(parent)
        self.diagram = None

        self.canvas = DiagramCanvas()
        self.canvas.toggle_dark(dark_mode)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(False)
        self.splitter = QSplitter(Qt.Orientation.Vertical)  # Store splitter reference
        self.log_container = QWidget()  # Store log container reference
        self.log_is_visible = True  # Track state

        # Connect canvas changes to update the JSON log
        self.canvas.diagram_changed.connect(self._on_canvas_changed)

        # Layout for the tab content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.splitter, 1)

        self.splitter.addWidget(self.canvas)

        # Log container setup (Log Label + Text Area)
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 5, 0, 0)

        # Log Header (Label only)
        log_header = QHBoxLayout()
        log_label = QLabel("Output Log (JSON):")
        log_label.setObjectName("log_label")
        log_header.addWidget(log_label)
        log_header.addStretch(1)

        log_layout.addLayout(log_header)
        log_layout.addWidget(self.output)

        self.splitter.addWidget(self.log_container)

        # Set initial sizes: Canvas gets most space (70%)
        self.splitter.setSizes([700, 300])

    def set_log_visibility(self, visible):
        """Called by the parent app to show or hide the log panel."""
        if visible:
            # Restore Log (restore split 70/30)
            sizes = self.splitter.sizes()
            total = sum(sizes)
            # Restore based on 70/30 split, unless total is 0
            if total > 0 and sizes[1] == 0:
                self.splitter.setSizes([int(total * 0.7), int(total * 0.3)])
            elif total > 0 and sizes[0] == 0:
                # Case for if canvas was hidden, restore it too
                self.splitter.setSizes([int(total * 0.7), int(total * 0.3)])
            self.log_is_visible = True
        else:
            # Hide Log (collapse the splitter handle)
            current_canvas_size = self.splitter.sizes()[0]
            self.splitter.setSizes([current_canvas_size + self.splitter.sizes()[1], 0])
            self.log_is_visible = False

    def _get_empty_diagram(self, title):
        return {"title": title, "nodes": [], "links": []}

    @pyqtSlot(dict)
    def _on_canvas_changed(self, diagram_dict):
        # Save/refresh local diagram and update JSON text area
        try:
            self.diagram = diagram_dict
            self.output.setPlainText(json.dumps(self.diagram, indent=2))
        except Exception as e:
            self.output.setPlainText("Failed to update diagram: " + str(e))

    def set_diagram_data(self, data):
        self.diagram = data
        self.canvas.set_diagram_data(data)

        # Safely check for parent (QTabWidget) before setting tab title
        tab_widget = self.parent()
        if tab_widget and isinstance(tab_widget, QTabWidget) and data and data.get('title'):
            # This line only runs IF the widget is attached to the QTabWidget
            tab_widget.setTabText(tab_widget.indexOf(self), data['title'])

        if data is not None:
            self.output.setPlainText(json.dumps(self.diagram, indent=2))
        else:
            self.output.clear()


# ---------------- Gemini Worker ----------------
class GeminiWorkerSignals(QObject):
    result = pyqtSignal(dict, QWidget)
    error = pyqtSignal(str, QWidget)
    finished = pyqtSignal()


class GeminiWorker(QRunnable):
    def __init__(self, prompt, key, model, schema, target_tab_widget):
        super().__init__()
        self.prompt = prompt
        self.key = key
        self.model = model
        self.schema = schema
        self.target_tab_widget = target_tab_widget
        self.signals = GeminiWorkerSignals()

    def _extract_text(self, response):
        try:
            if hasattr(response, "text") and response.text:
                return response.text
            if hasattr(response, "candidates") and response.candidates:
                c = response.candidates[0]
                return getattr(c, "content", None) or getattr(c, "text", None)
            return str(response)
        except Exception:
            return None

    def run(self):
        try:
            if not GENAI_AVAILABLE:
                raise RuntimeError("google.generativeai SDK not available in this environment.")
            if not self.key:
                raise RuntimeError("No GEMINI_API_KEY provided. Set the GEMINI_API_KEY environment variable.")
            genai.configure(api_key=self.key)

            prompt_system = (
                    "You are an expert diagram generator. Output ONLY a JSON object matching this schema:\n"
                    + json.dumps(self.schema)
            )

            # Example modern attempt: create a 'GenerativeModel' then generate_content
            try:
                model = genai.GenerativeModel(self.model)
                messages = [
                    {
                        "role": "model",
                        "parts": [prompt_system]
                    },
                    {
                        "role": "user",
                        "parts": [self.prompt]
                    }
                ]
                response = model.generate_content(
                    messages,
                    generation_config={
                        "response_mime_type": "application/json",
                        "response_schema": self.schema
                    }
                )
                raw = self._extract_text(response)
            except Exception:
                # Fallback: try genai.generate or genai.chat or genai.responses.create depending on SDK
                try:
                    response = genai.generate(
                        model=self.model,
                        prompt=prompt_system + "\n\n" + self.prompt,
                        max_output_tokens=800
                    )
                    raw = self._extract_text(response)
                except Exception as e_fallback:
                    raise RuntimeError(f"Gemini/generative call failed: {e_fallback}")

            if not raw:
                raise ValueError("Empty response from Gemini.")

            # extract first JSON object from raw text (robust)
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end < start:
                raise ValueError("No JSON object found in response.")
            data_text = raw[start:end + 1]
            data = json.loads(data_text)

            # sanitize coordinates and defaults
            for n in data.get('nodes', []):
                n['x'] = int(max(0, min(1000, int(n.get('x', 500)))))
                n['y'] = int(max(0, min(1000, int(n.get('y', 500)))))

            tab_widget = self.target_tab_widget
            tab_widget.diagram = data

            self.signals.result.emit(data, tab_widget)
        except Exception as e:
            self.signals.error.emit(str(e), self.target_tab_widget)
        finally:
            self.signals.finished.emit()


# ---------------- Main UI ----------------
class VenomSketchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Made by Krish 🔧")
        self.setGeometry(80, 60, 1200, 800)
        self.threadpool = QThreadPool()
        self.dark_mode = True  # Default to dark mode

        # Set a preferred application font
        self.preferred_font_name = "Impact"
        self.app_font = QFont(self.preferred_font_name, 10)
        if self.preferred_font_name not in self.app_font.family():
            self.app_font = QFont("Arial Black", 10)
        self.setFont(self.app_font)

        # Define a secondary, lighter font for inputs/placeholders
        self.placeholder_font = QFont("Arial", 11)

        self.diagram_count = 0

        self._build_ui()
        self.set_dark_mode(self.dark_mode) # set dark mode and the correct icon
        self.new_diagram()  # Start with one empty page/diagram
        self.log_toggle_main_btn.setText("Toggle Log View (Visible)")  # Initial button state

        # Schedule initial positioning after the UI is drawn
        self.reposition_global_elements()

    # --- Helper methods to access current tab's components ---
    def current_tab(self) -> Optional['DiagramTabWidget']:
        return self.tab_widget.currentWidget()

    def current_diagram(self):
        tab = self.current_tab()
        return tab.diagram if tab else None

    def current_canvas(self):
        tab = self.current_tab()
        return tab.canvas if tab else None

    def current_output(self):
        tab = self.current_tab()
        return tab.output if tab else None

    # --- Responsive Positioning for Toggle Button ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_global_elements()

    def reposition_global_elements(self):
        # Position the toggle button in the top right corner, like in EmoCare
        button_size = self.dark_toggle.width()
        right_margin = 20
        top_margin = 5

        new_x = self.width() - button_size - right_margin
        new_y = top_margin

        self.dark_toggle.move(new_x, new_y)

    # --- Tab Management ---
    def new_diagram(self):
        self.diagram_count += 1
        title = f"Untitled Diagram {self.diagram_count}"

        new_tab = DiagramTabWidget(parent=self.tab_widget, dark_mode=self.dark_mode)

        self.tab_widget.addTab(new_tab, title)
        self.tab_widget.setCurrentWidget(new_tab)

        new_tab.set_diagram_data(new_tab._get_empty_diagram(title))

        self.log_toggle_main_btn.setText("Toggle Log View (Visible)")

    def close_tab_by_index(self, index):
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)
        else:
            QMessageBox.information(self, "Cannot Close",
                                    "The last remaining diagram cannot be closed. Create a new one first.")

    def toggle_current_log(self):
        current_tab = self.current_tab()
        if not current_tab:
            return

        is_visible = current_tab.log_is_visible

        current_tab.set_log_visibility(not is_visible)

        if not is_visible:
            self.log_toggle_main_btn.setText("Toggle Log View (Visible)")
        else:
            self.log_toggle_main_btn.setText("Toggle Log View (Hidden)")

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Title/Header Label (Replicating EmoCare Header) ---
        self.title_label = QLabel("VenomSketch Lab 🎨")
        self.title_label.setObjectName("mainHeaderTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(50)
        layout.addWidget(self.title_label)

        # --- Theme Toggle Button (Replicating EmoCare Toggle) ---
        # Initialize button with empty text; the correct symbol is set in set_dark_mode()
        self.dark_toggle = QPushButton("", self)
        self.dark_toggle.setObjectName("themeButtonCircle")
        self.dark_toggle.setFixedSize(QSize(40, 40))
        self.dark_toggle.clicked.connect(self.toggle_dark_mode)

        # --- Main Content Container (Below Header) ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 10, 15, 15)

        # Row 1: Prompt Input
        prompt_row = QHBoxLayout()
        prompt_row.addWidget(QLabel("Prompt:"))
        self.prompt_entry = QLineEdit()
        self.prompt_entry.setObjectName("promptInput")
        self.prompt_entry.setFont(self.placeholder_font)  # Use softer font for input/placeholder
        self.prompt_entry.setPlaceholderText("e.g., Draw flowchart for even/odd numbers")
        prompt_row.addWidget(self.prompt_entry, 1)

        self.generate_btn = QPushButton("🧠 Generate Diagram")
        self.generate_btn.setObjectName("generateButton")
        self.generate_btn.clicked.connect(self.generate_diagram)
        self.generate_btn.setFixedWidth(200)
        prompt_row.addWidget(self.generate_btn)
        content_layout.addLayout(prompt_row)

        # Row 2: Action Buttons
        action_row = QHBoxLayout()

        self.new_diagram_btn = QPushButton("➕ New Diagram")
        self.new_diagram_btn.setObjectName("actionButton")
        self.new_diagram_btn.clicked.connect(self.new_diagram)
        action_row.addWidget(self.new_diagram_btn)

        self.auto_btn = QPushButton("🔀 Auto-layout")
        self.auto_btn.setObjectName("actionButton")
        self.auto_btn.clicked.connect(self.apply_auto_layout)
        action_row.addWidget(self.auto_btn)

        self.log_toggle_main_btn = QPushButton("Toggle Log View (Visible)")
        self.log_toggle_main_btn.setObjectName("actionButton")
        self.log_toggle_main_btn.clicked.connect(self.toggle_current_log)
        action_row.addWidget(self.log_toggle_main_btn)

        self.save_png_btn = QPushButton("💾 Save PNG")
        self.save_png_btn.setObjectName("saveButton")
        self.save_png_btn.clicked.connect(self.save_png)
        action_row.addWidget(self.save_png_btn)

        self.save_svg_btn = QPushButton("💾 Save SVG")
        self.save_svg_btn.setObjectName("saveButton")
        self.save_svg_btn.clicked.connect(self.save_svg)
        action_row.addWidget(self.save_svg_btn)

        # New buttons for node adding
        node_button_row = QHBoxLayout()
        self.add_process_btn = QPushButton("Add Process")
        self.add_process_btn.setObjectName("nodeButton")
        self.add_process_btn.clicked.connect(lambda: self._add_node_ui("process", "Process"))
        node_button_row.addWidget(self.add_process_btn)

        self.add_decision_btn = QPushButton("Add Decision")
        self.add_decision_btn.setObjectName("nodeButton")
        self.add_decision_btn.clicked.connect(lambda: self._add_node_ui("decision", "Decision"))
        node_button_row.addWidget(self.add_decision_btn)

        self.add_io_btn = QPushButton("Add I/O")
        self.add_io_btn.setObjectName("nodeButton")
        self.add_io_btn.clicked.connect(lambda: self._add_node_ui("data", "Input/Output"))
        node_button_row.addWidget(self.add_io_btn)

        self.add_db_btn = QPushButton("Add Database")
        self.add_db_btn.setObjectName("nodeButton")
        self.add_db_btn.clicked.connect(lambda: self._add_node_ui("database", "Database"))
        node_button_row.addWidget(self.add_db_btn)

        self.add_term_btn = QPushButton("Add Terminator")
        self.add_term_btn.setObjectName("nodeButton")
        self.add_term_btn.clicked.connect(lambda: self._add_node_ui("terminator", "Terminator"))
        node_button_row.addWidget(self.add_term_btn)

        self.add_doc_btn = QPushButton("Add Document")
        self.add_doc_btn.setObjectName("nodeButton")
        self.add_doc_btn.clicked.connect(lambda: self._add_node_ui("document", "Document"))
        node_button_row.addWidget(self.add_doc_btn)

        # Add arrow mode toggle
        self.add_link_mode_btn = QPushButton("↗ Add Arrow (Off)")
        self.add_link_mode_btn.setObjectName("toggleButton")
        self.add_link_mode_btn.setCheckable(True)
        self.add_link_mode_btn.clicked.connect(self._toggle_add_link_mode_ui)
        node_button_row.addWidget(self.add_link_mode_btn)

        # Link style toggle
        self.toggle_curve_btn = QPushButton("Curved Links: ON")
        self.toggle_curve_btn.setObjectName("toggleButton")
        self.toggle_curve_btn.setCheckable(True)
        self.toggle_curve_btn.setChecked(True)
        self.toggle_curve_btn.clicked.connect(self._toggle_curve_ui)
        node_button_row.addWidget(self.toggle_curve_btn)

        # Add these horizontal groups to the content_layout
        content_layout.addLayout(action_row)
        content_layout.addLayout(node_button_row)

        # Row 3: Drag Hint
        drag_hint_row = QHBoxLayout()
        self.drag_hint = QLabel(
            "Drag node to move (Right-click menu). Drag EMPTY space to pan/shift the whole diagram.")
        self.drag_hint.setObjectName("hintLabel")
        drag_hint_row.addWidget(self.drag_hint)
        drag_hint_row.addStretch(1)
        content_layout.addLayout(drag_hint_row)

        # QTabWidget for diagrams (Takes remaining space)
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabs")
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab_by_index)
        self.tab_widget.currentChanged.connect(lambda: self.log_toggle_main_btn.setText(
            "Toggle Log View (Visible)" if self.current_tab() and self.current_tab().log_is_visible else "Toggle Log View (Hidden)"
        ))

        content_layout.addWidget(self.tab_widget, 1)

        layout.addWidget(content_widget)

        # Initial positioning of the toggle button (will be corrected by resizeEvent)
        self.dark_toggle.move(self.width() - 60, 5)

    # ---------- UI Helpers ----------
    def _add_node_ui(self, typ, label):
        canvas = self.current_canvas()
        if not canvas:
            QMessageBox.information(self, "No Canvas", "Open or create a diagram first.")
            return
        canvas.add_node_center(typ=typ, text=label)

    def _toggle_add_link_mode_ui(self):
        canvas = self.current_canvas()
        if not canvas:
            return
        on = self.add_link_mode_btn.isChecked()
        canvas.toggle_add_link_mode(on)
        self.add_link_mode_btn.setText("↗ Add Arrow (On)" if on else "↗ Add Arrow (Off)")

    def _toggle_curve_ui(self):
        canvas = self.current_canvas()
        if not canvas:
            return
        on = self.toggle_curve_btn.isChecked()
        canvas.set_curved_links(on)
        self.toggle_curve_btn.setText("Curved Links: ON" if on else "Curved Links: OFF")

    # ---------- Actions (Modified to use current_tab) ----------
    def set_dark_mode(self, on: bool):
        self.dark_mode = on

        # --- UPDATE: Change symbol based on current mode ---
        if on:
            # Currently in Dark Mode -> Button offers to switch to Light Mode (Sun)
            self.dark_toggle.setText("🌝")
        else:
            # Currently in Light Mode -> Button offers to switch to Dark Mode (Moon)
            self.dark_toggle.setText("🌚")
        # ---------------------------------------------------

        # Define EmoCare-style color palette
        PRIMARY_ACCENT = "#9B70FF"  # Violet/Purple (Used for buttons, borders, and the app name)
        # SECONDARY_ACCENT = "#00BFFF"  # Cyan/Blue

        if on:
            # --- DARK THEME (EmoCare Dark) ---
            SOFT_BACKGROUND = "#1A1523"
            PANEL_BACKGROUND = "#282038"
            TEXT_COLOR = "#EBE9F5"

            # Main Stylesheet
            self.setStyleSheet(f"""
                QMainWindow, QWidget {{ background: {SOFT_BACKGROUND}; color: {TEXT_COLOR}; }}

                #mainHeaderTitle {{
                    background-color: transparent;
                    color: {PRIMARY_ACCENT}; 
                    font-family: '{self.app_font.family()}', sans-serif;
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
                #themeButtonCircle:hover {{ background: #7F5EFA; }}

                QTabBar::tab {{
                    background: #352D45;
                    color: {TEXT_COLOR}; padding: 12px 30px; margin: 2px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 14px;
                }}
                QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7F5EFA, stop:1 {PRIMARY_ACCENT});
                    color: white;
                }}
                QTabWidget::pane {{ border: 1px solid {PRIMARY_ACCENT}; background: {PANEL_BACKGROUND}; }}

                QLineEdit, QPlainTextEdit, #promptInput {{
                    background: #352D45;
                    color: {TEXT_COLOR};
                    border: 1px solid #453A5A;
                    border-radius: 8px;
                    padding: 8px;
                    /* Placeholder styling for QLineEdit/QPlainTextEdit */
                    font-family: 'Arial';
                    font-size: 11pt;
                    color: #AAAAAA; 
                }}
                /* Set input text color back to main color */
                #promptInput {{ color: {TEXT_COLOR}; }}


                #generateButton, #actionButton, #saveButton {{
                    background: {PRIMARY_ACCENT};
                    color: white; border: none; padding: 10px 15px; border-radius: 20px; font-weight: bold; font-size: 13px;
                }}
                #generateButton:hover, #actionButton:hover, #saveButton:hover {{ background: #7F5EFA; }}

                #nodeButton, #toggleButton {{
                    background-color: {PANEL_BACKGROUND};
                    color: {PRIMARY_ACCENT};
                    border: 2px solid {PRIMARY_ACCENT};
                    padding: 8px 15px;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 13px;
                }}
                #nodeButton:hover, #toggleButton:hover {{ background-color: #352D45; }}

                QLabel#log_label {{ color: {PRIMARY_ACCENT}; font-weight: bold; }}
                #hintLabel {{ color: #AAAAAA; font-style: italic; }}

                QSplitter::handle {{ background: #453A5A; }}
            """)
        else:
            # --- LIGHT THEME (EmoCare Light) ---
            SOFT_BACKGROUND = "#F5F6FA"
            PANEL_BACKGROUND = "#FFFFFF"
            TEXT_COLOR = "#2F2F4F"

            # Main Stylesheet
            self.setStyleSheet(f"""
                QMainWindow, QWidget {{ background: {SOFT_BACKGROUND}; color: {TEXT_COLOR}; }}

                #mainHeaderTitle {{
                    background-color: transparent;
                    color: {PRIMARY_ACCENT}; 
                    font-family: '{self.app_font.family()}', sans-serif;
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
                #themeButtonCircle:hover {{ background: #9B70FF; }}

                QTabBar::tab {{
                    background: #EBE9F5;
                    color: {TEXT_COLOR}; padding: 12px 30px; margin: 2px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 14px;
                }}
                QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PRIMARY_ACCENT}AA, stop:1 {PRIMARY_ACCENT});
                    color: white;
                }}
                QTabWidget::pane {{ border: 1px solid #EBE9F5; background: {PANEL_BACKGROUND}; }}

                QLineEdit, QPlainTextEdit, #promptInput {{
                    background: {PANEL_BACKGROUND};
                    color: {TEXT_COLOR};
                    border: 1px solid #CCC;
                    border-radius: 8px;
                    padding: 8px;
                    /* Placeholder styling for QLineEdit/QPlainTextEdit */
                    font-family: 'Arial';
                    font-size: 11pt;
                    color: #999999;
                }}
                /* Set input text color back to main color */
                #promptInput {{ color: {TEXT_COLOR}; }}


                #generateButton, #actionButton, #saveButton {{
                    background: {PRIMARY_ACCENT};
                    color: white; border: none; padding: 10px 15px; border-radius: 20px; font-weight: bold; font-size: 13px;
                }}
                #generateButton:hover, #actionButton:hover, #saveButton:hover {{ background: #9B70FF; }}

                #nodeButton, #toggleButton {{
                    background-color: {PANEL_BACKGROUND};
                    color: {PRIMARY_ACCENT};
                    border: 2px solid {PRIMARY_ACCENT};
                    padding: 8px 15px;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 13px;
                }}
                #nodeButton:hover, #toggleButton:hover {{ background-color: #EBE9F5; }}

                QLabel#log_label {{ color: {PRIMARY_ACCENT}; font-weight: bold; }}
                #hintLabel {{ color: #555555; font-style: italic; }}

                QSplitter::handle {{ background: #E0E0E0; }}
            """)

        # Update all canvas objects
        for i in range(self.tab_widget.count()):
            tab_widget = self.tab_widget.widget(i)
            tab_widget.canvas.toggle_dark(on)

    def toggle_dark_mode(self):
        self.set_dark_mode(not self.dark_mode)

    def generate_diagram(self):
        prompt = self.prompt_entry.text().strip()
        current_tab_widget = self.current_tab()

        if not prompt or not current_tab_widget:
            QMessageBox.warning(self, "Input Required", "Please enter a prompt and ensure a diagram is open.")
            return
        if not GENAI_AVAILABLE:
            QMessageBox.warning(self, "Gemini SDK missing",
                                "google.generativeai is not installed. Install it or set up your SDK.")
            return

        self.generate_btn.setEnabled(False)
        current_tab_widget.output.setPlainText("Generating...")

        worker = GeminiWorker(prompt, GEMINI_API_KEY, LLM_MODEL, DIAGRAM_SCHEMA, current_tab_widget)
        worker.signals.result.connect(self._on_generation_success)
        worker.signals.error.connect(self._on_generation_error)
        worker.signals.finished.connect(lambda: self.generate_btn.setEnabled(True))
        self.threadpool.start(worker)

    @pyqtSlot(dict, QWidget)
    def _on_generation_success(self, data, target_tab_widget: 'DiagramTabWidget'):
        target_tab_widget.diagram = data
        # Apply auto-layout to newly generated data, which also centers nodes if they lack coords
        auto_layout(target_tab_widget.diagram, iterations=300)
        # After layout, auto-create logical data flow links
        self._auto_create_flow_links(target_tab_widget.diagram)
        target_tab_widget.set_diagram_data(target_tab_widget.diagram)

    @pyqtSlot(str, QWidget)
    def _on_generation_error(self, err, target_tab_widget: 'DiagramTabWidget'):
        target_tab_widget.output.setPlainText("ERROR:\n" + str(err))
        # Clear canvas but keep the empty structure
        if target_tab_widget.diagram is None:
            target_tab_widget.set_diagram_data(target_tab_widget._get_empty_diagram("Error"))

    def apply_auto_layout(self):
        diagram = self.current_diagram()
        if not diagram:
            QMessageBox.information(self, "Nothing to layout", "Generate a diagram first.")
            return
        auto_layout(diagram, iterations=300)  # Using aggressive iteration count
        self.current_tab().set_diagram_data(diagram)

    def save_png(self):
        canvas = self.current_canvas()
        if not self.current_diagram():
            QMessageBox.information(self, "Nothing to save", "Generate a diagram first.")
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save Diagram as PNG", "diagram.png", "PNG Files (*.png)")
        if not fname:
            return
        # Render the canvas into a QPixmap using painter (reliable)
        pix = QPixmap(canvas.size())
        # Ensure the canvas background color is used for the pixmap
        if self.dark_mode:
            pix.fill(QColor(26, 26, 26))
        else:
            pix.fill(QColor(244, 244, 244))

        painter = QPainter(pix)
        canvas.render(painter)  # Use current canvas
        painter.end()
        saved = pix.save(fname, "PNG")
        if saved:
            QMessageBox.information(self, "Saved", f"Saved PNG to: {fname}")
        else:
            QMessageBox.warning(self, "Save failed", f"Failed to save PNG to: {fname}")

    def save_svg(self):
        canvas = self.current_canvas()
        if not self.current_diagram():
            QMessageBox.information(self, "Nothing to save", "Generate a diagram first.")
            return
        if not SVG_AVAILABLE:
            QMessageBox.warning(self, "SVG unsupported", "PyQt6.QtSvg not available. Saving PNG instead.")
            self.save_png()
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save Diagram as SVG", "diagram.svg", "SVG Files (*.svg)")
        if not fname:
            return
        # Use QSvgGenerator
        gen = QSvgGenerator()
        gen.setFileName(fname)
        gen.setSize(canvas.size())
        gen.setViewBox(canvas.rect())
        gen.setTitle("VenomSketch Diagram")
        painter = QPainter()
        painter.begin(gen)
        canvas.render(painter)  # Use current canvas
        painter.end()
        QMessageBox.information(self, "Saved", f"Saved SVG to: {fname}")

    # ---------- Auto data-flow heuristics ----------
    def _auto_create_flow_links(self, diagram):
        """
        Simple heuristic to create data flow arrows automatically:
        - Sort nodes by x then y and connect sequentially
        - For decision nodes, attempt to connect to two nearest nodes on the right
        - Prevent duplicates
        """
        if not diagram:
            return
        nodes = diagram.get('nodes', [])
        if not nodes:
            diagram['links'] = []
            return
        # Map nodes by id for quick access
        node_map = {n['id']: n for n in nodes}
        # Sort nodes left->right then top->bottom
        sorted_nodes = sorted(nodes, key=lambda n: (n.get('x', 500), n.get('y', 500)))
        links = diagram.setdefault('links', [])

        def exists(f, t):
            return any(l for l in links if l.get('from') == f and l.get('to') == t)

        # Connect sequentially
        for i in range(len(sorted_nodes) - 1):
            a = sorted_nodes[i]
            b = sorted_nodes[i + 1]
            if not exists(a['id'], b['id']):
                links.append({'from': a['id'], 'to': b['id'], 'label': ''})

        # For decision nodes, connect to two nearest nodes to the right (if available)
        for i, n in enumerate(sorted_nodes):
            typ = n.get('type', '').lower()
            if typ in ['decision', 'rhombus', 'diamond'] or any(
                    k in n.get('text', '').lower() for k in ['?', 'if', 'decision', 'loop']):
                # find up to two nodes whose x > n.x
                right_nodes = [m for m in sorted_nodes if m['x'] > n['x']]
                # choose two closest by x distance then y distance
                right_nodes = sorted(right_nodes, key=lambda m: (m['x'] - n['x'], abs(m['y'] - n['y'])))
                for target in right_nodes[:2]:
                    if not exists(n['id'], target['id']):
                        links.append({'from': n['id'], 'to': target['id'], 'label': ''})

        # remove obvious duplicates (safety)
        unique = []
        seen = set()
        for l in links:
            key = (l.get('from'), l.get('to'))
            if key not in seen:
                unique.append(l)
                seen.add(key)
        diagram['links'] = unique


# ---------------- Run ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VenomSketchApp()
    win.show()
    sys.exit(app.exec())
