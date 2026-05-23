# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QAction,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QGridLayout,
    QSizePolicy,
    QButtonGroup
)
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtCore import Qt, QSize, QPoint
from qgis.core import QgsFeatureRequest
import os


# ==========================================================
# LEGEND OVERLAY
# ==========================================================
class LegendOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dragPos = QPoint()
        self.resizing = False
        self.resize_start_pos = QPoint()
        self.resize_start_size = self.size()
        self.num_columns = 2
        self._last_layers = []

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            QWidget{
                background:white;
                border:1px solid gray;
                border-radius:6px;
            }
        """)

        self.resize(400, 400)
        self.setMinimumSize(180, 150)

        # =========================
        # MAIN
        # =========================
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(4, 4, 4, 4)
        self.layout_main.setSpacing(2)

        # =========================
        # HEADER
        # =========================
        self.header = QWidget()
        self.header.setStyleSheet("""
            background:#dfe6e9;
            border-radius:4px;
        """)

        h = QHBoxLayout(self.header)
        h.setContentsMargins(6, 4, 4, 4)

        self.label_title = QLabel("Legend")
        self.label_title.setStyleSheet("""
            QLabel{
                border:none;
                background:transparent;
                font-weight:bold;
                font-size:13px;
            }
        """)

        # =========================
        # TOMBOL PILIHAN KOLOM
        # =========================
        self.col_btn_group = QButtonGroup(self)
        self.col_btn_group.setExclusive(True)

        col_widget = QWidget()
        col_widget.setStyleSheet("background:transparent; border:none;")
        col_layout = QHBoxLayout(col_widget)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(2)

        btn_style_active = """
            QPushButton{
                background:#2980b9;
                color:white;
                border:none;
                border-radius:3px;
                font-size:10px;
                font-weight:bold;
                padding:2px 5px;
            }
        """
        btn_style_inactive = """
            QPushButton{
                background:#bdc3c7;
                color:#2c3e50;
                border:none;
                border-radius:3px;
                font-size:10px;
                padding:2px 5px;
            }
            QPushButton:hover{
                background:#95a5a6;
            }
        """

        for i, label in enumerate(["1", "2", "3", "4"]):
            btn = QPushButton(label)
            btn.setFixedSize(22, 20)
            btn.setCheckable(True)
            btn.setStyleSheet(
                btn_style_active if i + 1 == self.num_columns else btn_style_inactive
            )
            btn.clicked.connect(
                lambda checked, n=i + 1,
                ba=btn_style_active,
                bi=btn_style_inactive: self.on_col_changed(n, ba, bi)
            )
            self.col_btn_group.addButton(btn, i + 1)
            col_layout.addWidget(btn)

        # Set tombol default aktif (kolom 2)
        self.col_btn_group.button(self.num_columns).setChecked(True)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet("""
            QPushButton{
                background:#e74c3c;
                color:white;
                border:none;
                border-radius:3px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#c0392b;
            }
        """)
        self.btn_close.clicked.connect(self.close)

        h.addWidget(self.label_title)
        h.addStretch()
        h.addWidget(col_widget)
        h.addSpacing(6)
        h.addWidget(self.btn_close)

        self.layout_main.addWidget(self.header)

        # =========================
        # SCROLL AREA + GRID
        # =========================
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                outline: none;
                background: white;
            }
            QWidget {
                border: none;
                outline: none;
            }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background:white;border:none;") ## bagian ini 

        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setHorizontalSpacing(12)
        self.grid_layout.setVerticalSpacing(2)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.scroll_content)
        self.layout_main.addWidget(self.scroll_area)

        # =========================
        # RESIZE HANDLE
        # =========================
        b = QHBoxLayout()
        b.addStretch()

        self.resize_handle = QLabel("◢")
        self.resize_handle.setFixedSize(18, 18)
        self.resize_handle.setAlignment(Qt.AlignCenter)
        self.resize_handle.setCursor(Qt.SizeFDiagCursor)
        self.resize_handle.setStyleSheet("""
            QLabel{
                border:none;
                color:gray;
                font-size:14px;
            }
        """)

        b.addWidget(self.resize_handle)
        self.layout_main.addLayout(b)

    # ======================================================
    # GANTI KOLOM
    # ======================================================
    def on_col_changed(self, n, btn_style_active, btn_style_inactive):

        self.num_columns = n

        # Update warna semua tombol
        for i in range(1, 5):
            btn = self.col_btn_group.button(i)
            if btn:
                btn.setStyleSheet(
                    btn_style_active if i == n else btn_style_inactive
                )

        # Refresh legend dengan kolom baru
        if self._last_layers:
            self.update_legend_multi(self._last_layers)

    # ======================================================
    # DRAG / RESIZE
    # ======================================================
    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:

            if self.resize_handle.geometry().contains(event.pos()):
                self.resizing = True
                self.resize_start_pos = event.globalPos()
                self.resize_start_size = self.size()
                event.accept()
                return

            if self.header.geometry().contains(event.pos()):
                self.dragPos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):

        if not (event.buttons() & Qt.LeftButton):
            return

        if self.resizing:

            delta = event.globalPos() - self.resize_start_pos

            new_w = max(
                self.minimumWidth(),
                self.resize_start_size.width() + delta.x()
            )

            new_h = max(
                self.minimumHeight(),
                self.resize_start_size.height() + delta.y()
            )

            parent_rect = self.parent().rect()
            new_w = min(new_w, parent_rect.width() - self.x())
            new_h = min(new_h, parent_rect.height() - self.y())

            self.resize(new_w, new_h)
            event.accept()
            return

        if self.header.geometry().contains(event.pos()):

            newPos = event.globalPos() - self.dragPos
            parent_rect = self.parent().rect()

            x = max(0, min(newPos.x(), parent_rect.width() - self.width()))
            y = max(0, min(newPos.y(), parent_rect.height() - self.height()))

            self.move(x, y)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.resizing = False

    # ======================================================
    # COUNT FEATURE
    # ======================================================
    def get_count(self, layer, renderer, idx):

        class_field = None

        if hasattr(renderer, "classAttribute"):
            try:
                class_field = renderer.classAttribute()
            except:
                pass

        # Categorized
        try:
            categories = renderer.categories()
            if categories and idx < len(categories):
                val = categories[idx].value()
                if isinstance(val, str):
                    expr = f'"{class_field}" = \'{val}\''
                else:
                    expr = f'"{class_field}" = {val}'
                req = QgsFeatureRequest().setFilterExpression(expr)
                return sum(1 for _ in layer.getFeatures(req))
        except:
            pass

        # Graduated
        try:
            ranges = renderer.ranges()
            if ranges and idx < len(ranges):
                r = ranges[idx]
                low = r.lowerValue()
                high = r.upperValue()
                expr = (
                    f'"{class_field}" >= {low} '
                    f'AND "{class_field}" < {high}'
                )
                req = QgsFeatureRequest().setFilterExpression(expr)
                return sum(1 for _ in layer.getFeatures(req))
        except:
            pass

        # Rule Based
        try:
            root = renderer.rootRule()
            rules = root.children()
            if rules and idx < len(rules):
                rule = rules[idx]
                expr = rule.filterExpression()
                req = QgsFeatureRequest().setFilterExpression(expr)
                return sum(1 for _ in layer.getFeatures(req))
        except:
            pass

        return layer.featureCount()

    # ======================================================
    # MULTI LEGEND
    # ======================================================
    def update_legend_multi(self, layers):

        self._last_layers = layers

        # Bersihkan grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.label_title.setText("Legend")

        row = 0

        for layer in layers:

            # Header nama layer
            sep = QLabel(f"<b>{layer.name()}</b>")
            sep.setStyleSheet("""
                QLabel {
                    background: #f0f0f0;
                    border-radius: 3px;
                    padding: 2px 4px;
                    font-size: 11px;
                }
            """)
            sep.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.grid_layout.addWidget(sep, row, 0, 1, self.num_columns)
            row += 1

            renderer = layer.renderer()
            if not renderer:
                continue

            try:
                items = renderer.legendSymbolItems()
            except:
                continue

            col = 0

            for idx, item in enumerate(items):

                try:
                    symbol = item.symbol()
                    img = symbol.asImage(QSize(14, 14))
                    pix = QPixmap.fromImage(img)
                except:
                    pix = QPixmap(14, 14)
                    pix.fill(Qt.transparent)

                count = self.get_count(layer, renderer, idx)

                cell = QWidget()
                cell.setStyleSheet("background:transparent;border:none; outline:none;") ### bagian ini
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(2, 1, 2, 1)
                cell_layout.setSpacing(4)

                icon_label = QLabel()
                icon_label.setPixmap(pix)
                icon_label.setFixedSize(14, 14)
                icon_label.setStyleSheet("background:transparent; border:none;")

                text_label = QLabel(f"{item.label()} ({count})")
                text_label.setStyleSheet("""
                    QLabel {
                        background: transparent;
                        border: none;
                        font-size: 10px;
                    }
                """)
                text_label.setWordWrap(False)

                cell_layout.addWidget(icon_label)
                cell_layout.addWidget(text_label)
                cell_layout.addStretch()

                self.grid_layout.addWidget(cell, row, col)

                col += 1
                if col >= self.num_columns:
                    col = 0
                    row += 1

            if col != 0:
                row += 1


# ==========================================================
# MAIN PLUGIN
# ==========================================================
class LegendViewerPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.overlay = None

        self.plugin_dir = os.path.dirname(__file__)
        self.icon_path = os.path.join(self.plugin_dir, "icon.png")

    def initGui(self):

        self.action = QAction(
            QIcon(self.icon_path),
            "Legend Viewer",
            self.iface.mainWindow()
        )

        self.action.triggered.connect(self.show_legend)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Legend Viewer", self.action)

        self.iface.layerTreeView().selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )

    def unload(self):

        try:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("Legend Viewer", self.action)
        except:
            pass

        if self.overlay:
            self.overlay.close()
            self.overlay = None

    def on_selection_changed(self):

        if not self.overlay:
            return

        layers = self.iface.layerTreeView().selectedLayers()

        if layers:
            self.overlay.update_legend_multi(layers)

    def show_legend(self):

        layers = self.iface.layerTreeView().selectedLayers()

        if not layers:
            self.iface.messageBar().pushWarning(
                "Legend Viewer",
                "Tidak ada layer dipilih."
            )
            return

        if self.overlay:
            self.overlay.show()
            self.overlay.raise_()
            self.overlay.update_legend_multi(layers)
            return

        self.overlay = LegendOverlay(
            self.iface.mapCanvas()
        )

        self.overlay.move(20, 20)
        self.overlay.show()
        self.overlay.raise_()

        self.overlay.update_legend_multi(layers)
