"""
Interactive desktop interface for the backend analyzer.
"""
from __future__ import annotations

import io
import json
import os
import sys
import ctypes.util
import shutil
from contextlib import redirect_stderr, redirect_stdout
from typing import Optional

from analyzer.engine import AnalysisEngine, run_analysis
from analyzer.issue import IssueSeverity

try:
    from PySide6.QtCore import QThread, Qt, QTimer, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QTextEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - import availability depends on runtime environment
    QApplication = None
    QThread = object
    QFrame = object
    QGridLayout = object
    QHBoxLayout = object
    QLabel = object
    QLineEdit = object
    QMainWindow = object
    QMessageBox = object
    QPushButton = object
    QProgressBar = object
    QScrollArea = object
    QSizePolicy = object
    QSplitter = object
    QTextEdit = object
    QTreeWidget = object
    QTreeWidgetItem = object
    QVBoxLayout = object
    QWidget = object
    QFileDialog = object

    class _QtFallback:
        LeftButton = 1
        Horizontal = 1
        AlignRight = 0
        AlignVCenter = 0
        AlignLeft = 0
        PointingHandCursor = 0
        ScrollBarAsNeeded = 0

    class _QTimerFallback:
        @staticmethod
        def singleShot(_delay, _callback) -> None:
            return None

    def Signal(*_args, **_kwargs):  # type: ignore[misc]
        return None

    Qt = _QtFallback()
    QTimer = _QTimerFallback()


WINDOW_BG = "#ffffff"
SURFACE_BG = "#f8f9fa"
SURFACE_ALT = "#f0f2f5"
TEXT_PRIMARY = "#0d1117"
TEXT_MUTED = "#57606a"
ACCENT = "#0969da"
ACCENT_DEEP = "#0860ca"
ACCENT_SOFT = "#ddf4ff"
SUCCESS = "#1a7f37"
WARNING = "#d1a105"
DANGER = "#da3633"
TRACK = "#e5e7eb"
TEXT_INPUT_BG = "#ffffff"


class _ThreadSafeLogWriter(io.TextIOBase):
    """Forward worker-thread console output to Qt signals safely."""

    def __init__(self, emit_callback):
        self._emit_callback = emit_callback

    def write(self, content: str) -> int:
        if content:
            self._emit_callback(content)
        return len(content)

    def flush(self) -> None:
        return None


class StatCard(QFrame):
    """Small clickable summary card."""

    clicked = Signal(str)

    def __init__(self, title: str, value: str, caption: str):
        super().__init__()
        self.stat_key = title
        self.setObjectName("StatCard")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 26, 24, 26)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        layout.addWidget(self.value_label)

        caption_label = QLabel(caption)
        caption_label.setObjectName("StatCaption")
        caption_label.setWordWrap(True)
        layout.addWidget(caption_label)
        layout.addStretch(1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.stat_key)
        super().mousePressEvent(event)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class MetricBar(QWidget):
    """Paint a lightweight health bar."""

    def __init__(self, label: str):
        super().__init__()
        self.value = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title_label = QLabel(label)
        self.title_label.setObjectName("MetricLabel")
        self.title_label.setMinimumWidth(100)
        self.title_label.setMaximumWidth(100)
        layout.addWidget(self.title_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(16)
        self.bar.setObjectName("MetricProgress")
        layout.addWidget(self.bar, 1)

        self.value_label = QLabel("0/100")
        self.value_label.setObjectName("MetricValue")
        self.value_label.setMinimumWidth(60)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.value_label)

    def set_value(self, value: float) -> None:
        value = max(0.0, min(100.0, float(value)))
        self.value = value
        self.value_label.setText(f"{value:.0f}")
        self.bar.setValue(int(round(value * 10)))

        if value >= 75:
            color = SUCCESS
        elif value >= 45:
            color = WARNING
        else:
            color = DANGER

        self.bar.setStyleSheet(
            f"""
            QProgressBar#MetricProgress {{
                border: 1px solid {TRACK};
                border-radius: 8px;
                background: {SURFACE_ALT};
            }}
            QProgressBar#MetricProgress::chunk {{
                border-radius: 8px;
                background: {color};
            }}
            """
        )


class AnalysisWorker(QThread):
    """Background analysis worker."""

    log_message = Signal(str)
    analysis_done = Signal(str, object, object)

    def __init__(self, path: str, base_url: str, functional_test, source_label: str):
        super().__init__()
        self.path = path
        self.base_url = base_url
        self.functional_test = functional_test
        self.source_label = source_label

    def run(self) -> None:
        engine = AnalysisEngine()
        log_writer = _ThreadSafeLogWriter(self.log_message.emit)

        try:
            with redirect_stdout(log_writer), redirect_stderr(log_writer):
                report = engine.analyze_path(
                    self.path,
                    functional_tests=[self.functional_test] if self.functional_test else None,
                    functional_base_url=self.base_url,
                    functional_source_label=self.source_label or "Functional Test Builder",
                )
            self.analysis_done.emit(self.path, report, None)
        except Exception as exc:  # pragma: no cover - exercised via manual GUI runs
            self.analysis_done.emit(self.path, None, exc)


