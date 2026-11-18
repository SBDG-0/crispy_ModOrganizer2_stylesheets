"""Icon-only bridges for MO2 shortcut, missing tool-plugin, download and Nexus tab icons."""
from PyQt6.QtCore import QEvent, QObject, Qt, qWarning
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (QApplication, QPushButton, QStyledItemDelegate,
                             QTabWidget, QToolButton, QTreeView)
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


DOWNLOAD_WARNING_NAME = "actionMO2IconsDownloadWarning"
NEXUS_TAB_NAME = "actionMO2IconsNexusTab"


class DownloadWarningDelegate(QStyledItemDelegate):
    """Swap the built-in 'no metadata' warning icon for the QSS-supplied one."""
    def __init__(self, window, view):
        super().__init__(view)
        self.window = window
        self.icon = None
        self.resolved = False

    def invalidate(self):
        self.resolved = False

    def resolve(self):
        proxy = QToolButton()
        proxy.setObjectName(DOWNLOAD_WARNING_NAME)
        self.window.style().polish(proxy)
        self.icon = proxy.icon()
        self.resolved = True
        proxy.deleteLater()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Only rows with incomplete metadata carry a decoration icon.
        deco = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(deco, QIcon) or deco.isNull():
            return
        if not self.resolved:
            self.resolve()
        if self.icon is not None and not self.icon.isNull():
            option.icon = self.icon


class DownloadIconBridge(QObject):
    """Let QSS replace the warning icon on downloads without metadata."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = None
        self.delegate = None
        view = window.findChild(QTreeView, "downloadView")
        if view is None:
            for candidate in window.findChildren(QTreeView):
                if candidate.metaObject().className() == "DownloadListView":
                    view = candidate
                    break
        if view is None:
            qWarning("MO2 Icons Menu: downloads view not found")
            return
        if view.itemDelegateForColumn(0) is not None:
            qWarning("MO2 Icons Menu: downloads Name column already has a delegate; skipping")
            return
        self.view = view
        self.delegate = DownloadWarningDelegate(window, view)
        view.setItemDelegateForColumn(0, self.delegate)
        # Re-read the icon when the stylesheet changes.
        window.installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.delegate is not None and event.type() == QEvent.Type.StyleChange:
            self.delegate.invalidate()
            self.view.viewport().update()
        return False


class ModInfoTabBridge(QObject):
    """Let QSS replace the Nexus Info tab icon; the dialog is created on demand."""
    def __init__(self, window):
        super().__init__(window)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.Show and obj.isWidgetType()
                and obj.objectName() == "ModInfoDialog"):
            self.apply_icon(obj)
        return False

    def apply_icon(self, dialog):
        tabs = dialog.findChild(QTabWidget)
        if tabs is None:
            return
        target = -1
        for i in range(tabs.count()):
            if tabs.widget(i).objectName() == "tabNexus":
                target = i
                break
        if target < 0:
            # Fallback: the Nexus tab is the only one with a built-in icon.
            with_icon = [i for i in range(tabs.count())
                         if not tabs.tabIcon(i).isNull()]
            if len(with_icon) == 1:
                target = with_icon[0]
        if target < 0:
            qWarning("MO2 Icons Menu: Nexus Info tab not found")
            return
        proxy = QToolButton()
        proxy.setObjectName(NEXUS_TAB_NAME)
        dialog.style().polish(proxy)
        icon = proxy.icon()
        proxy.deleteLater()
        if not icon.isNull():
            tabs.setTabIcon(target, icon)


class MO2IconsMenu(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self.bridge = None
        self.tool_bridge = None
        self.download_bridge = None
        self.modinfo_bridge = None

    def init(self, organizer):
        organizer.onUserInterfaceInitialized(self._ui_ready)
        return True

    def _ui_ready(self, window):
        if self.bridge is None:
            self.bridge = ShortcutIconBridge(window)
            self.tool_bridge = ToolIconBridge(window)
            self.download_bridge = DownloadIconBridge(window)
            self.modinfo_bridge = ModInfoTabBridge(window)

    def name(self):
        return "MO2 Icons Menu"

    def localizedName(self):
        return self.name()

    def author(self):
        return "SavageBulldogOG"

    def description(self):
        return "Allows icon-set QSS to style Shortcut dropdowns and fill missing tool-plugin menu icons, and style the downloads warning and Nexus Info tab icons."

    def version(self):
        return mobase.VersionInfo(1, 2, 0)

    def settings(self):
        return []


def createPlugin():
    return MO2IconsMenu()
