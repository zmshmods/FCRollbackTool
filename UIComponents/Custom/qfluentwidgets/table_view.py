# coding: utf-8
from typing import List, Union

from PySide6.QtCore import Qt, QMargins, QModelIndex, QItemSelectionModel, Property, QRectF, QEvent
from PySide6.QtGui import QHelpEvent, QPainter, QColor, QKeyEvent, QPalette, QBrush, QPen
from PySide6.QtWidgets import (QAbstractItemView, QStyledItemDelegate, QApplication, QStyleOptionViewItem,
                             QTableView, QTableWidget, QWidget, QTableWidgetItem, QStyle,
                             QStyleOptionButton)

from .check_box import CheckBoxIcon
from ...common.font import getFont
from ...common.color import autoFallbackThemeColor
from ...common.style_sheet import isDarkTheme, FluentStyleSheet, themeColor, setCustomStyleSheet
from .line_edit import LineEdit
from .scroll_bar import SmoothScrollDelegate
from .tool_tip import ItemViewToolTipDelegate, ItemViewToolTipType


class TableItemDelegate(QStyledItemDelegate):

    def __init__(self, parent: QTableView):
        super().__init__(parent)
        self.margin = 2
        self.hoverRow = -1
        self.pressedRow = -1
        self.selectedRows = set()
        self.lightCheckedColor = QColor()
        self.darkCheckedColor = QColor()
        self.customColors = { # FRT
            "selected": {"color": None, "alpha": None},
            "hover": {"color": None, "alpha": None},
            "alternate": {"color": None, "alpha": None},
            "pressed": {"color": None, "alpha": None}
        }
        self.priorityOrder = ["selected", "pressed", "hover", "alternate"]  # FRT
        self._showIndicator = True
        self._rowBorderRadius = 5

        if isinstance(parent, QTableView):
            self.tooltipDelegate = ItemViewToolTipDelegate(parent, 100, ItemViewToolTipType.TABLE)
        else:
            self.tooltipDelegate = ItemViewToolTipDelegate(parent, 100, ItemViewToolTipType.LIST)

    def setHoverRow(self, row: int):
        self.hoverRow = row

    def setPressedRow(self, row: int):
        self.pressedRow = row

    def setSelectedRows(self, indexes: List[QModelIndex]):
        self.selectedRows.clear()
        for index in indexes:
            self.selectedRows.add(index.row())
            if index.row() == self.pressedRow:
                self.pressedRow = -1

    def sizeHint(self, option, index):
        # increase original sizeHint to accommodate space needed for border
        size = super().sizeHint(option, index)
        size = size.grownBy(QMargins(0, self.margin, 0, self.margin))
        return size

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        lineEdit = LineEdit(parent)
        lineEdit.setProperty("transparent", False)
        lineEdit.setStyle(QApplication.style())
        lineEdit.setText(option.text)
        lineEdit.setClearButtonEnabled(True)
        return lineEdit

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        rect = option.rect
        y = rect.y() + (rect.height() - editor.height()) // 2
        x, w = max(8, rect.x()), rect.width()
        if index.column() == 0:
            w -= 8

        editor.setGeometry(x, y, w, rect.height())

    def setCheckedColor(self, light, dark):
        """ set the color of indicator in checked status

        Parameters
        ----------
        light, dark: str | QColor | Qt.GlobalColor
            color in light/dark theme mode
        """
        self.lightCheckedColor = QColor(light)
        self.darkCheckedColor = QColor(dark)
        self.parent().viewport().update()

    def _drawBackground(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """ draw row background """
        r = self._rowBorderRadius  # FRT
        if index.column() == 0:
            rect = option.rect.adjusted(4, 0, r + 1, 0)
            painter.drawRoundedRect(rect, r, r)
        elif index.column() == index.model().columnCount(index.parent()) - 1:
            rect = option.rect.adjusted(-r - 1, 0, -4, 0)
            painter.drawRoundedRect(rect, r, r)
        else:
            rect = option.rect.adjusted(-1, 0, 1, 0)
            painter.drawRect(rect)

    def _drawIndicator(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """ draw indicator """
        y, h = option.rect.y(), option.rect.height()
        ph = round(0.35*h if self.pressedRow == index.row() else 0.257*h)
        painter.setBrush(autoFallbackThemeColor(self.lightCheckedColor, self.darkCheckedColor))
        painter.drawRoundedRect(4, ph + y, 3, h - 2*ph, 1.5, 1.5)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)

        # font
        option.font = index.data(Qt.FontRole) or getFont(13)

        # text color
        textColor = Qt.white if isDarkTheme() else Qt.black
        textBrush = index.data(Qt.ForegroundRole)   # type: QBrush
        if textBrush is not None:
            textColor = textBrush.color()

        option.palette.setColor(QPalette.Text, textColor)
        option.palette.setColor(QPalette.HighlightedText, textColor)

    # FRT
    def setSelectedRowColor(self, color: Union[str, QColor, Qt.GlobalColor], alpha: int = None):
        """Set the color and optional alpha for selected rows."""
        self.customColors["selected"]["color"] = QColor(color) if color else None
        self.customColors["selected"]["alpha"] = alpha if alpha is not None else None
        self.parent().viewport().update()

    def setHoverRowColor(self, color: Union[str, QColor, Qt.GlobalColor], alpha: int = None):
        """Set the color and optional alpha for hover rows."""
        self.customColors["hover"]["color"] = QColor(color) if color else None
        self.customColors["hover"]["alpha"] = alpha if alpha is not None else None
        self.parent().viewport().update()

    def setPressedRowColor(self, color: Union[str, QColor, Qt.GlobalColor], alpha: int = None):
        """Set the color and optional alpha for pressed rows."""
        self.customColors["pressed"]["color"] = QColor(color) if color else None
        self.customColors["pressed"]["alpha"] = alpha if alpha is not None else None
        self.parent().viewport().update()

    def setAlternateRowColor(self, color: Union[str, QColor, Qt.GlobalColor], alpha: int = None):
        """Set the color and optional alpha for alternate rows."""
        self.customColors["alternate"]["color"] = QColor(color) if color else None
        self.customColors["alternate"]["alpha"] = alpha if alpha is not None else None
        self.parent().viewport().update()

    def setPriorityOrder(self, order: List[str]):
        """Set the priority order for row states (selected, pressed, hover, alternate)."""
        valid_states = {"selected", "pressed", "hover", "alternate"}
        # Validate the provided order
        if set(order) == valid_states and len(order) == 4:
            self.priorityOrder = order
            self.parent().viewport().update()
        else:
            raise ValueError("Order must contain exactly 'selected', 'pressed', 'hover', and 'alternate'")
        
    def setShowIndicator(self, show: bool):
            """Set whether to show the indicator for selected rows."""
            self._showIndicator = show
            self.parent().viewport().update()

    def showIndicator(self) -> bool:
        """Return whether the indicator is shown for selected rows."""
        return self._showIndicator
    showIndicator = Property(bool, showIndicator, setShowIndicator)

    def setRowBorderRadius(self, radius: int):
        """Set the border radius for row background."""
        self._rowBorderRadius = max(0, radius)
        self.parent().viewport().update()
        
    # FRT
    def paint(self, painter, option, index):
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing)

        # set clipping rect of painter to avoid painting outside the borders
        painter.setClipping(True)
        painter.setClipRect(option.rect)

        # call original paint method where option.rect is adjusted to account for border
        option.rect.adjust(0, self.margin, 0, -self.margin)

        # draw highlight background
        isHover = self.hoverRow == index.row()
        isPressed = self.pressedRow == index.row()
        isAlternate = index.row() % 2 == 0 and self.parent().alternatingRowColors()
        isDark = isDarkTheme()

        c = 255 if isDark else 0
        alpha = 0
        applied_state = None

        # Apply states based on priority order
        for state in self.priorityOrder:
            if state == "selected" and index.row() in self.selectedRows:
                if isPressed and "pressed" in self.priorityOrder and self.priorityOrder.index("pressed") < self.priorityOrder.index("selected"):
                    alpha = 15 if self.customColors["pressed"]["alpha"] is None else self.customColors["pressed"]["alpha"]
                else:
                    alpha = 17 if self.customColors["selected"]["alpha"] is None else self.customColors["selected"]["alpha"]
                applied_state = "selected"
                break
            elif state == "pressed" and isPressed:
                alpha = 9 if self.customColors["pressed"]["alpha"] is None else self.customColors["pressed"]["alpha"]
                applied_state = "pressed"
                break
            elif state == "hover" and isHover and not index.row() in self.selectedRows:
                alpha = 12 if self.customColors["hover"]["alpha"] is None else self.customColors["hover"]["alpha"]
                applied_state = "hover"
                break
            elif state == "alternate" and isAlternate and not index.row() in self.selectedRows:
                alpha = 5 if self.customColors["alternate"]["alpha"] is None else self.customColors["alternate"]["alpha"]
                applied_state = "alternate"
                break

        if index.data(Qt.ItemDataRole.BackgroundRole):
            painter.setBrush(index.data(Qt.ItemDataRole.BackgroundRole))
        else:
            # Apply custom colors if available
            if applied_state == "selected" and self.customColors["selected"]["color"]:
                painter.setBrush(QColor(
                    self.customColors["selected"]["color"].red(),
                    self.customColors["selected"]["color"].green(),
                    self.customColors["selected"]["color"].blue(),
                    alpha
                ))
            elif applied_state == "pressed" and self.customColors["pressed"]["color"]:
                painter.setBrush(QColor(
                    self.customColors["pressed"]["color"].red(),
                    self.customColors["pressed"]["color"].green(),
                    self.customColors["pressed"]["color"].blue(),
                    alpha
                ))
            elif applied_state == "hover" and self.customColors["hover"]["color"]:
                painter.setBrush(QColor(
                    self.customColors["hover"]["color"].red(),
                    self.customColors["hover"]["color"].green(),
                    self.customColors["hover"]["color"].blue(),
                    alpha
                ))
            elif applied_state == "alternate" and self.customColors["alternate"]["color"]:
                painter.setBrush(QColor(
                    self.customColors["alternate"]["color"].red(),
                    self.customColors["alternate"]["color"].green(),
                    self.customColors["alternate"]["color"].blue(),
                    alpha
                ))
            else:
                painter.setBrush(QColor(c, c, c, alpha))

        self._drawBackground(painter, option, index)

        # draw indicator only if showIndicator is True
        if self._showIndicator and index.row() in self.selectedRows and index.column() == 0 and self.parent().horizontalScrollBar().value() == 0:
            self._drawIndicator(painter, option, index)

        if index.data(Qt.CheckStateRole) is not None:
            self._drawCheckBox(painter, option, index)

        painter.restore()
        super().paint(painter, option, index)

    def _drawCheckBox(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        checkState = Qt.CheckState(index.data(Qt.ItemDataRole.CheckStateRole))

        isDark = isDarkTheme()

        r = 4.5
        x = option.rect.x() + 15
        y = option.rect.center().y() - 9.5
        rect = QRectF(x, y, 19, 19)

        if checkState == Qt.CheckState.Unchecked:
            painter.setBrush(QColor(0, 0, 0, 26) if isDark else QColor(0, 0, 0, 6))
            painter.setPen(QColor(255, 255, 255, 142) if isDark else QColor(0, 0, 0, 122))
            painter.drawRoundedRect(rect, r, r)
        else:
            color = autoFallbackThemeColor(self.lightCheckedColor, self.darkCheckedColor)
            painter.setPen(color)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, r, r)

            if checkState == Qt.CheckState.Checked:
                CheckBoxIcon.ACCEPT.render(painter, rect)
            else:
                CheckBoxIcon.PARTIAL_ACCEPT.render(painter, rect)

        painter.restore()

    def helpEvent(self, event: QHelpEvent, view: QAbstractItemView, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        return self.tooltipDelegate.helpEvent(event, view, option, index)



class TableBase:
    """ Table base class """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegate = TableItemDelegate(self)
        self.scrollDelagate = SmoothScrollDelegate(self)
        self._isSelectRightClickedRow = False

        # set style sheet
        FluentStyleSheet.TABLE_VIEW.apply(self)

        self.setShowGrid(False)

        self.setMouseTracking(True)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(self.delegate)
        self.setSelectionBehavior(TableWidget.SelectRows)
        self.horizontalHeader().setHighlightSections(False)
        self.verticalHeader().setHighlightSections(False)
        self.verticalHeader().setDefaultSectionSize(38)

        self.entered.connect(lambda i: self._setHoverRow(i.row()))
        self.pressed.connect(lambda i: self._setPressedRow(i.row()))
        self.verticalHeader().sectionClicked.connect(self.selectRow)

    def setBorderVisible(self, isVisible: bool):
        """ set the visibility of border """
        self.setProperty("isBorderVisible", isVisible)
        self.setStyle(QApplication.style())

    def setBorderRadius(self, radius: int):
        """ set the radius of border """
        qss = f"QTableView{{border-radius: {radius}px}}"
        setCustomStyleSheet(self, qss, qss)

    def setCheckedColor(self, light, dark):
        """ set the color in checked status

        Parameters
        ----------
        light, dark: str | QColor | Qt.GlobalColor
            color in light/dark theme mode
        """
        self.delegate.setCheckedColor(light, dark)

    def _setHoverRow(self, row: int):
        """ set hovered row """
        self.delegate.setHoverRow(row)
        self.viewport().update()

    def _setPressedRow(self, row: int):
        """ set pressed row """
        if self.selectionMode() == QTableView.SelectionMode.NoSelection:
            return

        self.delegate.setPressedRow(row)
        self.viewport().update()

    def _setSelectedRows(self, indexes: List[QModelIndex]):
        if self.selectionMode() == QTableView.SelectionMode.NoSelection:
            return

        self.delegate.setSelectedRows(indexes)
        self.viewport().update()

    def leaveEvent(self, e):
        QTableView.leaveEvent(self, e)
        self._setHoverRow(-1)

    def resizeEvent(self, e):
        QTableView.resizeEvent(self, e)
        self.viewport().update()

    def keyPressEvent(self, e: QKeyEvent):
        QTableView.keyPressEvent(self, e)
        self.updateSelectedRows()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton or self._isSelectRightClickedRow:
            return QTableView.mousePressEvent(self, e)

        index = self.indexAt(e.pos())
        if index.isValid():
            self._setPressedRow(index.row())

        QWidget.mousePressEvent(self, e)

    def mouseReleaseEvent(self, e):
        QTableView.mouseReleaseEvent(self, e)
        self.updateSelectedRows()

        if self.indexAt(e.pos()).row() < 0 or e.button() == Qt.RightButton:
            self._setPressedRow(-1)

    def setItemDelegate(self, delegate: TableItemDelegate):
        self.delegate = delegate
        super().setItemDelegate(delegate)

    def selectAll(self):
        QTableView.selectAll(self)
        self.updateSelectedRows()

    def selectRow(self, row: int):
        QTableView.selectRow(self, row)
        self.updateSelectedRows()

    def clearSelection(self):
        QTableView.clearSelection(self)
        self.updateSelectedRows()

    def setCurrentIndex(self, index: QModelIndex):
        QTableView.setCurrentIndex(self, index)
        self.updateSelectedRows()

    def updateSelectedRows(self):
        self._setSelectedRows(self.selectedIndexes())

class TableWidget(TableBase, QTableWidget):
    """ Table widget """

    def __init__(self, parent=None):
        super().__init__(parent)

    def setCurrentCell(self, row: int, column: int, command=None):
        self.setCurrentItem(self.item(row, column), command)

    def setCurrentItem(self, item: QTableWidgetItem, command=None):
        if not command:
            super().setCurrentItem(item)
        else:
            super().setCurrentItem(item, command)

        self.updateSelectedRows()

    def setCurrentCell(self, row: int, column: int, command=None):
        self.setCurrentItem(self.item(row, column), command)

    def setCurrentItem(self, item: QTableWidgetItem, command=None):
        if not command:
            super().setCurrentItem(item)
        else:
            super().setCurrentItem(item, command)

        self.updateSelectedRows()

    def isSelectRightClickedRow(self):
        return self._isSelectRightClickedRow

    def setSelectRightClickedRow(self, isSelect: bool):
        self._isSelectRightClickedRow = isSelect

    selectRightClickedRow = Property(bool, isSelectRightClickedRow, setSelectRightClickedRow)

class TableView(TableBase, QTableView):
    """ Table view """

    def __init__(self, parent=None):
        super().__init__(parent)

    def isSelectRightClickedRow(self):
        return self._isSelectRightClickedRow

    def setSelectRightClickedRow(self, isSelect: bool):
        self._isSelectRightClickedRow = isSelect

    selectRightClickedRow = Property(bool, isSelectRightClickedRow, setSelectRightClickedRow)
