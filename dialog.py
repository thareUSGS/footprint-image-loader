import os
from urllib.parse import urljoin, urlparse, quote

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QComboBox,
    QRadioButton, QButtonGroup, QLineEdit, QPushButton, QFileDialog, QLabel,
    QDialogButtonBox, QProgressBar
)

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer


class LiftDialog(QDialog):
    """
    Dialog to load rasters referenced by selected vector footprint features.
    Works with QGIS 3.x (Qt5) and QGIS 4.x (Qt6) via qgis.PyQt compatibility layer.
    """

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.settings = QSettings()
        self._cancel = False

        self.setWindowTitle("LIFT - Load Image From Footprint")
        self.resize(600, 350)

        # Determine QDialogButtonBox enum compatibility for Qt5 vs Qt6
        # Qt5: QDialogButtonBox.Close, QDialogButtonBox.ActionRole
        # Qt6: QDialogButtonBox.StandardButton.Close, QDialogButtonBox.ButtonRole.ActionRole
        if hasattr(QDialogButtonBox, "Close"):
            self._qb_close = QDialogButtonBox.Close
        else:
            self._qb_close = QDialogButtonBox.StandardButton.Close

        if hasattr(QDialogButtonBox, "ActionRole"):
            self._qb_action_role = QDialogButtonBox.ActionRole
        else:
            self._qb_action_role = QDialogButtonBox.ButtonRole.ActionRole

        self._build_ui()
        self._restore_settings()
        self.refresh_layers()

    # ----------------------------------------------------------------------
    # UI Construction
    # ----------------------------------------------------------------------
    def _build_ui(self):
        """Builds the full dialog layout and widgets."""

        main_layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- Layer selection ---
        self.layers = QComboBox()
        self.fields = QComboBox()
        self.layers.currentIndexChanged.connect(self._update_fields)

        form.addRow("Footprint layer:", self.layers)
        form.addRow("Filename or HTTPS field:", self.fields)

        # --- Source type (local vs HTTPS) ---
        source_row = QHBoxLayout()
        self.local = QRadioButton("Local")
        self.https = QRadioButton("HTTPS")

        source_group = QButtonGroup(self)
        source_group.addButton(self.local)
        source_group.addButton(self.https)

        source_row.addWidget(self.local)
        source_row.addWidget(self.https)
        source_row.addStretch()

        form.addRow("Image source:", source_row)

        # --- Local directory selection ---
        local_row = QHBoxLayout()
        self.local_path = QLineEdit()
        self.browse = QPushButton("Browse...")
        self.browse.clicked.connect(self._browse_local_dir)

        local_row.addWidget(self.local_path)
        local_row.addWidget(self.browse)

        form.addRow("Local image directory: [optional]", local_row)

        # --- HTTPS base URL ---
        self.https_base = QLineEdit()
        self.https_base.setPlaceholderText("https://example.com/imagery/")
        form.addRow("HTTPS base URL: [optional]", self.https_base)

        # --- Group name for loaded rasters ---
        self.group = QLineEdit("Selected Images")
        form.addRow("Group name for loaded images:", self.group)

        main_layout.addLayout(form)

        # --- Status + progress bar ---
        self.status = QLabel("Select footprints, then click Load Images.")
        self.status.setWordWrap(True)
        main_layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        main_layout.addWidget(self.progress)

        # --- Buttons ---
        # Use the computed enum values for Close and ActionRole so this works in Qt5 and Qt6
        button_box = QDialogButtonBox(self._qb_close)

        self.load = QPushButton("Load Images")
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)

        # addButton expects a ButtonRole value; use the compatibility value computed above
        button_box.addButton(self.load, self._qb_action_role)
        button_box.addButton(self.cancel, self._qb_action_role)

        self.load.clicked.connect(self.load_images)
        self.cancel.clicked.connect(self.cancel_loading)
        button_box.rejected.connect(self.close)

        main_layout.addWidget(button_box)

        # --- Source toggle behavior ---
        self.local.toggled.connect(self._update_source_mode)
        self.https.toggled.connect(self._update_source_mode)

    # ----------------------------------------------------------------------
    # Settings persistence
    # ----------------------------------------------------------------------
    def _restore_settings(self):
        """Restore saved settings from previous runs."""

        use_https = self.settings.value(
            "lift/source", self.settings.value("footprint_image_loader/source", "local")
        ) == "https"
        self.https.setChecked(use_https)
        self.local.setChecked(not use_https)

        self.local_path.setText(
            self.settings.value(
                "lift/local_dir", self.settings.value("footprint_image_loader/local_dir", "")
            )
        )
        self.https_base.setText(
            self.settings.value(
                "lift/https_base", self.settings.value("footprint_image_loader/https_base", "")
            )
        )
        self.group.setText(
            self.settings.value(
                "lift/group", self.settings.value("footprint_image_loader/group", "Selected Images")
            )
        )

        self._update_source_mode()

    def _save_settings(self):
        """Save current settings."""

        self.settings.setValue(
            "lift/source",
            "https" if self.https.isChecked() else "local"
        )
        self.settings.setValue(
            "lift/local_dir",
            self.local_path.text().strip()
        )
        self.settings.setValue(
            "lift/https_base",
            self.https_base.text().strip()
        )
        self.settings.setValue(
            "lift/group",
            self.group.text().strip()
        )

    # ----------------------------------------------------------------------
    # UI helpers
    # ----------------------------------------------------------------------
    def _update_source_mode(self):
        """Enable/disable widgets depending on Local vs HTTPS mode."""

        local_mode = self.local.isChecked()
        self.local_path.setEnabled(local_mode)
        self.browse.setEnabled(local_mode)
        self.https_base.setEnabled(not local_mode)

    def _browse_local_dir(self):
        """Open a directory picker for local image directory."""

        start_dir = self.local_path.text().strip() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Image Directory", start_dir)

        if directory:
            self.local_path.setText(directory)

    # ----------------------------------------------------------------------
    # Layer + field handling
    # ----------------------------------------------------------------------
    def refresh_layers(self):
        """Populate the layer dropdown with vector layers."""

        previous = self.layers.currentData()

        self.layers.blockSignals(True)
        self.layers.clear()

        vector_layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if isinstance(lyr, QgsVectorLayer)
        ]

        for lyr in vector_layers:
            self.layers.addItem(lyr.name(), lyr.id())

        active = self.iface.activeLayer()
        target_id = active.id() if isinstance(active, QgsVectorLayer) else previous

        index = self.layers.findData(target_id) if target_id else -1
        if index >= 0:
            self.layers.setCurrentIndex(index)

        self.layers.blockSignals(False)
        self._update_fields()

    def _layer(self):
        """Return the currently selected vector layer."""
        layer_id = self.layers.currentData()
        return QgsProject.instance().mapLayer(layer_id) if layer_id else None

    def _update_fields(self):
        """Populate the field dropdown based on selected layer."""

        self.fields.clear()
        layer = self._layer()

        if not layer:
            return

        for field in layer.fields():
            self.fields.addItem(field.name())

        # Qt5: Qt.MatchFixedString, Qt6: Qt.MatchFlag.MatchFixedString
        match_flag = getattr(Qt, "MatchFixedString", getattr(Qt, "MatchFlag", Qt).MatchFixedString)
        i = self.fields.findText("filename", match_flag)
        if i >= 0:
            self.fields.setCurrentIndex(i)

    # ----------------------------------------------------------------------
    # Filename → path resolution
    # ----------------------------------------------------------------------
    def _local_src(self, name):
        """Resolve a filename to a local filesystem path."""

        name = os.path.expandvars(os.path.expanduser(name.strip()))

        if os.path.isabs(name):
            return os.path.normpath(name)

        base = self.local_path.text().strip()
        if not base:
            raise ValueError("Choose a local image directory.")

        return os.path.normpath(os.path.join(base, name))

    def _remote_src(self, name):
        """Resolve a filename to a HTTPS URL wrapped in /vsicurl/."""

        name = name.strip()
        parsed = urlparse(name)

        # If the field already contains a full URL
        if parsed.scheme in ("http", "https"):
            url = name
        else:
            base = self.https_base.text().strip()
            if not base.lower().startswith("https://"):
                raise ValueError("Enter an HTTPS base URL beginning with https://")

            url = urljoin(
                base.rstrip("/") + "/",
                quote(name.replace("\\", "/").lstrip("/"), safe="/:%?=&")
            )

        if not url.lower().startswith("https://"):
            raise ValueError("Only HTTPS URLs are supported in HTTPS mode.")

        return "/vsicurl/" + url

    # ----------------------------------------------------------------------
    # Loading workflow
    # ----------------------------------------------------------------------
    def cancel_loading(self):
        """User clicked Cancel — stop after current image."""
        self._cancel = True
        self.cancel.setEnabled(False)
        self.status.setText("Cancelling after the current image...")
        QApplication.processEvents()

    def _progress(self, i, total):
        """Update progress bar + status text."""
        self.progress.setValue(i)
        self.status.setText(f"Processing {i} of {total} image(s)...")
        QApplication.processEvents()

    def load_images(self):
        """Main loading loop: iterate selected features and load rasters."""

        layer = self._layer()
        field = self.fields.currentText()

        # --- Validation ---
        if not isinstance(layer, QgsVectorLayer) or not field:
            self.iface.messageBar().pushWarning(
                "LIFT - Load Image From Footprint",
                "Choose a footprint layer and filename field."
            )
            return

        features = layer.selectedFeatures()
        if not features:
            self.iface.messageBar().pushWarning(
                "LIFT - Load Image From Footprint",
                "Select one or more footprint features first."
            )
            return

        # --- Setup ---
        self._save_settings()
        self._cancel = False

        self.load.setEnabled(False)
        self.cancel.setEnabled(True)

        total = len(features)
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        QApplication.processEvents()

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        group_name = self.group.text().strip() or "Selected Images"
        grp = root.findGroup(group_name)
        if grp is None:
            grp = root.insertGroup(0, group_name)
        else:
            group_copy = grp.clone()
            grp.parent().removeChildNode(grp)
            root.insertChildNode(0, group_copy)
            grp = root.findGroup(group_name)

        existing_sources = {layer.source() for layer in project.mapLayers().values()}

        loaded = 0
        skipped = 0
        failed = []
        cancelled = False

        try:
            for i, feat in enumerate(features, 1):
                QApplication.processEvents()

                if self._cancel:
                    cancelled = True
                    break

                raw = feat[field]
                name = "" if raw is None else str(raw).strip()
                if not name:
                    failed.append("<empty filename>")
                    self._progress(i, total)
                    continue

                try:
                    src = self._remote_src(name) if self.https.isChecked() else self._local_src(name)
                except ValueError as e:
                    failed.append(f"{name}: {e}")
                    self._progress(i, total)
                    continue

                if src in existing_sources:
                    skipped += 1
                    self._progress(i, total)
                    continue

                if self.local.isChecked() and not os.path.isfile(src):
                    failed.append(name)
                    self._progress(i, total)
                    continue

                display_name = os.path.basename(urlparse(name).path) or name
                raster = QgsRasterLayer(src, os.path.splitext(display_name)[0], "gdal")
                if not raster.isValid():
                    failed.append(name)
                    self._progress(i, total)
                    continue

                project.addMapLayer(raster, False)
                grp.addLayer(raster)
                existing_sources.add(src)
                loaded += 1
                self._progress(i, total)
        finally:
            self.load.setEnabled(True)
            self.cancel.setEnabled(False)

        msg = ("Cancelled. " if cancelled else "") + f"Loaded {loaded} image(s); skipped {skipped} duplicate(s)."
        if failed:
            msg += f" {len(failed)} failed or missing."
        self.status.setText(msg + ("\n" + "\n".join(failed[:10]) if failed else ""))

        banner = (self.iface.messageBar().pushWarning if failed or cancelled else self.iface.messageBar().pushSuccess)
        banner("LIFT - Load Image From Footprint", msg)
