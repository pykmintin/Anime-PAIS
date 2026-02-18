"""
GUI MODULE - FULLY IMPLEMENTED
PySide6 user interface for NDIS Expense Assistant v2.0

Features:
    - Undo system (5-level stack for Confirm/Category/Delete)
    - Progress dialog with filename and error count
    - Structured logging with user feedback
    - Debounced auto-save
    - Thread-safe operations
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Callable
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QComboBox, QPushButton,
    QLabel, QLineEdit, QDialog, QDialogButtonBox, QTextEdit,
    QFileDialog, QMessageBox, QProgressDialog, QHeaderView,
    QAbstractItemView, QScrollArea, QFrame, QMenuBar, QMenu,
    QStatusBar, QToolBar
)
from PySide6.QtCore import Qt, Signal, QObject, QSettings, QTimer
from PySide6.QtGui import QPixmap, QImage, QAction, QFont, QColor

from logger_config import get_logger
from data_utils import AtomicCSV
from ocr_engine import OCREngine
from learning_system import MerchantLearningSystem
from image_viewer import ImageViewerDialog

# Undo framework integration
from undo_framework import (
    UndoStack, 
    ConfirmTransactionAction, 
    CategoryChangeAction,
    DeleteTransactionAction
)

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Primary application window for NDIS Expense Assistant."""
    
    transaction_confirmed = Signal(dict)
    category_changed = Signal(int, str)
    
    def __init__(self, ocr_engine=None, learning_system=None, parent=None):
        super().__init__(parent)
        
        self.ocr_engine = ocr_engine
        self.learning_system = learning_system
        
        # Undo system - 5 level stack, memory only
        self.undo_stack = UndoStack(max_size=5)
        
        self.pending_data: List[Dict] = []
        self.completed_data: List[Dict] = []
        self.categories = [
            "Food", "Transport", "Healthcare", "Supplies", 
            "Utilities", "Entertainment", "Other"
        ]
        
        self.pending_csv = AtomicCSV("pending.csv", [
            'file_hash', 'filename', 'filepath', 'date_raw', 'amount_raw',
            'merchant_raw', 'merchant_normalized', 'category', 'description',
            'status', 'confidence'
        ])
        self.completed_csv = AtomicCSV("completed.csv", [
            'file_hash', 'completed_timestamp', 'filename', 'filepath', 'date_raw', 
            'amount_raw', 'merchant_raw', 'merchant_normalized', 'category', 
            'description', 'status', 'confidence'
        ])
        
        # Debounced save timer
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_pending_data)
        
        self.setWindowTitle("NDIS Expense Assistant v2.0")
        self.resize(1400, 800)
        
        self.init_ui()
        self.load_pending_data()
        self._update_undo_button_state()
        logger.info("MainWindow initialized with undo system")
    
    def init_ui(self) -> None:
        """Initialize user interface."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        self.btn_process = QPushButton("📁 Check New Screenshots")
        self.btn_process.setToolTip("Scan Screenshots folder and process any new images")
        self.btn_process.clicked.connect(self.process_screenshots)
        toolbar.addWidget(self.btn_process)
        
        # Force Reprocess checkbox
        from PySide6.QtWidgets import QCheckBox
        self.chk_force_reprocess = QCheckBox("Force Reprocess")
        self.chk_force_reprocess.setToolTip("Reprocess all images even if already scanned")
        toolbar.addWidget(self.chk_force_reprocess)
        
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setToolTip("Reload data from CSV files")
        self.btn_refresh.clicked.connect(self.refresh_table)
        toolbar.addWidget(self.btn_refresh)
        
        toolbar.addSeparator()
        
        self.btn_view_pending = QPushButton("⏳ Pending")
        self.btn_view_pending.clicked.connect(self.show_pending)
        toolbar.addWidget(self.btn_view_pending)
        
        self.btn_view_completed = QPushButton("✅ Completed")
        self.btn_view_completed.clicked.connect(self.show_completed)
        toolbar.addWidget(self.btn_view_completed)
        
        toolbar.addSeparator()
        
        # Undo button
        self.btn_undo = QPushButton("↩️ Undo")
        self.btn_undo.setToolTip("Undo last action (Confirm, Category change, or Delete)")
        self.btn_undo.clicked.connect(self.undo_last_action)
        self.btn_undo.setEnabled(False)
        toolbar.addWidget(self.btn_undo)
        
        # Status label
        self.lbl_status = QLabel("Ready")
        layout.addWidget(self.lbl_status)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Amount", "Merchant", "Category", "Confidence", "Status", "Actions"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.on_row_double_click)
        layout.addWidget(self.table)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def _update_undo_button_state(self) -> None:
        """Update undo button based on stack state."""
        if self.undo_stack.can_undo():
            action = self.undo_stack.peek()
            self.btn_undo.setEnabled(True)
            self.btn_undo.setToolTip(f"Undo: {action.description()}")
        else:
            self.btn_undo.setEnabled(False)
            self.btn_undo.setToolTip("Nothing to undo")
    
    def undo_last_action(self) -> None:
        """
        Undo the last action from the stack.
        
        Shows error dialog if undo fails. Updates table and button state.
        """
        if not self.undo_stack.can_undo():
            return
        
        action = self.undo_stack.pop()
        action.log_undo_attempt()
        
        # Validate before attempting
        if not action.validate():
            QMessageBox.warning(
                self, "Cannot Undo",
                f"Cannot undo '{action.description()}'.\n\n"
                "The transaction may have been modified or removed."
            )
            self._update_undo_button_state()
            return
        
        try:
            action.undo()
            self.show_pending()
            self._update_undo_button_state()
            self.statusBar().showMessage(f"Undone: {action.description()}", 3000)
            logger.info(f"Undo successful: {action.description()}")
        except Exception as e:
            QMessageBox.critical(
                self, "Undo Failed",
                f"Failed to undo '{action.description()}':\n\n{e}"
            )
            logger.error(f"Undo failed for '{action.description()}': {e}")
            # Try to recover by refreshing data
            self.load_pending_data()
    
    def load_pending_data(self) -> None:
        """Load pending transactions from CSV."""
        try:
            self.pending_data = self.pending_csv.read_all()
            self.show_pending()
        except Exception as e:
            logger.error(f"Failed to load pending data: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load pending data: {e}")
            self.pending_data = []
    
    def show_pending(self) -> None:
        """Display pending transactions."""
        self.table.setRowCount(len(self.pending_data))
        
        for row_idx, transaction in enumerate(self.pending_data):
            # Date
            date_str = transaction.get('date_raw', 'Unknown')
            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            
            # Amount
            amount = transaction.get('amount_raw', '$0.00')
            self.table.setItem(row_idx, 1, QTableWidgetItem(amount))
            
            # Merchant
            merchant = transaction.get('merchant_raw', 'Unknown')
            self.table.setItem(row_idx, 2, QTableWidgetItem(merchant))
            
            # Category (editable dropdown)
            category_combo = QComboBox()
            category_combo.addItems(self.categories)
            current_category = transaction.get('category', 'Other')
            category_combo.setCurrentText(current_category)
            
            # Store old category for undo tracking
            category_combo.setProperty("old_category", current_category)
            category_combo.currentTextChanged.connect(
                lambda text, r=row_idx, combo=category_combo: self.on_category_changed(r, text, combo)
            )
            self.table.setCellWidget(row_idx, 3, category_combo)
            
            # Confidence
            confidence = transaction.get('confidence', 0.0)
            try:
                confidence_val = float(confidence)
            except (ValueError, TypeError):
                confidence_val = 0.0
            conf_str = f"{confidence_val:.0%}"
            conf_item = QTableWidgetItem(conf_str)
            self.table.setItem(row_idx, 4, conf_item)
            
            # Color code row based on confidence (readable colors)
            if confidence_val >= 0.85:
                bg_color = QColor(144, 238, 144)  # Light green
                fg_color = QColor(0, 0, 0)  # Black text
            elif confidence_val >= 0.60:
                bg_color = QColor(255, 200, 100)  # Darker orange (not bright yellow)
                fg_color = QColor(0, 0, 0)  # Black text
            else:
                bg_color = QColor(255, 150, 150)  # Light red
                fg_color = QColor(0, 0, 0)  # Black text
            
            # Bold font for better readability
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)  # Slightly larger
            
            for col in range(6):  # Include status column
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(bg_color)
                    item.setForeground(fg_color)
                    item.setFont(font)
            
            # Status
            status = transaction.get('status', 'pending')
            self.table.setItem(row_idx, 5, QTableWidgetItem(status))
            
            # Actions (Confirm + Delete buttons)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)
            
            btn_done = QPushButton("✓ Confirm")
            btn_done.setToolTip("Move this transaction to completed")
            btn_done.clicked.connect(lambda checked, r=row_idx: self.confirm_transaction(r))
            actions_layout.addWidget(btn_done)
            
            btn_delete = QPushButton("🗑️ Delete")
            btn_delete.setToolTip("Delete this transaction from pending")
            btn_delete.clicked.connect(lambda checked, r=row_idx: self.delete_transaction(r))
            actions_layout.addWidget(btn_delete)
            
            self.table.setCellWidget(row_idx, 6, actions_widget)
        
        self.lbl_status.setText(f"Showing {len(self.pending_data)} pending transactions")
    
    def show_completed(self) -> None:
        """Display completed transactions."""
        try:
            self.completed_data = self.completed_csv.read_all()
        except:
            self.completed_data = []
        
        self.table.setRowCount(len(self.completed_data))
        
        for row_idx, transaction in enumerate(self.completed_data):
            date_str = transaction.get('date_raw', 'Unknown')
            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            
            amount = transaction.get('amount_raw', '$0.00')
            self.table.setItem(row_idx, 1, QTableWidgetItem(amount))
            
            merchant = transaction.get('merchant_raw', 'Unknown')
            self.table.setItem(row_idx, 2, QTableWidgetItem(merchant))
            
            category = transaction.get('category', 'Other')
            self.table.setItem(row_idx, 3, QTableWidgetItem(category))
            
            self.table.setItem(row_idx, 4, QTableWidgetItem("Completed"))
            self.table.setItem(row_idx, 5, QTableWidgetItem("done"))
            self.table.setItem(row_idx, 6, QTableWidgetItem("-"))
        
        self.lbl_status.setText(f"Showing {len(self.completed_data)} completed transactions")
    
    def refresh_table(self) -> None:
        """Refresh table data."""
        self.load_pending_data()
    
    def add_transaction(self, transaction: dict) -> None:
        """
        Add a new transaction from the orchestrator.
        Called when orchestrator emits transaction_ready signal.
        
        Args:
            transaction: Transaction dictionary from OCR processing
        """
        try:
            # Check for duplicates
            file_hash = transaction.get('file_hash', '')
            if self.is_duplicate(file_hash):
                logger.info(f"Duplicate transaction skipped: {transaction.get('merchant_raw', 'Unknown')}")
                return
            
            # Add to pending data
            self.pending_data.append(transaction)
            
            # Save to CSV
            self.pending_csv.append_row(transaction)
            
            # Refresh display
            self.show_pending()
            
            logger.info(f"Transaction added: {transaction.get('merchant_raw', 'Unknown')}")
            self.statusBar().showMessage(
                f"New transaction: {transaction.get('merchant_raw', 'Unknown')}", 3000
            )
            
        except Exception as e:
            logger.error(f"Failed to add transaction: {e}")
            self.statusBar().showMessage(f"Error adding transaction: {e}", 5000)
    
    def on_category_changed(self, row: int, new_category: str, combo: QComboBox) -> None:
        """Handle category change with undo tracking and debounced save."""
        if 0 <= row < len(self.pending_data):
            old_category = combo.property("old_category")
            
            # Only track if actually changed
            if old_category != new_category:
                # Create undo action
                action = CategoryChangeAction(
                    row, old_category, new_category,
                    self.pending_data, self.pending_csv
                )
                self.undo_stack.push(action)
                self._update_undo_button_state()
                
                # Update stored old category
                combo.setProperty("old_category", new_category)
                
                self.pending_data[row]['category'] = new_category
                self.save_timer.start(1000)  # Debounced save
                self.statusBar().showMessage(f"Category changed to {new_category}", 1000)
                logger.debug(f"Category updated for row {row}: {new_category}")
    
    def _save_pending_data(self) -> None:
        """Save pending data to CSV."""
        try:
            self.pending_csv.write_all(self.pending_data)
            self.statusBar().showMessage("Saved", 2000)
            logger.info("Pending data auto-saved")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save changes: {e}")
            logger.error(f"Auto-save failed: {e}")
    
    def on_row_double_click(self, row: int, column: int) -> None:
        """Handle double-click on table row - open image viewer."""
        if 0 <= row < len(self.pending_data):
            transaction = self.pending_data[row]
            filepath = transaction.get('filepath', '')
            
            if filepath and Path(filepath).exists():
                dialog = ImageViewerDialog(Path(filepath), transaction, self)
                result = dialog.exec()
                
                if result == ImageViewerDialog.Rejected:
                    logger.info(f"User marked transaction as needing fix: {transaction.get('merchant_raw', 'Unknown')}")
                    self.statusBar().showMessage("Transaction needs manual review", 3000)
            else:
                QMessageBox.warning(self, "File Not Found", 
                    f"Screenshot file not found:\n{filepath}")
                logger.warning(f"Image file not found: {filepath}")
    
    def confirm_transaction(self, row: int) -> None:
        """Move transaction from pending to completed."""
        # Ensure any pending save completes first
        if self.save_timer.isActive():
            self.save_timer.stop()
            self._save_pending_data()
        
        if 0 <= row < len(self.pending_data):
            # Confirmation dialog
            transaction = self.pending_data[row]
            merchant = transaction.get('merchant_raw', 'Unknown')
            amount = transaction.get('amount_raw', '$0.00')
            
            reply = QMessageBox.question(
                self, 'Confirm Transaction',
                f"Confirm this transaction?\n\nMerchant: {merchant}\nAmount: {amount}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Create undo action BEFORE removing
            undo_action = ConfirmTransactionAction(
                transaction, self.pending_data, self.completed_data,
                self.pending_csv, self.completed_csv
            )
            self.undo_stack.push(undo_action)
            
            transaction = self.pending_data.pop(row)
            
            # Record in learning system
            if self.learning_system:
                merchant = transaction.get('merchant_normalized', transaction.get('merchant_raw', ''))
                category = transaction.get('category', 'Other')
                self.learning_system.record_confirmation(merchant, category)
            
            # Add to completed
            transaction['completed_timestamp'] = datetime.now().isoformat()
            transaction['status'] = 'completed'
            self.completed_data.append(transaction)
            
            # Save both CSVs
            try:
                self.pending_csv.write_all(self.pending_data)
                self.completed_csv.append_row(transaction)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")
                logger.error(f"Failed to move transaction: {e}")
                return
            
            # Refresh display
            self.show_pending()
            self._update_undo_button_state()
            
            logger.info(f"Transaction confirmed: {transaction.get('merchant_raw', 'Unknown')}")
            self.statusBar().showMessage(f"Confirmed: {transaction.get('merchant_raw', 'Unknown')}")
    
    def delete_transaction(self, row: int) -> None:
        """Delete transaction from pending list."""
        if 0 <= row < len(self.pending_data):
            transaction = self.pending_data[row]
            merchant = transaction.get('merchant_raw', 'Unknown')
            
            reply = QMessageBox.question(
                self, 'Delete Transaction',
                f"Delete this transaction?\n\nMerchant: {merchant}\n\n"
                "(Can be undone with the Undo button)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Create undo action BEFORE deleting
            undo_action = DeleteTransactionAction(
                transaction, row, self.pending_data, self.pending_csv
            )
            self.undo_stack.push(undo_action)
            
            # Remove from list
            self.pending_data.pop(row)
            
            # Save
            try:
                self.pending_csv.write_all(self.pending_data)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
                logger.error(f"Failed to delete transaction: {e}")
                return
            
            self.show_pending()
            self._update_undo_button_state()
            
            logger.info(f"Transaction deleted: {merchant}")
            self.statusBar().showMessage(f"Deleted: {merchant}", 3000)
    
    def process_screenshots(self) -> None:
        """Process all screenshots in all batches (runs in background thread)."""
        if not self.ocr_engine:
            QMessageBox.warning(self, "Error", "OCR Engine not initialized")
            return
        
        # Scan ALL receipt batches
        receipts_root = Path("../receipts")
        screenshot_files = []
        
        if receipts_root.exists():
            # Scan all batch folders
            for batch_dir in sorted(receipts_root.glob("batch_*")):
                if batch_dir.is_dir():
                    screenshot_files.extend(list(batch_dir.glob("*.jpg")))
        
        # Fallback to Screenshots folder if no batches found
        if not screenshot_files:
            screenshot_dir = Path("Screenshots")
            if screenshot_dir.exists():
                screenshot_files = list(screenshot_dir.rglob("*.jpg"))
        
        if not screenshot_files:
            QMessageBox.warning(self, "Error", f"No receipts found in {receipts_root.absolute()}")
            return
        
        if not screenshot_files:
            QMessageBox.information(self, "Info", "No screenshots found")
            return
        
        # Disable button during processing
        self.btn_process.setEnabled(False)
        self.statusBar().showMessage(f"Processing {len(screenshot_files)} screenshots...")
        
        # Process in background to keep UI responsive
        from PySide6.QtCore import QThread, Signal
        
        class ProcessingThread(QThread):
            progress = Signal(int)
            finished_processing = Signal(int, int)  # processed_count, error_count
            error = Signal(str)
            
            def __init__(self, parent, files, ocr, learning_system, pending_data, completed_data, force_reprocess=False):
                super().__init__(parent)
                self.files = files
                self.ocr = ocr
                self.learning_system = learning_system
                self.pending_data = pending_data
                self.completed_data = completed_data
                self.force_reprocess = force_reprocess
                self.processed = 0
                self.errors = 0
                self.new_transactions = []
                self._cancel_requested = False
            
            def cancel(self):
                """Thread-safe cancel request."""
                self._cancel_requested = True
                logger.debug("Cancel requested for processing thread")
            
            def compute_hash(self, filepath):
                import hashlib
                h = hashlib.md5()
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        h.update(chunk)
                return h.hexdigest()
            
            def is_duplicate(self, file_hash):
                if self.force_reprocess:
                    # Remove old entry if exists
                    self.pending_data[:] = [item for item in self.pending_data if item.get('file_hash') != file_hash]
                    return False
                for item in self.pending_data + self.completed_data:
                    if item.get('file_hash') == file_hash:
                        return True
                return False
            
            def guess_category(self, merchant):
                if self.learning_system:
                    category, _ = self.learning_system.suggest_category(merchant)
                    if category:
                        return category
                
                merchant_lower = merchant.lower()
                if any(word in merchant_lower for word in ['bakery', 'cafe', 'food', 'muffin', 'restaurant']):
                    return "Food"
                elif any(word in merchant_lower for word in ['health', 'medical', 'pharmacy']):
                    return "Healthcare"
                elif any(word in merchant_lower for word in ['petrol', 'fuel', 'shell', 'bp']):
                    return "Transport"
                elif any(word in merchant_lower for word in ['mobile', 'phone', 'internet']):
                    return "Utilities"
                return "Other"
            
            def run(self):
                for i, screenshot_path in enumerate(self.files):
                    # Check for cancel
                    if self._cancel_requested:
                        logger.info(f"Processing cancelled after {self.processed} files")
                        break
                    
                    self.progress.emit(i)
                    
                    try:
                        file_hash = self.compute_hash(screenshot_path)
                        if self.is_duplicate(file_hash):
                            continue
                        
                        result = self.ocr.extract_transaction(screenshot_path)
                        
                        if result.get('success'):
                            # Rename file with date-based filename
                            new_path = self.rename_with_date(screenshot_path, result)
                            if new_path:
                                screenshot_path = new_path
                            
                            transaction = {
                                'file_hash': file_hash,
                                'filename': screenshot_path.name,
                                'filepath': str(screenshot_path),
                                'date_raw': result.get('date_raw', 'Unknown'),
                                'amount_raw': result.get('amount_raw', '$0.00'),
                                'merchant_raw': result.get('merchant_raw', 'Unknown'),
                                'merchant_normalized': self.learning_system.normalize_merchant(result.get('merchant_raw', '')) if self.learning_system else '',
                                'category': self.guess_category(result.get('merchant_raw', '')),
                                'description': '',
                                'status': 'pending',
                                'confidence': result.get('confidence', 0.0)
                            }
                            self.new_transactions.append(transaction)
                            self.processed += 1
                    
                    except Exception as e:
                        self.error.emit(f"Failed to process {screenshot_path}: {e}")
                        self.errors += 1
                
                self.progress.emit(len(self.files))
                self.finished_processing.emit(self.processed, self.errors)
            
            def rename_with_date(self, image_path, result):
                """Rename file to YYYY-MM-DD_Merchant_Amount.jpg format."""
                import re
                
                try:
                    date_str = result.get('date_raw', '')
                    merchant = result.get('merchant_raw', 'Unknown')
                    amount = result.get('amount_raw', '')
                    
                    # Parse date to ISO format
                    iso_date = self.parse_date_to_iso(date_str)
                    if not iso_date:
                        return None
                    
                    # Sanitize merchant name
                    safe_merchant = self.sanitize_filename(merchant)
                    
                    # Generate new filename
                    new_name = f"{iso_date}_{safe_merchant}_{amount}{image_path.suffix}"
                    new_path = image_path.parent / new_name
                    
                    # Handle duplicates
                    counter = 1
                    original_new_path = new_path
                    while new_path.exists():
                        stem = original_new_path.stem
                        new_path = image_path.parent / f"{stem}_{counter}{image_path.suffix}"
                        counter += 1
                    
                    # Rename file
                    image_path.rename(new_path)
                    logger.info(f"Renamed: {image_path.name} -> {new_path.name}")
                    return new_path
                    
                except Exception as e:
                    logger.error(f"Rename failed: {e}")
                    return None
            
            def parse_date_to_iso(self, date_str):
                """Convert '13 May 2025' to '2025-05-13'."""
                month_map = {
                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                }
                
                pattern = r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
                match = re.match(pattern, date_str, re.IGNORECASE)
                
                if match:
                    day, month, year = match.groups()
                    month_num = month_map.get(month.lower(), '00')
                    day_num = day.zfill(2)
                    return f"{year}-{month_num}-{day_num}"
                
                return None
            
            def sanitize_filename(self, text, max_length=30):
                """Convert text to safe filename."""
                # Remove unsafe characters including:
                # - Windows reserved: \ / : * ? " < > |
                # - Shell special: & ; $ ` ! ( ) [ ] { } | * ? < > # @
                # - OCR artifacts: = ~ ^ % +
                # - Quotes: ' " `
                text = re.sub(r'[\\\\/*?:"<>|()\[\]{}&;!$`~^%+=@#\'"]', '', text)
                text = re.sub(r'\s+', '-', text)
                text = re.sub(r'-+', '-', text)
                text = text.strip('-')
                
                # Truncate if too long
                if len(text) > max_length:
                    text = text[:max_length]
                
                return text
        
        # Create and start thread
        self.processing_thread = ProcessingThread(
            self, screenshot_files, self.ocr_engine, self.learning_system,
            self.pending_data, self.completed_data,
            force_reprocess=self.chk_force_reprocess.isChecked()
        )
        
        # Enhanced progress dialog
        self.progress_dialog = QProgressDialog(
            "Scanning screenshots...", "Cancel", 0, len(screenshot_files), self
        )
        self.progress_dialog.setWindowTitle("Processing Screenshots")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        
        # Track current file for display
        self._current_processing_file = ""
        self._processed_count = 0
        self._error_count = 0
        
        def update_progress(current):
            # Get current file name
            if current < len(screenshot_files):
                self._current_processing_file = screenshot_files[current].name
            
            # Update dialog text with filename and stats
            self.progress_dialog.setLabelText(
                f"Processing: {self._current_processing_file}\n"
                f"({self._processed_count} of {len(screenshot_files)}, {self._error_count} errors)"
            )
            self.progress_dialog.setValue(current)
        
        def on_finished(processed, errors):
            self.progress_dialog.close()
            self.pending_data.extend(self.processing_thread.new_transactions)
            if self.processing_thread.new_transactions:
                self.pending_csv.write_all(self.pending_data)
                self.show_pending()
            
            self.btn_process.setEnabled(True)
            
            # Show completion summary
            if errors > 0:
                QMessageBox.warning(
                    self, "Processing Complete",
                    f"Processed {processed} new screenshots\n"
                    f"⚠️ {errors} errors occurred\n\n"
                    f"Check the log file for details."
                )
            else:
                QMessageBox.information(
                    self, "Processing Complete",
                    f"Successfully processed {processed} new screenshots"
                )
            
            self.statusBar().showMessage(f"Processed {processed} new screenshots ({errors} errors)")
            logger.info(f"Screenshot processing complete: {processed} new, {errors} errors")
        
        def on_error(msg):
            self._error_count += 1
            logger.error(msg)
        
        def on_progress(current):
            # Update processed count (approximate)
            if current > self._processed_count:
                self._processed_count = current
            update_progress(current)
        
        # Connect cancel button
        self.progress_dialog.canceled.connect(
            lambda: self.processing_thread.cancel()
        )
        
        self.processing_thread.progress.connect(on_progress)
        self.processing_thread.finished_processing.connect(on_finished)
        self.processing_thread.error.connect(on_error)
        self.processing_thread.start()
    
    def compute_hash(self, filepath: Path) -> str:
        """Compute MD5 hash of file."""
        import hashlib
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def is_duplicate(self, file_hash: str) -> bool:
        """Check if file hash already exists."""
        for item in self.pending_data + self.completed_data:
            if item.get('file_hash') == file_hash:
                return True
        return False
    
    def guess_category(self, merchant: str) -> str:
        """Guess category based on learning system."""
        if self.learning_system:
            category, _ = self.learning_system.suggest_category(merchant)
            if category:
                return category
        
        # Default categorization
        merchant_lower = merchant.lower()
        if any(word in merchant_lower for word in ['bakery', 'cafe', 'food', 'muffin', 'restaurant']):
            return "Food"
        elif any(word in merchant_lower for word in ['health', 'medical', 'pharmacy']):
            return "Healthcare"
        elif any(word in merchant_lower for word in ['petrol', 'fuel', 'shell', 'bp']):
            return "Transport"
        elif any(word in merchant_lower for word in ['mobile', 'phone', 'internet']):
            return "Utilities"
        return "Other"
    
    def closeEvent(self, event) -> None:
        """Handle window close - save pending changes and cleanup threads."""
        # Save any pending changes
        if self.save_timer.isActive():
            self.save_timer.stop()
            self._save_pending_data()
        
        # Clean up processing thread
        if hasattr(self, 'processing_thread') and self.processing_thread:
            if self.processing_thread.isRunning():
                self.processing_thread.cancel()  # Request cancel
                self.processing_thread.quit()
                if not self.processing_thread.wait(2000):  # Wait up to 2 seconds
                    self.processing_thread.terminate()  # Force terminate if needed
        
        # Clear undo stack (memory only, not persisted)
        self.undo_stack.clear()
        
        logger.info("MainWindow closing - cleanup complete")
        event.accept()