class AnalyzerGUI(QMainWindow):
    """PySide6 GUI for the backend analyzer."""

    def __init__(self, initial_path: str = ""):
        super().__init__()
        self.setWindowTitle("Backend Analyzer Studio")
        self.resize(1600, 1000)
        self.setMinimumSize(1080, 760)

        self.current_report = None
        self.issue_lookup: dict[QTreeWidgetItem, object] = {}
        self.live_result_lookup: dict[QTreeWidgetItem, object] = {}
        self.functional_findings_lookup: dict[QTreeWidgetItem, object] = {}
        self.endpoint_lookup: dict[QTreeWidgetItem, object] = {}
        self.worker: Optional[AnalysisWorker] = None
        self.current_endpoint_kind = "Unknown"
        self.latest_live_result_text = ""

        self._build_ui()
        self._apply_styles()
        self._refresh_available_tools()

        if initial_path:
            self.path_input.setText(initial_path)
            QTimer.singleShot(250, self.start_analysis)

    def _build_ui(self) -> None:
        container = QWidget()
        self.setCentralWidget(container)

        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(getattr(QFrame, "NoFrame", 0))
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll_area)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        scroll_area.setWidget(content)

        header = self._build_header()
        root.addWidget(header)

        # STAT CARDS ROW - More prominent
        stats_frame = QFrame()
        stats_frame.setObjectName("Panel")
        stats_frame.setMinimumHeight(170)
        stats_frame.setStyleSheet("QFrame#Panel { background: #f8f9fa; border: none; border-bottom: 2px solid #e5e7eb; }")
        stats_row_layout = QHBoxLayout(stats_frame)
        stats_row_layout.setContentsMargins(32, 28, 32, 28)
        stats_row_layout.setSpacing(24)
        
        self.stat_cards = {}
        stats_data = [
            ("Overall Score", "0", "Overall health"),
            ("Issues", "0", "Total  Static Findings"),
            ("🔴 Critical", "0", "High severity"),
            ("🟡 Medium", "0", "Medium severity"),
            ("🔵 Info", "0", "Low severity"),
        ]
        
        for title, value, caption in stats_data:
            card = StatCard(title, value, caption)
            card.clicked.connect(self._on_stat_card_selected)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            card.setMinimumHeight(130)
            stats_row_layout.addWidget(card)
            self.stat_cards[title] = card
        
        root.addWidget(stats_frame)

        health_panel = self._build_health_panel()
        root.addWidget(health_panel)

        static_review_panel = self._build_static_review_panel()
        root.addWidget(static_review_panel)

        live_api_panel = self._build_live_api_panel()
        root.addWidget(live_api_panel)

        # MAIN CONTENT
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_right_column())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.statusBar().showMessage("👉 Choose a Python file or folder to begin analysis")
        self.statusBar().setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

    def _build_health_panel(self) -> QWidget:
        health_panel = QFrame()
        health_panel.setObjectName("Panel")
        health_layout = QVBoxLayout(health_panel)
        health_layout.setContentsMargins(26, 26, 26, 26)
        health_layout.setSpacing(18)
        health_layout.addWidget(self._section_title("📊 Health Scores", "Safety, Speed, Structure, and Trust ratings"))

        self.summary_label = QLabel("Run analysis to see scores →")
        self.summary_label.setObjectName("HintLabel")
        self.summary_label.setWordWrap(True)
        health_layout.addWidget(self.summary_label)

        self.metric_rows = {}
        for key, label, emoji in [
            ("security", "Safety", "🔒"),
            ("performance", "Speed", "⚡"),
            ("design", "Structure", "🏗️"),
            ("reliability", "Trust", "🛡️"),
        ]:
            metric = MetricBar(f"{emoji} {label}")
            metric.setMinimumHeight(44)
            health_layout.addWidget(metric)
            self.metric_rows[key] = metric

        self.available_tools_label = QLabel("Core analysis active...")
        self.available_tools_label.setObjectName("HintLabel")
        self.available_tools_label.setWordWrap(True)
        health_layout.addWidget(self.available_tools_label)
        return health_panel

    def _build_header(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # HERO SECTION
        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(36, 28, 36, 28)
        hero_layout.setSpacing(28)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(8)
        title = QLabel("Backend Analyzer Studio")
        title.setObjectName("HeroTitle")
        hero_copy.addWidget(title)

        subtitle = QLabel(
            "Analyze your backend code for production-level risks, performance issues, and design problems."
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        hero_side = QVBoxLayout()
        hero_side.setSpacing(10)
        hero_side.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.hero_status = QLabel("Ready to analyze")
        self.hero_status.setObjectName("HeroBadge")
        self.hero_status.setAlignment(Qt.AlignCenter)
        hero_side.addWidget(self.hero_status)

        self.hero_hint = QLabel("Analyze a codebase to get started →")
        self.hero_hint.setObjectName("HeroHint")
        self.hero_hint.setWordWrap(True)
        self.hero_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hero_side.addWidget(self.hero_hint)
        hero_layout.addLayout(hero_side)
        layout.addWidget(hero)

        shell = QFrame()
        shell.setObjectName("Panel")
        shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 24, 24, 24)
        shell_layout.setSpacing(20)

        # INPUT SECTION
        target_panel = QFrame()
        target_panel.setObjectName("SubPanelSoft")
        target_layout = QVBoxLayout(target_panel)
        target_layout.setContentsMargins(20, 20, 20, 20)
        target_layout.setSpacing(14)
        target_layout.addWidget(self._section_title("📁 Analysis Target", "Select a Python file or backend folder to analyze"))

        row = QHBoxLayout()
        row.setSpacing(12)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to Python file or backend folder")
        self.path_input.setMinimumHeight(40)
        self.path_input.returnPressed.connect(self.start_analysis)
        row.addWidget(self.path_input, 1)

        file_button = QPushButton("📄 File")
        file_button.setMinimumHeight(40)
        file_button.setMaximumWidth(100)
        file_button.clicked.connect(self.choose_file)
        row.addWidget(file_button)

        folder_button = QPushButton("📁 Folder")
        folder_button.setMinimumHeight(40)
        folder_button.setMaximumWidth(120)
        folder_button.clicked.connect(self.choose_folder)
        row.addWidget(folder_button)

        self.run_button = QPushButton("🚀 Analyze Codebase")
        self.run_button.setObjectName("AccentButton")
        self.run_button.setMinimumHeight(40)
        self.run_button.setMaximumWidth(160)
        self.run_button.clicked.connect(self.start_analysis)
        row.addWidget(self.run_button)

        target_layout.addLayout(row)
        shell_layout.addWidget(target_panel)

        # TWO COLUMN GRID
        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(20)
        top_grid.setVerticalSpacing(20)

        # LEFT: BACKEND SNAPSHOT
        profile_panel = QFrame()
        profile_panel.setObjectName("Panel")
        profile_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        profile_layout = QGridLayout(profile_panel)
        profile_layout.setContentsMargins(20, 20, 20, 20)
        profile_layout.setHorizontalSpacing(16)
        profile_layout.setVerticalSpacing(14)
        profile_layout.addWidget(self._section_title("🔍 Backend Profile", "Runtime, database, API type, and discovered endpoints"), 0, 0, 1, 2)

        self.backend_runtime_value = self._value_box("Unknown")
        self.database_type_value = self._value_box("Unknown")
        self.api_kind_value = self._value_box("Unknown")
        self.endpoint_count_value = self._value_box("0 endpoints")
        self.frameworks_value = self._value_box("Analyzing...")
        
        profile_layout.addWidget(self._labeled_widget("Runtime", self.backend_runtime_value), 1, 0)
        profile_layout.addWidget(self._labeled_widget("Database", self.database_type_value), 1, 1)
        profile_layout.addWidget(self._labeled_widget("API Style", self.api_kind_value), 2, 0)
        profile_layout.addWidget(self._labeled_widget("Endpoints", self.endpoint_count_value), 2, 1)
        profile_layout.addWidget(self._labeled_widget("Frameworks", self.frameworks_value), 3, 0, 1, 2)
        top_grid.addWidget(profile_panel, 0, 0)

        # RIGHT: API EXPLORER
        explorer_panel = QFrame()
        explorer_panel.setObjectName("Panel")
        explorer_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        explorer_layout = QVBoxLayout(explorer_panel)
        explorer_layout.setContentsMargins(20, 20, 20, 20)
        explorer_layout.setSpacing(14)
        explorer_layout.addWidget(self._section_title("🌐 API Explorer", "Select an endpoint to test it against your running backend"))

        base_row = QHBoxLayout()
        base_row.setSpacing(12)
        base_url_field, self.base_url_input = self._labeled_line_edit("Base URL", "http://localhost:8000")
        base_row.addWidget(base_url_field, 1)
        self.base_url_input.setMinimumHeight(40)
        self.base_url_input.setText("http://localhost:8000")
        self.endpoint_run_button = QPushButton("📤 Send Test")
        self.endpoint_run_button.setMinimumHeight(40)
        self.endpoint_run_button.setMaximumWidth(140)
        self.endpoint_run_button.clicked.connect(self.run_selected_endpoint_test)
        base_row.addWidget(self.endpoint_run_button)
        explorer_layout.addLayout(base_row)

        self.selected_endpoint_label = QLabel("Analyze first to discover endpoints →")
        self.selected_endpoint_label.setObjectName("HintLabel")
        self.selected_endpoint_label.setWordWrap(True)
        explorer_layout.addWidget(self.selected_endpoint_label)

        self.endpoint_tree = QTreeWidget()
        self.endpoint_tree.setColumnCount(5)
        self.endpoint_tree.setHeaderLabels(["Path", "Operation", "Method", "Type", "Source"])
        self.endpoint_tree.itemSelectionChanged.connect(self._on_endpoint_selected)
        self.endpoint_tree.setRootIsDecorated(False)
        self.endpoint_tree.setAlternatingRowColors(False)
        self.endpoint_tree.header().setStretchLastSection(True)
        self.endpoint_tree.setColumnWidth(0, 170)
        self.endpoint_tree.setColumnWidth(1, 220)
        self.endpoint_tree.setColumnWidth(2, 80)
        self.endpoint_tree.setColumnWidth(3, 90)
        self.endpoint_tree.setMinimumHeight(120)
        explorer_layout.addWidget(self.endpoint_tree, 1)
        top_grid.addWidget(explorer_panel, 0, 1)

        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)
        shell_layout.addLayout(top_grid)

        # REQUEST WORKSPACE
        request_panel = QFrame()
        request_panel.setObjectName("Panel")
        request_layout = QVBoxLayout(request_panel)
        request_layout.setContentsMargins(20, 20, 20, 20)
        request_layout.setSpacing(14)
        request_layout.addWidget(self._section_title("✉️ Request Workspace", "REST uses body. GraphQL uses query + optional variables"))

        request_grid = QGridLayout()
        request_grid.setHorizontalSpacing(16)
        request_grid.setVerticalSpacing(10)

        self.request_mode_badge = QLabel("Request Mode: Waiting for endpoint")
        self.request_mode_badge.setObjectName("ModeBadge")
        request_grid.addWidget(self.request_mode_badge, 0, 0, 1, 2)

        query_label = QLabel("Request Body / Query")
        query_label.setObjectName("EditorLabel")
        request_grid.addWidget(query_label, 1, 0)

        variables_label = QLabel("GraphQL Variables")
        variables_label.setObjectName("EditorLabel")
        request_grid.addWidget(variables_label, 1, 1)

        self.query_text = QTextEdit()
        self.query_text.setMinimumHeight(170)
        self.query_text.setPlaceholderText('{\n  "example": "request payload"\n}')
        request_grid.addWidget(self.query_text, 2, 0)

        self.variables_text = QTextEdit()
        self.variables_text.setMinimumHeight(170)
        self.variables_text.setPlaceholderText('{\n  "variables": "GraphQL only"\n}')
        request_grid.addWidget(self.variables_text, 2, 1)

        self.request_hint_label = QLabel("Pick an endpoint to populate the workspace →")
        self.request_hint_label.setObjectName("HintLabel")
        self.request_hint_label.setWordWrap(True)
        request_grid.addWidget(self.request_hint_label, 3, 0, 1, 2)

        request_grid.setColumnStretch(0, 2)
        request_grid.setColumnStretch(1, 1)
        request_layout.addLayout(request_grid)
        shell_layout.addWidget(request_panel)

        # FOOTER
        footer = QHBoxLayout()
        footer.setSpacing(14)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(10)
        self.progress.hide()
        footer.addWidget(self.progress)

        self.status_label = QLabel("Choose a Python file or folder to begin analysis →")
        self.status_label.setObjectName("HintLabel")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        shell_layout.addLayout(footer)

        layout.addWidget(shell)
        layout.addStretch(1)
        return wrapper

    def _build_static_review_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(16)
        layout.addWidget(self._section_title("🔎 Static Review", "Findings and detailed review context"))

        static_row = QSplitter(Qt.Horizontal)
        static_row.setChildrenCollapsible(False)

        findings_panel = QFrame()
        findings_panel.setObjectName("SubPanelAlt")
        findings_layout = QVBoxLayout(findings_panel)
        findings_layout.setContentsMargins(20, 20, 20, 20)
        findings_layout.setSpacing(14)
        findings_layout.addWidget(self._section_title("🔎 Static Code Review Findings", "Issues ranked by severity and category"))

        self.issue_tree = QTreeWidget()
        self.issue_tree.setColumnCount(4)
        self.issue_tree.setHeaderLabels(["Issue", "Severity", "Category", "Location"])
        self.issue_tree.setRootIsDecorated(False)
        self.issue_tree.itemSelectionChanged.connect(self._on_issue_selected)
        self.issue_tree.header().setStretchLastSection(True)
        self.issue_tree.setMinimumHeight(220)
        findings_layout.addWidget(self.issue_tree, 1)
        static_row.addWidget(findings_panel)

        static_detail_panel = QFrame()
        static_detail_panel.setObjectName("SubPanelAlt")
        static_detail_layout = QVBoxLayout(static_detail_panel)
        static_detail_layout.setContentsMargins(20, 20, 20, 20)
        static_detail_layout.setSpacing(14)
        static_detail_layout.addWidget(self._section_title("🔎 Static Code Review Finding", "Detailed review context for the selected issue"))

        self.static_detail_title = QLabel("Select a static finding on the left →")
        self.static_detail_title.setObjectName("DetailTitle")
        self.static_detail_title.setWordWrap(True)
        static_detail_layout.addWidget(self.static_detail_title)

        self.static_detail_meta = QLabel("")
        self.static_detail_meta.setObjectName("HintLabel")
        self.static_detail_meta.setWordWrap(True)
        static_detail_layout.addWidget(self.static_detail_meta)

        self.static_detail_body = QTextEdit()
        self.static_detail_body.setReadOnly(True)
        self.static_detail_body.setMinimumHeight(180)
        self.static_detail_body.setPlainText("Select a static finding to inspect code review details here.")
        static_detail_layout.addWidget(self.static_detail_body, 1)
        static_row.addWidget(static_detail_panel)
        static_row.setStretchFactor(0, 3)
        static_row.setStretchFactor(1, 2)
        layout.addWidget(static_row, 1)
        return panel

    def _build_left_column(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        functional_panel = QFrame()
        functional_panel.setObjectName("Panel")
        functional_layout = QVBoxLayout(functional_panel)
        functional_layout.setContentsMargins(26, 26, 26, 26)
        functional_layout.setSpacing(16)
        functional_layout.addWidget(self._section_title("⚙️ Functional Findings", "Actionable failures surfaced by live checks"))

        self.functional_findings_tree = QTreeWidget()
        self.functional_findings_tree.setColumnCount(4)
        self.functional_findings_tree.setHeaderLabels(["Failure", "Severity", "Cause", "Location"])
        self.functional_findings_tree.setRootIsDecorated(False)
        self.functional_findings_tree.itemSelectionChanged.connect(self._on_functional_finding_selected)
        self.functional_findings_tree.header().setStretchLastSection(True)
        self.functional_findings_tree.setMinimumHeight(180)
        functional_layout.addWidget(self.functional_findings_tree, 1)
        layout.addWidget(functional_panel, 1)
        return wrapper

    def _build_live_api_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(16)
        layout.addWidget(self._section_title("Live API Test Runs", "Raw request/response execution output"))

        live_splitter = QSplitter(Qt.Horizontal)
        live_splitter.setChildrenCollapsible(False)

        self.live_result_tree = QTreeWidget()
        self.live_result_tree.setColumnCount(4)
        self.live_result_tree.setHeaderLabels(["Run", "Result", "Request", "HTTP"])
        self.live_result_tree.setRootIsDecorated(False)
        self.live_result_tree.itemSelectionChanged.connect(self._on_live_result_selected)
        self.live_result_tree.header().setStretchLastSection(True)
        self.live_result_tree.setMinimumHeight(180)
        live_splitter.addWidget(self.live_result_tree)

        live_detail_panel = QFrame()
        live_detail_panel.setObjectName("SubPanelAlt")
        live_detail_layout = QVBoxLayout(live_detail_panel)
        live_detail_layout.setContentsMargins(20, 20, 20, 20)
        live_detail_layout.setSpacing(12)
        live_detail_layout.addWidget(self._section_title("🌐 Live Test Result", "Execution trace for one selected run"))

        self.live_detail_title = QLabel("Select a live test run beside this panel →")
        self.live_detail_title.setObjectName("DetailTitle")
        self.live_detail_title.setWordWrap(True)
        live_detail_layout.addWidget(self.live_detail_title)

        self.live_detail_meta = QLabel("")
        self.live_detail_meta.setObjectName("HintLabel")
        self.live_detail_meta.setWordWrap(True)
        live_detail_layout.addWidget(self.live_detail_meta)

        self.live_detail_body = QTextEdit()
        self.live_detail_body.setReadOnly(True)
        self.live_detail_body.setMinimumHeight(180)
        self.live_detail_body.setPlainText("Select a live test result to inspect request and response details here.")
        live_detail_layout.addWidget(self.live_detail_body, 1)
        live_splitter.addWidget(live_detail_panel)
        live_splitter.setStretchFactor(0, 3)
        live_splitter.setStretchFactor(1, 2)
        layout.addWidget(live_splitter, 1)
        return panel

    def _build_right_column(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        functional_detail_panel = QFrame()
        functional_detail_panel.setObjectName("Panel")
        functional_detail_layout = QVBoxLayout(functional_detail_panel)
        functional_detail_layout.setContentsMargins(26, 26, 26, 26)
        functional_detail_layout.setSpacing(16)
        functional_detail_layout.addWidget(self._section_title("🛠 Functional Diagnosis", "Why a live check failed and what to do next"))

        self.functional_detail_title = QLabel("Select a functional finding below →")
        self.functional_detail_title.setObjectName("DetailTitle")
        self.functional_detail_title.setWordWrap(True)
        functional_detail_layout.addWidget(self.functional_detail_title)

        self.functional_detail_meta = QLabel("")
        self.functional_detail_meta.setObjectName("HintLabel")
        self.functional_detail_meta.setWordWrap(True)
        functional_detail_layout.addWidget(self.functional_detail_meta)

        self.functional_detail_body = QTextEdit()
        self.functional_detail_body.setReadOnly(True)
        self.functional_detail_body.setMinimumHeight(180)
        self.functional_detail_body.setPlainText("Select a functional finding to inspect the failure details here.")
        functional_detail_layout.addWidget(self.functional_detail_body, 1)
        layout.addWidget(functional_detail_panel, 1)

        # LOG
        log_panel = QFrame()
        log_panel.setObjectName("Panel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(26, 26, 26, 26)
        log_layout.setSpacing(16)
        log_layout.addWidget(self._section_title("📋 Analysis Log", "Real-time output from the analyzer"))

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.log_text.setPlainText("Logs will appear here during analysis.\n")
        self.log_text.setFont(self._get_monospace_font())
        log_layout.addWidget(self.log_text, 1)
        layout.addWidget(log_panel, 1)
        return wrapper
    
    def _get_monospace_font(self):
        """Return a monospace font for log display."""
        font = self.log_text.font()
        # Try to use a monospace font, falling back to default if not available
        for family in ["Courier New", "Courier", "Monospace", "Monaco", "Menlo"]:
            font.setFamily(family)
            if font.fixedPitch():
                break
        font.setPointSize(10)
        return font

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {WINDOW_BG};
                color: {TEXT_PRIMARY};
            }}
            QStatusBar {{
                background: {SURFACE_ALT};
                color: {TEXT_MUTED};
                border-top: 1px solid {TRACK};
                padding: 4px 8px;
            }}
            QFrame#HeroPanel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {ACCENT}, stop:1 {ACCENT_DEEP});
                border: none;
                border-radius: 8px;
            }}
            QFrame#Panel {{
                background: {SURFACE_BG};
                border: 1px solid {TRACK};
                border-radius: 8px;
            }}
            QFrame#SubPanelAlt {{
                background: {SURFACE_ALT};
                border: 1px solid {TRACK};
                border-radius: 6px;
            }}
            QFrame#SubPanelSoft {{
                background: {ACCENT_SOFT};
                border: 1px solid {ACCENT};
                border-radius: 6px;
            }}
            QFrame#StatCard {{
                background: white;
                border: 1px solid {TRACK};
                border-radius: 8px;
            }}
            QFrame#StatCard:hover {{
                border: 2px solid {ACCENT};
            }}
            QLabel#HeroTitle {{
                font-size: 32px;
                font-weight: 900;
                color: white;
                min-height: 40px;
            }}
            QLabel#HeroSubtitle {{
                font-size: 15px;
                color: rgba(255, 255, 255, 0.95);
                min-height: 24px;
                font-weight: 500;
            }}
            QLabel#HeroBadge {{
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 20px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                color: white;
                min-width: 140px;
            }}
            QLabel#HeroHint {{
                font-size: 12px;
                color: rgba(255, 255, 255, 0.85);
                max-width: 320px;
                font-weight: 500;
            }}
            QLabel#SectionTitle {{
                font-size: 16px;
                font-weight: 800;
                color: {TEXT_PRIMARY};
                min-height: 22px;
            }}
            QLabel#SectionSubtitle {{
                font-size: 12px;
                color: {TEXT_MUTED};
                min-height: 18px;
                font-weight: 500;
            }}
            QLabel#StatTitle {{
                font-size: 13px;
                font-weight: 700;
                color: {TEXT_MUTED};
            }}
            QLabel#StatValue {{
                font-size: 42px;
                font-weight: 900;
                color: {ACCENT};
            }}
            QLabel#StatCaption {{
                font-size: 12px;
                color: {TEXT_MUTED};
                font-weight: 500;
            }}
            QLabel#MetricLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {TEXT_PRIMARY};
            }}
            QLabel#MetricValue {{
                font-size: 12px;
                color: {ACCENT};
                font-weight: 700;
            }}
            QLabel#HintLabel {{
                font-size: 12px;
                color: {TEXT_MUTED};
                min-height: 18px;
                font-weight: 400;
            }}
            QLabel#EditorLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {TEXT_PRIMARY};
            }}
            QLabel#ValueBox {{
                background: {SURFACE_ALT};
                border: 1px solid {TRACK};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 500;
                color: {TEXT_PRIMARY};
            }}
            QLabel#DetailTitle {{
                font-size: 20px;
                font-weight: 800;
                color: {TEXT_PRIMARY};
            }}
            QLabel#ModeBadge {{
                background: {ACCENT_SOFT};
                border: 1px solid {ACCENT};
                border-radius: 20px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                color: {ACCENT};
            }}
            QPushButton {{
                background: {SURFACE_ALT};
                border: 1px solid {TRACK};
                border-radius: 6px;
                padding: 8px 14px;
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {TRACK};
                border: 1px solid #d0d7de;
            }}
            QPushButton:pressed {{
                background: #cfd9e0;
            }}
            QPushButton:disabled {{
                color: {TEXT_MUTED};
                background: #f0f2f5;
                border: 1px solid {TRACK};
            }}
            QPushButton#AccentButton {{
                background: {ACCENT};
                color: white;
                border: 1px solid {ACCENT};
            }}
            QPushButton#AccentButton:hover {{
                background: {ACCENT_DEEP};
                border: 1px solid {ACCENT_DEEP};
            }}
            QPushButton#AccentButton:pressed {{
                background: #0860ca;
            }}
            QLineEdit, QTextEdit, QTreeWidget {{
                background: {TEXT_INPUT_BG};
                border: 1px solid {TRACK};
                border-radius: 6px;
                color: {TEXT_PRIMARY};
                font-size: 12px;
                padding: 8px;
                selection-background-color: {ACCENT_SOFT};
                selection-color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 2px solid {ACCENT};
            }}
            QLineEdit {{
                min-height: 28px;
            }}
            QTextEdit {{
                line-height: 1.5;
            }}
            QTreeWidget::item {{
                padding: 8px 6px;
                height: 28px;
            }}
            QTreeWidget::item:hover {{
                background: {SURFACE_ALT};
            }}
            QTreeWidget::item:selected {{
                background: {ACCENT_SOFT};
                color: {TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background: {SURFACE_ALT};
                border: none;
                border-bottom: 1px solid {TRACK};
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                padding: 8px 6px;
            }}
            QProgressBar {{
                border: 1px solid {TRACK};
                border-radius: 4px;
                background: {SURFACE_ALT};
                min-height: 14px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 4px;
            }}
            QScrollBar:vertical {{
                width: 12px;
                background: {WINDOW_BG};
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {TRACK};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #d0d7de;
            }}
            """
        )

    def _section_title(self, title: str, subtitle: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("SectionSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        return wrapper

    def _value_box(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ValueBox")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def _labeled_widget(self, label: str, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        title = QLabel(label)
        title.setObjectName("HintLabel")
        layout.addWidget(title)
        layout.addWidget(widget)
        return wrapper

    def _labeled_line_edit(self, label: str, placeholder: str) -> tuple[QWidget, QLineEdit]:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        return self._labeled_widget(label, field), field

    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Python file",
            "",
            "Python files (*.py);;All files (*.*)",
        )
        if selected:
            self.path_input.setText(selected)

    def choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose backend folder")
        if selected:
            self.path_input.setText(selected)

    def _selected_endpoint(self):
        items = self.endpoint_tree.selectedItems()
        if not items:
            return None
        return self.endpoint_lookup.get(items[0])

    def _populate_discovery(self, discovery) -> None:
        self.backend_runtime_value.setText(discovery.runtime or "Unknown")
        self.database_type_value.setText(discovery.database_type or "Unknown")
        self.api_kind_value.setText(discovery.api_style or "Unknown")
        self.current_endpoint_kind = discovery.api_style or "Unknown"
        frameworks = ", ".join(discovery.frameworks) if discovery.frameworks else "No framework markers detected"
        self.frameworks_value.setText(frameworks)
        count = len(discovery.endpoints)
        self.endpoint_count_value.setText(f"{count} discovered endpoint{'s' if count != 1 else ''}")
        self._populate_endpoint_tree(discovery.endpoints)

    def _populate_endpoint_tree(self, endpoints) -> None:
        self.endpoint_tree.clear()
        self.endpoint_lookup = {}

        if not endpoints:
            placeholder = QTreeWidgetItem(["No API endpoints discovered", "", "", "", ""])
            self.endpoint_tree.addTopLevelItem(placeholder)
            self.endpoint_lookup[placeholder] = None
            self.selected_endpoint_label.setText("No REST or GraphQL endpoints were detected in this codebase.")
            self.request_mode_badge.setText("Request Mode: No endpoint")
            self.request_hint_label.setText("No request example is available because no endpoint was discovered.")
            self._set_request_editors(
                body_text='{\n  "message": "No example request available yet."\n}',
                variables_text="{}",
                graphql_enabled=False,
            )
            return

        for endpoint in endpoints:
            operation_name = endpoint.name if endpoint.kind == "graphql" else ""
            item = QTreeWidgetItem(
                [
                    endpoint.path,
                    operation_name,
                    endpoint.method,
                    endpoint.kind.upper(),
                    f"{endpoint.source_file}:{endpoint.line}",
                ]
            )
            self.endpoint_tree.addTopLevelItem(item)
            self.endpoint_lookup[item] = endpoint

        self.endpoint_tree.setCurrentItem(self.endpoint_tree.topLevelItem(0))
        self._sync_endpoint_preview(self.endpoint_lookup[self.endpoint_tree.topLevelItem(0)])

    def _serialize_endpoint_example(self, endpoint) -> str:
        if endpoint is None:
            return '{\n  "message": "No request example available."\n}'
        if endpoint.kind == "graphql":
            return endpoint.graphql_query or f"query {endpoint.name}Query {{\n  {endpoint.name}\n}}"
        return json.dumps(endpoint.example_json_body or {}, indent=2)

    def _serialize_endpoint_variables(self, endpoint) -> str:
        if endpoint is None or endpoint.kind != "graphql":
            return "{}"
        return json.dumps(endpoint.graphql_variables or {}, indent=2)

    def _sync_endpoint_preview(self, endpoint) -> None:
        if endpoint is None:
            self.selected_endpoint_label.setText("No endpoint selected.")
            return

        kind_label = "GraphQL" if endpoint.kind == "graphql" else "REST"
        self.current_endpoint_kind = kind_label
        self.api_kind_value.setText(kind_label)
        display_name = endpoint.label() if endpoint.kind == "graphql" else f"{endpoint.method} {endpoint.path}"
        self.selected_endpoint_label.setText(
            f"{display_name} from {endpoint.source_file}:{endpoint.line}"
        )
        if endpoint.kind == "graphql":
            self.request_mode_badge.setText("Request Mode: GraphQL query + optional variables")
            self.request_hint_label.setText("Paste a raw GraphQL query or mutation on the left. Put variables JSON on the right only if the operation needs them. Left side shows available fields to select.")
            self._set_request_editors(
                body_text=self._serialize_endpoint_example(endpoint),
                variables_text=self._serialize_endpoint_variables(endpoint),
                graphql_enabled=True,
            )
        else:
            response_example = json.dumps(endpoint.example_response_body or {}, indent=2) if endpoint.example_response_body else '{\n  "message": "No response example available."\n}'
            self.request_mode_badge.setText("Request Mode: REST request body + response format")
            self.request_hint_label.setText("Edit the request body on the left. The right panel shows the expected response format with available fields.")
            self._set_request_editors(
                body_text=self._serialize_endpoint_example(endpoint),
                variables_text=response_example,
                graphql_enabled=False,
            )

    def _on_endpoint_selected(self) -> None:
        self._sync_endpoint_preview(self._selected_endpoint())

    def run_selected_endpoint_test(self) -> None:
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.critical(self, "Missing target", "Choose a file or folder to analyze first.")
            return

        endpoint = self._selected_endpoint()
        if endpoint is None:
            QMessageBox.critical(self, "Missing endpoint", "Analyze the codebase and choose a discovered endpoint first.")
            return

        base_url = self.base_url_input.text().strip()
        if not base_url:
            QMessageBox.critical(self, "Missing base URL", "Enter the running backend base URL before testing an endpoint.")
            return

        try:
            functional_test = self._build_functional_test_definition()
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid request example", str(exc))
            return

        normalized = os.path.abspath(os.path.expanduser(path))
        self.status_label.setText(f"Sending {endpoint.method} request to {endpoint.path}...")
        self.summary_label.setText(f"Live test against {base_url}")
        self._reset_log_view()
        self._append_log(f"$ Analyzing {normalized}\n")
        self._append_log(f"$ Live test {endpoint.method} {endpoint.path} against {base_url}\n")
        self._set_busy(True)
        self._clear_report_views()
        self._start_worker(normalized, functional_test, f"{endpoint.method} {endpoint.path}")

    def start_analysis(self) -> None:
        if self.worker and self.worker.isRunning():
            return

        path = self.path_input.text().strip()
        if not path:
            QMessageBox.critical(self, "Missing target", "Choose a file or folder to analyze.")
            return

        normalized = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(normalized):
            QMessageBox.critical(self, "Invalid target", f"{normalized} does not exist.")
            return

        self.path_input.setText(normalized)
        self.status_label.setText("Analyzing codebase and discovering API surface...")
        self.summary_label.setText(f"Scanning {os.path.basename(normalized) or normalized}")
        self._reset_log_view()
        self._append_log(f"$ Analyzing {normalized}\n")
        self._set_busy(True)
        self._clear_report_views()
        self._start_worker(normalized, None, "")

    def _start_worker(self, path: str, functional_test, source_label: str) -> None:
        self.worker = AnalysisWorker(
            path=path,
            base_url=self.base_url_input.text().strip(),
            functional_test=functional_test,
            source_label=source_label,
        )
        self.worker.log_message.connect(self._append_log)
        self.worker.analysis_done.connect(self._handle_analysis_result)
        self.worker.start()

    def _handle_analysis_result(self, path: str, report, error: Optional[Exception]) -> None:
        self._set_busy(False)

        if error is not None:
            self.status_label.setText("Analysis failed.")
            self._append_log(f"Error: {error}\n")
            QMessageBox.critical(self, "Analysis failed", str(error))
            return

        if report is None:
            self.status_label.setText("No report generated.")
            return

        self.current_report = report
        self._populate_discovery(report.backend_discovery)
        self._render_report(path, report)
        if report.functional_summary:
            self._populate_live_results(report.functional_summary)
            self._populate_functional_findings(report.functional_issues)
        else:
            self.latest_live_result_text = ""
            self.live_result_lookup = {}
            self.live_result_tree.clear()
            self._set_live_placeholder("No live tests", "Run a live test to see REST or GraphQL results here.")
            self._populate_functional_findings([])

        if report.functional_summary:
            self.status_label.setText("Analysis complete. Review Findings for live test failures or GraphQL/API issues.")
        else:
            self.status_label.setText("Analysis complete. Use the cards or Findings list to inspect detailed results.")
        self._append_log("Analysis complete.\n")

    def _render_report(self, path: str, report) -> None:
        scores = report.health_score.to_dict()
        summary = report.to_dict()["summary"]
        functional_summary = report.functional_summary
        discovery = report.backend_discovery

        self.stat_cards["Overall Score"].set_value(f"{scores['overall']}")
        self.stat_cards["Issues"].set_value(str(summary["total_issues"]))
        self.stat_cards["🔴 Critical"].set_value(str(summary["critical"]))
        self.stat_cards["🟡 Medium"].set_value(str(summary["warnings"]))
        self.stat_cards["🔵 Info"].set_value(str(summary["info"]))

        summary_text = f"{os.path.basename(path) or path} — {summary['total_issues']} findings"
        if discovery and discovery.endpoints:
            summary_text += f" — {len(discovery.endpoints)} endpoints"
        if functional_summary:
            summary_text += f" — {functional_summary.passed}/{functional_summary.total} tests pass"
        self.summary_label.setText(summary_text)

        self.metric_rows["security"].set_value(scores["security"])
        self.metric_rows["performance"].set_value(scores["performance"])
        self.metric_rows["design"].set_value(scores["design"])
        self.metric_rows["reliability"].set_value(scores["reliability"])

        self._populate_issues(report.issues)
        if not report.issues:
            self._render_insights(report)

    def _populate_issues(self, issues) -> None:
        self.issue_tree.clear()
        self.issue_lookup = {}

        if not issues:
            placeholder = QTreeWidgetItem(["No issues found", "", "", ""])
            self.issue_tree.addTopLevelItem(placeholder)
            self.issue_lookup[placeholder] = None
            self._set_static_placeholder("No issues found.", "The analyzer did not report any problems for this target.")
            return

        for issue in issues:
            item = QTreeWidgetItem(
                [
                    issue.title,
                    issue.severity.value.upper(),
                    issue.issue_type.value.title(),
                    str(issue.location),
                ]
            )
            self.issue_tree.addTopLevelItem(item)
            self.issue_lookup[item] = issue

        self.issue_tree.setCurrentItem(self.issue_tree.topLevelItem(0))
        self._show_issue_detail(self.issue_lookup[self.issue_tree.topLevelItem(0)])

    def _populate_live_results(self, functional_summary) -> None:
        self.live_result_tree.clear()
        self.live_result_lookup = {}
        self.latest_live_result_text = self._format_functional_summary(functional_summary)

        if not functional_summary or not functional_summary.results:
            placeholder = QTreeWidgetItem(["No live test runs", "", "", ""])
            self.live_result_tree.addTopLevelItem(placeholder)
            self.live_result_lookup[placeholder] = None
            return

        for result in functional_summary.results:
            outcome = "PASS" if result.passed else "FAIL"
            request = f"{result.request_method or 'GET'} {result.endpoint}"
            status = str(result.status_code) if result.status_code is not None else ""
            item = QTreeWidgetItem([result.name, outcome, request, status])
            self.live_result_tree.addTopLevelItem(item)
            self.live_result_lookup[item] = result

        self.live_result_tree.setCurrentItem(self.live_result_tree.topLevelItem(0))

    def _populate_functional_findings(self, issues) -> None:
        self.functional_findings_tree.clear()
        self.functional_findings_lookup = {}

        if not issues:
            placeholder = QTreeWidgetItem(["No live-check failures", "", "", ""])
            self.functional_findings_tree.addTopLevelItem(placeholder)
            self.functional_findings_lookup[placeholder] = None
            self._set_functional_placeholder(
                "No functional failures",
                "Live checks passed cleanly or have not been run yet.",
            )
            return

        for issue in issues:
            item = QTreeWidgetItem(
                [
                    issue.title,
                    issue.severity.value.upper(),
                    issue.issue_type.value.title(),
                    str(issue.location),
                ]
            )
            self.functional_findings_tree.addTopLevelItem(item)
            self.functional_findings_lookup[item] = issue

        self.functional_findings_tree.setCurrentItem(self.functional_findings_tree.topLevelItem(0))
        first = self.functional_findings_lookup[self.functional_findings_tree.topLevelItem(0)]
        if first is not None:
            self._show_functional_finding_detail(first)

    def _render_insights(self, report) -> None:
        intelligence = report.intelligence or {}
        lines = []
        for key in ("reliability", "scalability", "security", "maintainability"):
            insight = intelligence.get(key)
            if not insight:
                continue
            risk = insight.get("risk_level", "unknown").upper()
            summary = insight.get("summary", "")
            lines.append(f"{key.title()} [{risk}]\n{summary}")

        correlations = intelligence.get("correlations", [])
        for correlation in correlations[:3]:
            lines.append(
                f"Correlation [{correlation.get('severity', 'medium').upper()}]\n"
                f"{correlation.get('pattern', '')}\n"
                f"Recommendation: {correlation.get('recommendation', '')}"
            )

        if lines:
            self.static_detail_body.setPlainText("\n\n".join(lines))

    def _build_functional_test_definition(self) -> dict:
        endpoint_spec = self._selected_endpoint()
        if endpoint_spec is None:
            raise ValueError("Choose one discovered endpoint before running a live test.")

        endpoint = endpoint_spec.path
        if not endpoint:
            raise ValueError("The selected endpoint is missing a path.")

        base_url = self.base_url_input.text().strip()
        if not endpoint.startswith(("http://", "https://")) and not base_url:
            raise ValueError("Enter a base URL when the endpoint is a relative path.")

        body_text = self.query_text.toPlainText().strip()
        test_definition = {
            "name": endpoint_spec.label(),
            "kind": endpoint_spec.kind,
            "method": endpoint_spec.method,
            "path": endpoint,
            "expect": {"status": 200},
        }

        if endpoint_spec.kind == "graphql":
            query, variables, operation_name = self._parse_graphql_input(
                query_text=self.query_text.toPlainText().strip(),
                variables_text=self.variables_text.toPlainText().strip(),
                endpoint_spec=endpoint_spec,
            )
            test_definition["query"] = query
            test_definition["variables"] = variables
            if operation_name:
                test_definition["operation_name"] = operation_name
            test_definition["expect"]["data_not_null"] = True
            test_definition["expect"]["no_errors"] = True
        else:
            if endpoint_spec.method in {"POST", "PUT", "PATCH", "DELETE"}:
                if body_text:
                    try:
                        test_definition["json_body"] = json.loads(body_text)
                    except json.JSONDecodeError as exc:
                        raise ValueError("REST example must be valid JSON in the request example box.") from exc
                elif endpoint_spec.example_json_body is not None:
                    test_definition["json_body"] = endpoint_spec.example_json_body

        return test_definition

    def _parse_graphql_input(self, query_text: str, variables_text: str, endpoint_spec) -> tuple[str, dict, Optional[str]]:
        if not query_text:
            query = endpoint_spec.graphql_query or ""
            if not query:
                raise ValueError("No GraphQL query or mutation is available for the selected endpoint.")
            variables = endpoint_spec.graphql_variables or {}
            return query, variables, None

        try:
            payload = json.loads(query_text)
        except json.JSONDecodeError:
            query = query_text.strip()
            if not query:
                raise ValueError("GraphQL request cannot be empty.")
            variables = self._parse_graphql_variables_json(variables_text)
            return query, variables, None

        if not isinstance(payload, dict):
            raise ValueError("GraphQL request JSON must be an object with `query` and optional `variables`.")

        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("GraphQL request JSON must include a non-empty `query` field.")

        variables = payload.get("variables", {})
        if variables is None:
            variables = {}
        if not isinstance(variables, dict):
            raise ValueError("GraphQL `variables` must be a JSON object.")

        operation_name = payload.get("operationName")
        if operation_name is not None:
            operation_name = str(operation_name).strip() or None

        return query, variables, operation_name

    def _parse_graphql_variables_json(self, variables_text: str) -> dict:
        if not variables_text:
            return {}
        try:
            payload = json.loads(variables_text)
        except json.JSONDecodeError as exc:
            raise ValueError("GraphQL variables must be valid JSON.") from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("GraphQL variables must be a JSON object.")
        return payload

    def _on_issue_selected(self) -> None:
        items = self.issue_tree.selectedItems()
        if not items:
            return

        issue = self.issue_lookup.get(items[0])
        if issue is None:
            self._set_static_placeholder("No issues found.", "The analyzer did not report any problems for this target.")
            return
        self._show_issue_detail(issue)

    def _on_live_result_selected(self) -> None:
        items = self.live_result_tree.selectedItems()
        if not items:
            return

        result = self.live_result_lookup.get(items[0])
        if result is None:
            self._set_live_placeholder("No live tests", "Run a live test to see REST or GraphQL results here.")
            return
        self._show_live_result_detail(result)

    def _on_functional_finding_selected(self) -> None:
        items = self.functional_findings_tree.selectedItems()
        if not items:
            return

        issue = self.functional_findings_lookup.get(items[0])
        if issue is None:
            self._set_functional_placeholder(
                "No functional findings",
                "Run live API tests to see failures in this section.",
            )
            return
        self._show_functional_finding_detail(issue)

    def _show_live_result_detail(self, result=None) -> None:
        if result is None:
            items = self.live_result_tree.selectedItems()
            if not items:
                self._set_live_placeholder(
                    "No live result yet",
                    "Click Send Test to run a live API check and view the request and response here.",
                )
                return
            result = self.live_result_lookup.get(items[0])
        if result is None:
            self._set_live_placeholder("No live tests", "Run a live test to see REST or GraphQL results here.")
            return

        self.live_detail_title.setText(f"Live API Test: {result.name}")
        self.live_detail_meta.setText(
            f"Outcome: {'PASS' if result.passed else 'FAIL'}    "
            f"Request: {result.request_method or 'GET'} {result.endpoint}"
        )
        self.live_detail_body.setPlainText(self._format_single_live_result(result))

    def _format_single_live_result(self, result) -> str:
        sections = [
            f"Test: {result.name}",
            f"Outcome: {'PASS' if result.passed else 'FAIL'}",
            f"Request: {result.request_method or 'GET'} {result.endpoint}",
        ]
        if result.request_headers:
            sections.append(f"Request headers:\n{json.dumps(result.request_headers, indent=2)}")
        if result.request_body:
            sections.append(f"Request body:\n{result.request_body}")
        if result.status_code is not None:
            sections.append(f"HTTP status code: {result.status_code}")
        if result.response_time_ms is not None:
            sections.append(f"Response time: {result.response_time_ms} ms")
        if result.message:
            sections.append(f"Message:\n{result.message}")
        if result.details:
            sections.append("Details:\n" + "\n".join(f"- {detail}" for detail in result.details))
        if result.response_headers:
            sections.append(f"Response headers:\n{json.dumps(result.response_headers, indent=2)}")
        if result.response_body is not None:
            sections.append(f"Response body:\n{result.response_body}")
        return "\n\n".join(sections)

    def _on_stat_card_selected(self, stat_key: str) -> None:
        if self.current_report is None:
            self._set_static_placeholder(
                "No analysis yet",
                "Run an analysis first to see score breakdowns.",
            )
            return

        if stat_key == "Overall Score":
            self._show_overall_score_detail()
            return

        filters = {
            "Issues": None,
            "🔴 Critical": IssueSeverity.HIGH,
            "🟡 Medium": IssueSeverity.MEDIUM,
            "🔵 Info": IssueSeverity.LOW,
        }
        self._show_issue_group_detail(stat_key, filters.get(stat_key))

    def _format_issue_for_humans(self, issue) -> str:
        summary = self._issue_plain_summary(issue)
        impact = self._issue_plain_impact(issue)
        action = self._issue_plain_action(issue)

        parts = [
            f"What this means:\n{summary}",
            f"Why it matters:\n{impact}",
            f"What to do next:\n{action}",
        ]

        if issue.related_code:
            parts.append(f"Code involved:\n{issue.related_code.strip()}")

        return "\n\n".join(parts)

    def _issue_plain_summary(self, issue) -> str:
        title = (issue.title or "").lower()
        desc = (issue.description or "").lower()
        rec = (issue.recommendation or "").lower()
        combined = " ".join([title, desc, rec])

        if "silent error" in combined or "swallowed" in combined:
            return "The code hides a failure instead of recording it or returning a clear error."
        if "pickle" in combined:
            return "The code is loading Python pickle data, which is unsafe when that data could come from outside the system."
        if "functional test failed" in combined:
            return "A live API check did not match the expected behavior, so this endpoint may be unavailable or misconfigured."
        if "without validation" in combined or "parameter used without validation" in combined:
            return "The code uses incoming data before checking whether it is present, valid, and the right type."
        if ".json()" in combined or ".decode()" in combined:
            return "The code assumes incoming JSON or encoded data is valid and may crash if the payload is malformed."
        if "inconsistent responses" in combined:
            return "This function returns different shapes of data in different situations, so callers cannot rely on one stable contract."
        if "does too much" in combined:
            return "This function is carrying too many responsibilities, which makes it harder to understand and safer changes harder to make."
        if "doesn't say what type of data it expects" in combined or "missing type hints" in combined:
            return "The function signature does not clearly say what inputs and outputs are expected."
        if "might wait forever" in combined or "timeout" in combined:
            return "A database call may hang without a time limit, which can tie up requests and workers."
        if "no pagination" in combined:
            return "This query can ask for too much data at once instead of limiting the result size."
        return issue.description or "This finding needs attention."

    def _issue_plain_impact(self, issue) -> str:
        if issue.risk_explanation:
            return issue.risk_explanation

        title = (issue.title or "").lower()
        desc = (issue.description or "").lower()
        combined = f"{title} {desc}"

        if "silent error" in combined or "swallowed" in combined:
            return "Problems can happen in production with little or no trace, so teams lose time debugging and may miss real failures."
        if "pickle" in combined:
            return "If untrusted data reaches this path, it can become a remote-code-execution risk instead of a normal parsing failure."
        if "functional test failed" in combined:
            return "Users or dependent services may hit a broken endpoint and get an error instead of the expected response."
        if "validation" in combined:
            return "Bad input can turn into server errors, confusing behavior, or inconsistent data."
        if ".json()" in combined or ".decode()" in combined:
            return "Malformed requests can trigger a 500 error instead of a clean client-facing validation response."
        if "inconsistent responses" in combined:
            return "Other parts of the app may break because they cannot safely predict the return format."
        if "timeout" in combined or "wait forever" in combined:
            return "If the database stalls, requests can pile up and make the whole service feel stuck."
        if "no pagination" in combined:
            return "Large responses can waste memory, slow down the API, and eventually crash the service."
        return "This can reduce reliability, increase support/debugging time, or expose the system to avoidable failures."

    def _issue_plain_action(self, issue) -> str:
        if issue.recommendation:
            recommendation = issue.recommendation.strip()
            if recommendation.lower().startswith("recommendation:"):
                return recommendation.split(":", 1)[1].strip()
            return recommendation

        title = (issue.title or "").lower()
        desc = (issue.description or "").lower()
        combined = f"{title} {desc}"

        if "silent error" in combined or "swallowed" in combined:
            return "Log the exception with enough context or re-raise it so the failure is visible and actionable."
        if "pickle" in combined:
            return "Replace pickle with a safer format such as JSON for any data that can come from users, requests, caches, or integrations."
        if "functional test failed" in combined:
            return "Check whether the route exists, whether the server is running on the expected URL, and whether the test matches the real API contract."
        if "validation" in combined:
            return "Validate inputs at the start of the function and fail early with a clear error when the data is missing or malformed."
        if ".json()" in combined or ".decode()" in combined:
            return "Wrap parsing in try/except and return a controlled error response for invalid payloads."
        if "inconsistent responses" in combined:
            return "Standardize the return shape so callers always receive the same type of object or value."
        if "timeout" in combined or "wait forever" in combined:
            return "Add a timeout or other guardrail to the database call."
        if "no pagination" in combined:
            return "Add paging or hard result limits so one request cannot pull the full dataset."
        return "Review this code path and add the missing guardrail or cleanup suggested by the analyzer."

    def _show_issue_detail(self, issue) -> None:
        self.static_detail_title.setText(issue.title)
        self.static_detail_meta.setText(
            f"Severity: {issue.severity.value.upper()}    Category: {issue.issue_type.value.title()}    Location: {issue.location}"
        )
        self.static_detail_body.setPlainText(self._format_issue_for_humans(issue))

    def _show_functional_finding_detail(self, issue) -> None:
        self.functional_detail_title.setText(issue.title)
        self.functional_detail_meta.setText(
            f"Severity: {issue.severity.value.upper()}    Category: {issue.issue_type.value.title()}    Location: {issue.location}"
        )
        self.functional_detail_body.setPlainText(self._format_issue_for_humans(issue))

    def _show_overall_score_detail(self) -> None:
        report = self.current_report
        if report is None:
            return

        scores = report.health_score.to_dict()
        summary = report.to_dict()["summary"]
        sections = [
            f"📊 Overall Health Score: {scores['overall']}/100",
            "This score combines Safety (35%), Speed (30%), Structure (20%), and Trust (15%).",
            (
                "📈 Score Breakdown:\n"
                f"  🔒 Safety:     {scores['security']}/100\n"
                f"  ⚡ Speed:      {scores['performance']}/100\n"
                f"  🏗️  Structure:  {scores['design']}/100\n"
                f"  🛡️  Trust:      {scores['reliability']}/100"
            ),
            (
                "🎯 Findings Summary:\n"
                f"  Total Issues:  {summary['total_issues']}\n"
                f"  Critical (🔴): {summary['critical']}\n"
                f"  Medium (🟡):   {summary['warnings']}\n"
                f"  Info (🔵):     {summary['info']}"
            ),
        ]

        if report.backend_discovery and report.backend_discovery.endpoints:
            sections.append(f"🌐 API Endpoints: {len(report.backend_discovery.endpoints)} discovered")

        if report.functional_summary:
            sections.append(
                "✅ Functional Tests:\n"
                f"  Passed:  {report.functional_summary.passed}\n"
                f"  Failed:  {report.functional_summary.failed}\n"
                f"  Total:   {report.functional_summary.total}"
            )

        self.static_detail_title.setText("Overall Health Score")
        self.static_detail_meta.setText("Summary of your backend's quality metrics")
        self.static_detail_body.setPlainText("\n\n".join(sections))

    def _show_issue_group_detail(self, stat_key: str, severity_filter: Optional[IssueSeverity]) -> None:
        report = self.current_report
        if report is None:
            return

        issues = report.issues
        if severity_filter is not None:
            issues = [issue for issue in issues if issue.severity == severity_filter]

        if not issues:
            label = "findings" if stat_key == "Issues" else stat_key.lower()
            self._set_static_placeholder(
                f"No {stat_key.lower()}",
                f"This analysis report has no {label}.",
            )
            return

        summary_lines = []
        for issue in issues:
            chunk = [
                f"[{issue.severity.value.upper()}] {issue.title}",
                f"Category: {issue.issue_type.value.title()}",
                f"Location: {issue.location}",
                f"What this means: {self._issue_plain_summary(issue)}",
                f"Why it matters: {self._issue_plain_impact(issue)}",
                f"What to do next: {self._issue_plain_action(issue)}",
            ]
            summary_lines.append("\n".join(chunk))

        self.static_detail_title.setText(f"{stat_key}: {len(issues)} finding(s)")
        self.static_detail_meta.setText("Select findings below for context:")
        self.static_detail_body.setPlainText("\n\n".join(summary_lines))

    def _set_static_placeholder(self, title: str, body: str) -> None:
        self.static_detail_title.setText(title)
        self.static_detail_meta.setText("")
        self.static_detail_body.setPlainText(body)

    def _set_functional_placeholder(self, title: str, body: str) -> None:
        self.functional_detail_title.setText(title)
        self.functional_detail_meta.setText("")
        self.functional_detail_body.setPlainText(body)

    def _set_live_placeholder(self, title: str, body: str) -> None:
        self.live_detail_title.setText(title)
        self.live_detail_meta.setText("")
        self.live_detail_body.setPlainText(body)

    def _format_functional_summary(self, functional_summary) -> str:
        sections = [
            "Live API Test Summary",
            f"Source: {functional_summary.config_path}",
            f"Passed: {functional_summary.passed}",
            f"Failed: {functional_summary.failed}",
        ]

        for index, result in enumerate(functional_summary.results, start=1):
            outcome = "PASS" if result.passed else "FAIL"
            chunk = [
                f"Test {index}: {result.name}",
                f"Outcome: {outcome}",
                f"Request sent: {result.request_method or 'GET'} {result.endpoint}",
            ]
            if result.request_headers:
                chunk.append(f"Request headers:\n{json.dumps(result.request_headers, indent=2)}")
            if result.request_body:
                chunk.append(f"Request body:\n{result.request_body}")
            if result.status_code is not None:
                chunk.append(f"HTTP status code: {result.status_code}")
            if result.response_time_ms is not None:
                chunk.append(f"Response time: {result.response_time_ms} ms")
            if result.message:
                chunk.append(f"What happened:\n{result.message}")
            if result.details:
                chunk.append("Why it failed:\n" + "\n".join(f"- {detail}" for detail in result.details))
            if result.response_headers:
                chunk.append(f"Response headers:\n{json.dumps(result.response_headers, indent=2)}")
            if result.response_body is not None:
                chunk.append(f"Response body:\n{result.response_body}")
            sections.append("\n\n".join(chunk))

        return "\n\n".join(sections)

    def _set_request_editors(self, body_text: str, variables_text: str, graphql_enabled: bool) -> None:
        self.query_text.setPlainText(body_text)
        self.variables_text.setPlainText(variables_text)
        self.variables_text.setReadOnly(not graphql_enabled)
        self.variables_text.setEnabled(graphql_enabled)

    def _append_log(self, content: str) -> None:
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(content)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def _reset_log_view(self) -> None:
        self.log_text.setPlainText("Analyzer output will stream here.\n")

    def _clear_report_views(self) -> None:
        self.current_report = None
        self.latest_live_result_text = ""
        self.stat_cards["Overall Score"].set_value("0")
        self.stat_cards["Issues"].set_value("0")
        self.stat_cards["🔴 Critical"].set_value("0")
        self.stat_cards["🟡 Medium"].set_value("0")
        self.stat_cards["🔵 Info"].set_value("0")
        self.live_result_tree.clear()
        self.live_result_lookup = {}
        self.functional_findings_tree.clear()
        self.functional_findings_lookup = {}

        self.backend_runtime_value.setText("Detecting...")
        self.database_type_value.setText("Detecting...")
        self.api_kind_value.setText("Detecting...")
        self.frameworks_value.setText("Scanning...")
        self.endpoint_count_value.setText("Discovering...")
        self.selected_endpoint_label.setText("Analyzing...")

        for metric in self.metric_rows.values():
            metric.set_value(0)

        self.issue_tree.clear()
        placeholder_issue = QTreeWidgetItem(["Scanning codebase...", "", "", ""])
        self.issue_tree.addTopLevelItem(placeholder_issue)
        self.issue_lookup = {placeholder_issue: None}
        self._set_static_placeholder("Analysis running...", "The analyzer is scanning files. Results will appear here soon.")
        self._set_live_placeholder("Analysis running...", "The analyzer is scanning files. Results will appear here soon.")
        self._set_functional_placeholder("Analysis running...", "The analyzer is scanning files. Results will appear here soon.")

        self.endpoint_tree.clear()
        placeholder_endpoint = QTreeWidgetItem(["Finding endpoints...", "", "", ""])
        self.endpoint_tree.addTopLevelItem(placeholder_endpoint)
        self.endpoint_lookup = {placeholder_endpoint: None}

        self.request_mode_badge.setText("Request Mode: Waiting...")
        self.request_hint_label.setText("Results will populate after analysis →")
        self._set_request_editors(
            body_text='{\n  "status": "analyzing..."\n}',
            variables_text="{}",
            graphql_enabled=False,
        )

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setDisabled(busy)
        self.endpoint_run_button.setDisabled(busy)
        self.progress.setVisible(busy)
        self.hero_status.setText("Analyzing..." if busy else "Ready to analyze")

    def _refresh_available_tools(self) -> None:
        try:
            tools = [tool for tool in ("bandit", "flake8") if shutil.which(tool)]
            if tools:
                self.available_tools_label.setText(f"Optional deep scanners detected: {', '.join(tools)}")
                self.hero_hint.setText(f"Optional deep scanners available: {', '.join(tools)}")
            else:
                self.available_tools_label.setText("Optional deep scanners not detected. Core AST analysis is still active.")
                self.hero_hint.setText("Core AST analysis is active. Optional deep scanners are not currently detected.")
        except Exception:
            self.available_tools_label.setText("Optional tool detection unavailable. Core AST analysis is still active.")
            self.hero_hint.setText("Core AST analysis is active. Optional tool detection is unavailable in this environment.")


def launch_gui(initial_path: str = "") -> None:
    """Create and run the desktop interface."""
    if QApplication is None:
        local_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
        if os.path.exists(local_python) and os.path.abspath(sys.executable) != os.path.abspath(local_python):
            os.execv(local_python, [local_python, os.path.abspath(__file__), *sys.argv[1:]])

        print("The GUI now uses PySide6, but it is not installed in this environment.")
        print("Install it with one of these options:")
        print("  python3 -m venv .venv")
        print("  .venv/bin/pip install PySide6")
        print("  .venv/bin/python cli.py")
        sys.exit(1)

    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("No desktop display session was detected, so the Qt GUI cannot open here.")
        print("Run this on your local desktop session, or use CLI mode:")
        print(f"  python3 {os.path.basename(__file__)} --cli /path/to/backend/code")
        sys.exit(1)

    if (
        sys.platform.startswith("linux")
        and os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
        and ctypes.util.find_library("xcb-cursor") is None
    ):
        print("Qt cannot start because the Linux package for xcb cursor support is missing.")
        print("Install `libxcb-cursor0` and then run `python3 cli.py` again.")
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv)
    window = AnalyzerGUI(initial_path=initial_path)
    window.show()
    app.exec()


def main() -> None:
    """
    Launch the GUI by default.

    Use `python cli.py --cli <path>` to keep the original console output mode.
    """
    args = sys.argv[1:]

    if args and args[0] == "--cli":
        if len(args) < 2:
            print("Please give the folder path. How to use:")
            print("\nExample:")
            print("  python cli.py --cli /path/to/backend/code")
            print("  python cli.py --cli ./src")
            sys.exit(1)
        run_analysis(args[1])
        return

    initial_path = args[0] if args else ""
    launch_gui(initial_path)


if __name__ == "__main__":
    main()
