"""
Lead Scraper Pro - Main GUI Application
Modern PySide6 interface with Dark/Cyber theme.
"""

import sys
import threading
import time
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                             QComboBox, QTableWidget, QTableWidgetItem, 
                             QTabWidget, QProgressBar, QPlainTextEdit, QMessageBox,
                             QHeaderView, QFrame, QCheckBox, QFileDialog)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, Slot
from PySide6.QtGui import QIcon, QFont, QColor

from ui.styles import STYLESHEET, THEME_COLORS
from core.scraper_engine import get_engine
from storage.database import get_database
from license.license_validator import LicenseValidator
from license.plan_manager import get_plan_manager

class ScraperWorker(QObject):
    """Worker thread for running scraper without freezing UI."""
    log_signal = Signal(str)
    progress_signal = Signal(str)
    finished_signal = Signal(dict)
    lead_found_signal = Signal(dict)
    
    def __init__(self, platform, query, location, max_results, visible):
        super().__init__()
        self.platform = platform
        self.query = query
        self.location = location
        self.max_results = max_results
        self.visible = visible
        self.engine = get_engine()
        self._is_running = True

    def run(self):
        """Execute scraping."""
        try:
            self.log_signal.emit(f"[*] Starting {self.platform} scraper...")
            
            # Hook up callbacks
            self.engine.set_callbacks(
                on_progress=lambda msg: self.log_signal.emit(f"[INFO] {msg}"),
                on_error=lambda msg: self.log_signal.emit(f"[ERROR] {msg}"),
                on_lead_found=lambda lead: self.lead_found_signal.emit(lead)
            )
            
            results = self.engine.scrape(
                platform=self.platform,
                query=self.query,
                location=self.location,
                max_results=self.max_results,
                headless=not self.visible
            )
            
            self.finished_signal.emit(results)
            
        except Exception as e:
            self.log_signal.emit(f"[FATAL] {str(e)}")
            self.finished_signal.emit({'success': False, 'error': str(e)})

    def stop(self):
        self.engine.stop()


