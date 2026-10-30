"""Compact sample table, projecting the shared state without owning audio."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from choppeur.core.models import CandidateType
from choppeur.gui.sample_state import SampleState


class SampleTable(QTableWidget):
    sample_clicked = Signal(int, bool)

    def mousePressEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and index.isValid():
            event.accept()
            if index.column() != 4:
                self.setFocus()
                cell = self.item(index.row(), 0)
                if cell is not None:
                    self.sample_clicked.emit(
                        cell.data(Qt.ItemDataRole.UserRole),
                        bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier),
                    )
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.mousePressEvent(event)


class CandidatesPanel(QWidget):
    export_requested = Signal(str)
    drag_requested = Signal(int)

    def __init__(self, state: SampleState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self._item_ids: tuple[int, ...] = ()
        self._syncing = False
        self.table = SampleTable(0, 5)
        self.table.setHorizontalHeaderLabels(["Type", "Tempo", "Durée", "Position", "⠿"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort)
        for column, width in enumerate((0, 90, 90, 100, 36)):
            if column:
                self.table.setColumnWidth(column, width)
        self.table.sample_clicked.connect(state.click)
        self.table.currentCellChanged.connect(self._navigate)
        self.export_marked_button = QPushButton()
        self.export_all_button = QPushButton()
        self.export_marked_button.clicked.connect(lambda: self.export_requested.emit("marked"))
        self.export_all_button.clicked.connect(lambda: self.export_requested.emit("all"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.export_marked_button)
        buttons.addWidget(self.export_all_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        state.changed.connect(self._sync)
        self._sync()

    def _sort(self, column: int) -> None:
        header = self.table.horizontalHeader()
        order = (
            Qt.SortOrder.DescendingOrder
            if header.sortIndicatorSection() == column
            and header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
            else Qt.SortOrder.AscendingOrder
        )
        self._syncing = True
        try:
            self.table.sortItems(column, order)
        finally:
            self._syncing = False
        self._sync()

    def _navigate(self, row: int, column: int, old_row: int, old_column: int) -> None:
        if not self._syncing and row >= 0:
            cell = self.table.item(row, 0)
            if cell is not None:
                self.state.navigate(cell.data(Qt.ItemDataRole.UserRole))

    def _sync(self) -> None:
        self._syncing = True
        try:
            ids = tuple(item.id for item in self.state.items)
            if ids != self._item_ids:
                self.table.setRowCount(0)
                self.table.setRowCount(len(ids))
                for row, item in enumerate(self.state.items):
                    candidate = item.candidate
                    minutes, seconds = divmod(candidate.start_seconds, 60)
                    values = (
                        "",
                        f"{candidate.bpm:g}" if candidate.bpm else "—",
                        f"{candidate.end_seconds - candidate.start_seconds:.3f} s",
                        f"{int(minutes):02d}:{seconds:06.3f}",
                        "⠿",
                    )
                    for column, value in enumerate(values):
                        new_cell = QTableWidgetItem(value)
                        new_cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                        new_cell.setData(Qt.ItemDataRole.UserRole, item.id)
                        self.table.setItem(row, column, new_cell)
                self._item_ids = ids
            by_id = {item.id: item for item in self.state.items}
            for row in range(self.table.rowCount()):
                cell = self.table.item(row, 0)
                if cell is None:
                    continue
                item_id = cell.data(Qt.ItemDataRole.UserRole)
                candidate = by_id[item_id].candidate
                label = (
                    f"Boucle {candidate.bars} mesures" if candidate.type is CandidateType.LOOP else "One-shot"
                )
                marks = "✓ " if item_id in self.state.marked_ids else ""
                playing = "▶ " if item_id == self.state.playing_id else ""
                cell.setText(playing + marks + label)
                if item_id == self.state.active_id and self.table.currentRow() != row:
                    self.table.setCurrentCell(row, 0)
            if self.state.active_id is None:
                self.table.setCurrentCell(-1, -1)
                self.table.clearSelection()
            marked = len(self.state.marked_ids)
            self.export_marked_button.setText(f"Exporter la sélection ({marked})")
            self.export_all_button.setText(f"Tout exporter ({len(ids)})")
            self.export_marked_button.setEnabled(marked > 0)
            self.export_all_button.setEnabled(bool(ids))
        finally:
            self._syncing = False
