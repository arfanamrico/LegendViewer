# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QAction,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem
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

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            QWidget{
                background:white;
                border:1px solid gray;
                border-radius:6px;
            }
        """)

        self.resize(300, 400)
        self.setMinimumSize(180, 150)

        # =========================
        # MAIN
        # =========================
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(4,4,4,4)
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
        h.setContentsMargins(6,4,4,4)

        self.label_title = QLabel("Legend Viewer")
        self.label_title.setStyleSheet("""
            QLabel{
                border:none;
                background:transparent;
                font-weight:bold;
                font-size:13px;
            }
        """)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20,20)
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
        h.addWidget(self.btn_close)

        self.layout_main.addWidget(self.header)

        # =========================
        # LIST
        # =========================
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget{
                border:none;
                background:white;
            }
            QListWidget::item{
                height:24px;
                padding-left:4px;
            }
        """)
        self.layout_main.addWidget(self.list_widget)

        # =========================
        # RESIZE HANDLE
        # =========================
        b = QHBoxLayout()
        b.addStretch()

        self.resize_handle = QLabel("◢")
        self.resize_handle.setFixedSize(18,18)
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

        # resize
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

        # drag
        if self.header.geometry().contains(event.pos()):

            newPos = event.globalPos() - self.dragPos
            parent_rect = self.parent().rect()

            x = max(
                0,
                min(newPos.x(), parent_rect.width() - self.width())
            )

            y = max(
                0,
                min(newPos.y(), parent_rect.height() - self.height())
            )

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

        # =====================================
        # Categorized Renderer
        # =====================================
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

        # =====================================
        # Graduated Renderer
        # =====================================
        try:
            ranges = renderer.ranges()

            if ranges and idx < len(ranges):

                r = ranges[idx]

                low = r.lowerValue()
                high = r.upperValue()

                # class qgis default:
                # lower inclusive, upper exclusive
                expr = (
                    f'"{class_field}" >= {low} '
                    f'AND "{class_field}" < {high}'
                )

                req = QgsFeatureRequest().setFilterExpression(expr)

                return sum(1 for _ in layer.getFeatures(req))
        except:
            pass

        # =====================================
        # Rule Based
        # =====================================
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

        # fallback
        return layer.featureCount()

    # ======================================================
    # MULTI LEGEND
    # ======================================================
    def update_legend_multi(self, layers):

        self.list_widget.clear()

        self.label_title.setText("Legend") # f"{len(layers)} Layers"

        for layer in layers:

            sep = QListWidgetItem(f"{layer.name()}") #◆ 
            f = sep.font()
            f.setBold(True)
            sep.setFont(f)
            self.list_widget.addItem(sep)

            renderer = layer.renderer()
            if not renderer:
                continue

            try:
                items = renderer.legendSymbolItems()
            except:
                continue

            for idx, item in enumerate(items):

                try:
                    symbol = item.symbol()
                    img = symbol.asImage(QSize(16,16))
                    pix = QPixmap.fromImage(img)
                    icon = QIcon(pix)
                except:
                    icon = QIcon()

                count = self.get_count(layer, renderer, idx)
                txt = f"   {item.label()} ({count})"

                qitem = QListWidgetItem(icon, txt)
                self.list_widget.addItem(qitem)


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

        self.overlay.move(20,20)
        self.overlay.show()
        self.overlay.raise_()

        self.overlay.update_legend_multi(layers)