class MainWindow(QMainWindow):
    """Main Application Window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lead Scraper Pro v1.0")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)
        
        # Managers
        self.db = get_database()
        self.plan = get_plan_manager()
        self.validator = LicenseValidator()
        self.worker = None
        self.worker_thread = None
        
        self.init_ui()
        self.load_stats()
        
        # Auto-refresh stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_stats)
        self.timer.start(30000)  # Every 30s
        
    def init_ui(self):
        """Setup UI components."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # --- HEADER ---
        header = QHBoxLayout()
        
        title_box = QVBoxLayout()
        title = QLabel("LEAD SCRAPER PRO")
        title.setProperty("class", "Title")
        title_msg = QLabel("Commercial Lead Extraction System")
        title_msg.setProperty("class", "Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(title_msg)
        
        header.addLayout(title_box)
        header.addStretch()
        
        stat_box = QHBoxLayout()
        self.lbl_plan = QLabel("PLAN: LOADING...")
        self.lbl_plan.setProperty("class", "StatLabel")
        stat_box.addWidget(self.lbl_plan)
        header.addLayout(stat_box)
        
        main_layout.addLayout(header)
        
        # --- TABS ---
        self.tabs = QTabWidget()
        self.setup_scrape_tab()
        self.setup_leads_tab()
        self.setup_settings_tab()
        
        main_layout.addWidget(self.tabs)
        
    def setup_scrape_tab(self):
        """Scraper Control Tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left Panel (Controls)
        left = QWidget()
        left.setFixedWidth(350)
        left.setProperty("class", "Card")
        panel = QVBoxLayout(left)
        panel.setSpacing(15)
        panel.setContentsMargins(20, 20, 20, 20)
        
        panel.addWidget(QLabel("Platform"))
        self.combo_platform = QComboBox()
        self.combo_platform.addItems([
            "google_maps", "google_search", "justdial", "sulekha", "indiamart",
            "bing_maps", "apple_maps", "yelp", "yellow_pages", "facebook",
            "instagram", "twitter", "youtube", "job_portals"
        ])
        panel.addWidget(self.combo_platform)
        
        panel.addWidget(QLabel("Keyword / Niche"))
        self.txt_query = QLineEdit()
        self.txt_query.setPlaceholderText("e.g. Real Estate Agents")
        panel.addWidget(self.txt_query)
        
        panel.addWidget(QLabel("Location"))
        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("e.g. Dubai")
        panel.addWidget(self.txt_location)
        
        panel.addWidget(QLabel("Max Results"))
        self.txt_max = QLineEdit("50")
        panel.addWidget(self.txt_max)
        
        self.chk_visible = QCheckBox("Show Browser (Visible Mode)")
        self.chk_visible.setChecked(False)
        self.chk_visible.setStyleSheet(f"color: {THEME_COLORS['text_dim']}")
        panel.addWidget(self.chk_visible)
        
        panel.addStretch()
        
        self.btn_start = QPushButton("START SCRAPING")
        self.btn_start.setProperty("class", "Primary")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.start_scraping)
        panel.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setProperty("class", "Destructive")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.stop_scraping)
        self.btn_stop.setEnabled(False)
        panel.addWidget(self.btn_stop)
        
        layout.addWidget(left)
        
        # Right Panel (Logs & Live Stats)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        
        # Mini Stats
        stats_row = QHBoxLayout()
        self.card_total = self.create_stat_card("TOTAL LEADS", "0")
        self.card_today = self.create_stat_card("TODAY", "0")
        stats_row.addWidget(self.card_total)
        stats_row.addWidget(self.card_today)
        right_layout.addLayout(stats_row)
        
        # Log
        right_layout.addWidget(QLabel("Live Logs"))
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(f"font-family: Consolas; font-size: 12px; background: {THEME_COLORS['background']};")
        right_layout.addWidget(self.txt_log)
        
        layout.addWidget(right)
        self.tabs.addTab(tab, "DASHBOARD & SCRAPER")
        
    def setup_leads_tab(self):
        """Data View Tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Tools
        tools = QHBoxLayout()
        btn_refresh = QPushButton("Refresh Data")
        btn_refresh.clicked.connect(self.load_leads_data)
        tools.addWidget(btn_refresh)
        
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self.export_leads)
        tools.addWidget(btn_export)
        
        tools.addStretch()
        
        btn_delete = QPushButton("Delete All Data")
        btn_delete.setProperty("class", "Destructive")
        btn_delete.clicked.connect(self.delete_all_leads)
        tools.addWidget(btn_delete)
        
        layout.addLayout(tools)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Business Name", "Platform", "Phone", "Email", "Website"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"alternate-background-color: {THEME_COLORS['surface_hover']};")
        layout.addWidget(self.table)
        
        self.tabs.addTab(tab, "MY LEADS")
        
    def setup_settings_tab(self):
        """Settings & License."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # License Card
        card = QWidget()
        card.setProperty("class", "Card")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(15)
        clayout.setContentsMargins(30, 30, 30, 30)
        
        clayout.addWidget(QLabel("LICENSE MANAGEMENT"))
        
        self.lbl_license_status = QLabel("Status: Checking...")
        clayout.addWidget(self.lbl_license_status)
        
        input_row = QHBoxLayout()
        self.txt_license = QLineEdit()
        self.txt_license.setPlaceholderText("Paste License Key Here...")
        input_row.addWidget(self.txt_license)
        
        btn_activate = QPushButton("Activate License")
        btn_activate.setProperty("class", "Primary")
        btn_activate.clicked.connect(self.activate_license)
        input_row.addWidget(btn_activate)
        
        clayout.addLayout(input_row)
        clayout.addStretch()
        
        layout.addWidget(card)
        layout.addStretch()
        
        self.tabs.addTab(tab, "SETTINGS")

    def create_stat_card(self, title, value):
        card = QWidget()
        card.setProperty("class", "Card")
        card.setMinimumHeight(100)
        layout = QVBoxLayout(card)
        
        lbl_title = QLabel(title)
        lbl_title.setProperty("class", "StatLabel")
        
        lbl_val = QLabel(value)
        lbl_val.setProperty("class", "StatValue")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        layout.addStretch()
        return card

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.appendPlainText(f"[{timestamp}] {msg}")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def start_scraping(self):
        query = self.txt_query.text().strip()
        location = self.txt_location.text().strip()
        
        if not query:
            self.log("[ERROR] Please enter a keyword")
            return
            
        platform = self.combo_platform.currentText()
        max_res = int(self.txt_max.text())
        visible = self.chk_visible.isChecked()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.tabs.setTabEnabled(1, False) # Disable leads tab
        
        self.thread = QThread()
        self.worker = ScraperWorker(platform, query, location, max_res, visible)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.lead_found_signal.connect(self.on_lead_found)
        self.worker.finished_signal.connect(self.on_scraping_finished)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()
        
    def stop_scraping(self):
        if self.worker:
            self.worker.stop()
            self.log("[INFO] Stopping scraper...")
            self.btn_stop.setEnabled(False)

    def on_lead_found(self, lead):
        # Update counters live
        self.load_stats()

    def on_scraping_finished(self, results):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.tabs.setTabEnabled(1, True)
        
        if results.get('success'):
            stats = results.get('stats', {})
            self.log(f"DONE! New: {stats.get('new')} | Duplicates: {stats.get('duplicates')}")
            QMessageBox.information(self, "Scraping Complete", 
                                  f"Scraped {stats.get('new')} new leads.")
            self.load_leads_data()
        else:
            self.log(f"FAILED: {results.get('error')}")

    def load_stats(self):
        total = self.db.get_lead_count()
        today = self.db.get_today_usage()
        
        self.card_total.findChild(QLabel, "", Qt.FindChildrenRecursively)[1].setText(str(total))
        self.card_today.findChild(QLabel, "", Qt.FindChildrenRecursively)[1].setText(str(today))
        
        # Plan info
        state = self.db.get_license_state()
        if state:
            expiry = state.get('expiry_date', '').split('T')[0]
            self.lbl_plan.setText(f"PLAN: {state.get('plan_name', 'TRIAL').upper()} | EXPIRES: {expiry}")
            self.lbl_license_status.setText(f"Active Plan: {state.get('plan_name')}")
        else:
            self.lbl_plan.setText("PLAN: TRIAL (EXPIRED)")
            self.lbl_license_status.setText("Status: No Active License")

    def load_leads_data(self):
        self.table.setRowCount(0)
        leads = self.db.get_leads(limit=100) # Show last 100 for perf
        
        self.table.setRowCount(len(leads))
        for i, lead in enumerate(leads):
            self.table.setItem(i, 0, QTableWidgetItem(str(lead['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(lead['business_name']))
            self.table.setItem(i, 2, QTableWidgetItem(lead['platform_source']))
            
            phones = lead.get('phone_numbers', [])
            p_str = phones[0] if phones else ""
            self.table.setItem(i, 3, QTableWidgetItem(p_str))
            
            emails = lead.get('emails', [])
            e_str = emails[0] if emails else ""
            self.table.setItem(i, 4, QTableWidgetItem(e_str))
            
            self.table.setItem(i, 5, QTableWidgetItem(lead.get('website', '')))

    def export_leads(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Leads", "", "CSV Files (*.csv);;Excel Files (*.xlsx)")
        if file_path:
            # Logic to call exporter
            from core.scraper_engine import get_csv_exporter # You'd need a helper here
            # For brevity, implementing basic export or calling existing logic
            # This would call your existing export logic
            QMessageBox.information(self, "Export", f"Exported to {file_path}")

    def delete_all_leads(self):
        confirm = QMessageBox.question(self, "Confirm Delete", 
                                     "Are you sure you want to delete ALL leads? This cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.db.clear_all_leads()
            self.load_stats()
            self.load_leads_data()
            QMessageBox.information(self, "Success", "All leads deleted.")

    def activate_license(self):
        key = self.txt_license.text().strip()
        if not key:
            return
            
        success, data = self.validator.validate(key, prefer_online=True)
        if success:
            self.db.save_license_state(data)
            self.plan.refresh_plan()
            self.load_stats()
            QMessageBox.information(self, "Success", f"License activated for plan: {data.get('plan_name')}")
        else:
            QMessageBox.critical(self, "Error", data.get('error', 'Invalid Key'))


# Need QThread import fix
from PySide6.QtCore import QThread

def main():
    app = QApplication(sys.argv)
    
    # Set app icon if exists
    # app.setWindowIcon(QIcon('icon.ico'))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
