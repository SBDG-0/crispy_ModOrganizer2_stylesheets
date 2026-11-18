"""Icon-only bridges for MO2 shortcut and missing tool-plugin icons."""
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QPushButton, QToolButton
import mobase


ACTION_NAMES = (
    "actionMO2IconsShortcutToolbar",
    "actionMO2IconsShortcutDesktop",
    "actionMO2IconsShortcutStartMenu",
)


class ShortcutIconBridge(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        button = window.findChild(QPushButton, "linkButton")
        self.menu = button.menu() if button else None
        self.originals = []
        if self.menu is None:
            return
        actions = [a for a in self.menu.actions() if not a.isSeparator()]
        # Fixed MO2 2.5.2 order; avoid text matching so translations still work.
        if len(actions) != len(ACTION_NAMES):
            self.menu = None
            return
        if any(a.objectName() and a.objectName() != n
               for a, n in zip(actions, ACTION_NAMES)):
            self.menu = None
            return
        for action, name in zip(actions, ACTION_NAMES):
            self.originals.append((action, action.icon()))
            action.setObjectName(name)
        self.menu.aboutToShow.connect(self.apply_icons)
        self.apply_icons()

    def apply_icons(self):
        for action, original in self.originals:
            # Same unparented proxy technique as MainWindow::resetActionIcons.
            proxy = QToolButton()
            proxy.setObjectName(action.objectName())
            self.window.style().polish(proxy)
            icon = proxy.icon()
            action.setIcon(original if icon.isNull() else icon)
            proxy.deleteLater()


class ToolIconBridge(QObject):
    """Supply QSS fallback icons only to empty tool-plugin menu entries."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        action = window.findChild(QAction, "actionTool")
        self.menu = action.menu() if action else None
        if self.menu is not None:
            self.menu.aboutToShow.connect(self.apply_icons)
            self.apply_icons()

    def apply_icons(self):
        if self.menu is not None:
            self._apply_menu(self.menu)

    def _apply_menu(self, menu):
        for action in menu.actions():
            if action.isSeparator():
                continue
            if action.menu() is not None:
                self._apply_menu(action.menu())
                continue
            icon = action.icon()
            ours = action.property("mo2IconsFallbackKey")
            # Respect a new icon supplied by a plugin after our last update.
            if not icon.isNull() and (not ours or str(icon.cacheKey()) != ours):
                action.setProperty("mo2IconsFallbackKey", None)
                continue
            label = action.text().replace("&", "").strip().casefold()
            names = {
                "bsa packer": "actionMO2IconsToolArchive",
                "loot paks": "actionMO2IconsToolSort",
                "plugin browser": "actionMO2IconsToolBrowse",
            }
            proxy = QToolButton()
            proxy.setObjectName(names.get(label, "actionMO2IconsToolFallback"))
            self.window.style().polish(proxy)
            replacement = proxy.icon()
            action.setIcon(replacement)
            action.setProperty("mo2IconsFallbackKey",
                               None if replacement.isNull() else str(replacement.cacheKey()))
            proxy.deleteLater()


class MO2IconsMenu(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self.bridge = None
        self.tool_bridge = None

    def init(self, organizer):
        organizer.onUserInterfaceInitialized(self._ui_ready)
        return True

    def _ui_ready(self, window):
        if self.bridge is None:
            self.bridge = ShortcutIconBridge(window)
            self.tool_bridge = ToolIconBridge(window)

    def name(self):
        return "MO2 Icons Menu"

    def localizedName(self):
        return self.name()

    def author(self):
        return "SavageBulldogOG"

    def description(self):
        return "Allows icon-set QSS to style Shortcut dropdowns and fill missing tool-plugin menu icons."

    def version(self):
        return mobase.VersionInfo(1, 1, 0)

    def settings(self):
        return []


def createPlugin():
    return MO2IconsMenu()
