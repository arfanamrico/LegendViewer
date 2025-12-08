# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QAction, QDialog, QLabel, QVBoxLayout, QHBoxLayout
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtCore import Qt, QSize
from qgis.core import QgsProject, QgsFeatureRequest
import os


class LegendDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Legend: {layer.name()}")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(300, 380)

        self.layer = layer

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setSpacing(2)
        self.layout_main.setContentsMargins(6, 6, 6, 6)

        # Layer title
        self.label_title = QLabel(layer.name())
        self.label_title.setStyleSheet("font-size: 13px; font-weight: 600; margin-bottom: 6px;")
        self.layout_main.addWidget(self.label_title)

        # Container for legend rows
        self.legend_container = QVBoxLayout()
        self.legend_container.setSpacing(0)
        self.legend_container.setContentsMargins(0, 0, 0, 0)
        self.layout_main.addLayout(self.legend_container)

        self.update_legend(layer)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def _get_renderer_categories(self, renderer):
        return renderer.categories() if hasattr(renderer, "categories") else []

    def _get_renderer_ranges(self, renderer):
        return renderer.ranges() if hasattr(renderer, "ranges") else []

    def _get_rule_children(self, renderer):
        try:
            root = renderer.rootRule()
            return root.children() if root is not None else []
        except Exception:
            return []

    def _range_bounds(self, r):
        """
        Return (low, high) for a renderer range object, trying known attribute names.
        """
        # try common API names in different QGIS versions
        for low_name in ("lowerValue", "lowerBound", "minimumValue"):
            low = getattr(r, low_name, None)
            if callable(low):
                low = low()
            if low is not None:
                break
        else:
            low = None

        for high_name in ("upperValue", "upperBound", "maximumValue"):
            high = getattr(r, high_name, None)
            if callable(high):
                high = high()
            if high is not None:
                break
        else:
            high = None

        return low, high

    def update_legend(self, layer=None):
        if layer is None:
            layer = self.layer
        if layer is None:
            return

        self.layer = layer
        self.label_title.setText(layer.name())

        renderer = layer.renderer()
        if not renderer:
            self.clear_layout(self.legend_container)
            return

        # get legend items (symbols + label)
        # prefer legendItemsV2 if available? we keep legendSymbolItems for compatibility
        try:
            if hasattr(renderer, "legendItemsV2"):
                items = renderer.legendItemsV2()
            else:
                items = renderer.legendSymbolItems()
        except Exception:
            items = renderer.legendSymbolItems()

        # prepared helper lists
        categories = self._get_renderer_categories(renderer)
        ranges = self._get_renderer_ranges(renderer)
        rules = self._get_rule_children(renderer)

        class_field = None
        if hasattr(renderer, "classAttribute"):
            try:
                class_field = renderer.classAttribute()
            except Exception:
                class_field = None

        # Clear existing legend
        self.clear_layout(self.legend_container)

        for idx, item in enumerate(items):
            row = QHBoxLayout()
            row.setSpacing(0)
            row.setContentsMargins(0, 0, 0, 0)

            # Render symbol image (safe)
            try:
                symbol = item.symbol()
                img = symbol.asImage(QSize(14, 14))
                pix = QPixmap.fromImage(img)
            except Exception:
                pix = QPixmap()

            icon_label = QLabel()
            icon_label.setPixmap(pix)
            icon_label.setFixedSize(18, 18)
            icon_label.setAlignment(Qt.AlignCenter)
            row.addWidget(icon_label)

            base_label = item.label() or ""
            count = None

            # 1) Categorized renderer (use category.filterExpression() if available)
            if categories and idx < len(categories):
                cat = categories[idx]
                # prefer filterExpression if available
                filt = None
                try:
                    filt = cat.filterExpression() if hasattr(cat, "filterExpression") else None
                except Exception:
                    filt = None

                if filt:
                    try:
                        req = QgsFeatureRequest().setFilterExpression(filt)
                        count = sum(1 for _ in layer.getFeatures(req))
                    except Exception:
                        count = None
                else:
                    # fallback comparing attribute value
                    try:
                        val = cat.value() if hasattr(cat, "value") else None
                        if val is None:
                            # if label includes the value, try extract last token
                            val = base_label
                        expr = f'"{class_field}" = \'{val}\''
                        req = QgsFeatureRequest().setFilterExpression(expr)
                        count = sum(1 for _ in layer.getFeatures(req))
                    except Exception:
                        count = None

            # 2) Graduated renderer (use ranges list)
            elif ranges and idx < len(ranges) and class_field:
                rng = ranges[idx]
                low, high = self._range_bounds(rng)
                if low is not None and high is not None:
                    # build expression: >= low AND < high (mimic QGIS)
                    expr = f'"{class_field}" >= {low} AND "{class_field}" < {high}'
                    try:
                        req = QgsFeatureRequest().setFilterExpression(expr)
                        count = sum(1 for _ in layer.getFeatures(req))
                    except Exception:
                        count = None

            # 3) Rule-based renderer (match rule label and use its filter)
            elif rules:
                matched = None
                for r in rules:
                    try:
                        if r.label() == base_label:
                            matched = r
                            break
                    except Exception:
                        continue
                if matched:
                    try:
                        filt = matched.filterExpression()
                        req = QgsFeatureRequest().setFilterExpression(filt)
                        count = sum(1 for _ in layer.getFeatures(req))
                    except Exception:
                        count = None

            # 4) Fallback: total features
            if count is None:
                try:
                    count = layer.featureCount()
                except Exception:
                    count = 0

            # Compose final label with count (show 0 if none)
            final_label = f"{base_label}  ({count})"

            text_label = QLabel(final_label)
            text_label.setStyleSheet("font-size: 12px; margin-left: 6px; padding: 0px;")
            row.addWidget(text_label)
            row.addStretch()
            self.legend_container.addLayout(row)


class LegendViewerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

        self.plugin_dir = os.path.dirname(__file__)
        self.icon_path = os.path.join(self.plugin_dir, "icon.png")

    def initGui(self):
        icon = QIcon(self.icon_path)
        self.action = QAction(icon, "Legend Viewer", self.iface.mainWindow())
        self.action.triggered.connect(self.show_legend)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Legend Viewer", self.action)

        # Auto refresh when active layer changes
        self.iface.layerTreeView().currentLayerChanged.connect(self.on_layer_changed)

        # Auto refresh when new layers added (fix delete-all case)
        QgsProject.instance().layersAdded.connect(self.on_layers_added)

    def unload(self):
        try:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginToMenu("Legend Viewer", self.action)
        except Exception:
            pass

    def reset_dialog(self):
        self.dialog = None

    def on_layers_added(self, layers):
        if self.dialog and layers:
            self.dialog.update_legend(self.iface.activeLayer())

    def on_layer_changed(self, layer):
        if self.dialog and layer:
            self.dialog.update_legend(layer)

    def show_legend(self):
        layer = self.iface.activeLayer()
        if not layer:
            self.iface.messageBar().pushWarning("Legend Viewer", "Tidak ada layer aktif.")
            return

        if self.dialog:
            self.dialog.update_legend(layer)
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

        self.dialog = LegendDialog(layer)
        self.dialog.finished.connect(self.reset_dialog)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
