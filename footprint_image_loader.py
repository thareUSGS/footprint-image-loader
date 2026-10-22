from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from .dialog import FootprintImageLoaderDialog

class FootprintImageLoader:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(QIcon(), "Load Images from Footprints", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Footprint Image Loader", self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("&Footprint Image Loader", self.action)
            self.action = None

    def run(self):
        # Create dialog if needed
        if self.dialog is None:
            self.dialog = FootprintImageLoaderDialog(self.iface)

        # Refresh and show
        self.dialog.refresh_layers()
        self.dialog.show()

        # Call raise_() if available (Qt5), otherwise try any callable named "raise" via getattr
        raise_fn = getattr(self.dialog, "raise_", None)
        if callable(raise_fn):
            raise_fn()
        else:
            # Use getattr with string "raise" to avoid syntax error from using .raise
            alt_raise = getattr(self.dialog, "raise", None)
            if callable(alt_raise):
                alt_raise()

        # Activate window
        self.dialog.activateWindow()
