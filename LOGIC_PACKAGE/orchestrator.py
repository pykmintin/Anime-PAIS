"""
ORCHESTRATOR MODULE
File watching, processing pipeline, and backup management for NDIS Expense Assistant v2.0

Responsibilities:
1. FileSystemWatcher - Auto-detect new screenshots (watchdog 5s polling)
2. ProcessingPipeline - Hash → OCR → Validate → Organize → Update CSV
3. BackupManager - Startup backup to prevent data loss
4. Signal-based coordination with GUI

Usage:
    from orchestrator import Orchestrator
    
    orch = Orchestrator(gui_reference)
    orch.start_watching()  # Auto-detect new files
    orch.process_new_file("screenshot.jpg")  # Manual trigger
"""

import os
import shutil
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QThread

# Optional watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    print("Warning: watchdog not installed. Auto-detection disabled.")

from data_utils import AtomicCSV, ContentHasher
from ocr_engine import OCREngine
from learning_system import MerchantLearningSystem
from logger_config import get_logger

logger = get_logger(__name__)


class BackupManager:
    """
    Startup backup manager - prevents data loss.
    
    Creates timestamped backup of pending.csv on startup.
    Maintains last 10 backups (auto-cleanup).
    """
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = 10
    
    def startup_backup(self, pending_csv: str = "pending.csv") -> Optional[Path]:
        """
        Create backup on application startup.
        
        Returns:
            Path to backup file or None if pending.csv doesn"t exist
        """
        pending = Path(pending_csv)
        if not pending.exists():
            logger.info("No pending.csv to backup")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"pending_{timestamp}.csv"
        
        shutil.copy2(pending, backup_path)
        logger.info(f"Startup backup created: {backup_path}")
        
        # Cleanup old backups (keep last 10)
        self._cleanup_old_backups()
        
        return backup_path
    
    def _cleanup_old_backups(self):
        """Remove old backups, keep only max_backups."""
        backups = sorted(self.backup_dir.glob("pending_*.csv"))
        if len(backups) > self.max_backups:
            for old in backups[:-self.max_backups]:
                old.unlink()
                logger.debug(f"Removed old backup: {old}")


class ProcessingPipeline:
    """
    Processing pipeline: Hash → OCR → Validate → Organize → Update CSV
    
    Single responsibility: Process one screenshot end-to-end.
    """
    
    def __init__(self):
        self.hasher = ContentHasher()
        self.ocr = OCREngine()
        self.learning = MerchantLearningSystem()
        
        # CSV handlers
        self.pending_csv = AtomicCSV("pending.csv", [
            "file_hash", "filename", "filepath", "date_raw", "amount_raw",
            "merchant_raw", "merchant_normalized", "category", "description",
            "status", "confidence"
        ])
    
    def process(self, image_path: str, gui_callback: Optional[Callable] = None) -> dict:
        """
        Process a single screenshot through the pipeline.
        
        Pipeline:
        1. Hash file (duplicate detection)
        2. OCR extraction
        3. Validate transaction
        4. Suggest category (learning system)
        5. Calculate target filename
        6. Add to pending.csv FIRST (before rename)
        7. Rename file (after CSV write)
        8. Notify GUI (if callback provided)
        
        Returns:
            Result dict with status, transaction data, or error
        """
        image_path = Path(image_path)
        
        try:
            # Step 1: Hash
            file_hash = self.hasher.calculate_hash(image_path)
            
            # Check for duplicates
            existing = self._find_by_hash(file_hash)
            if existing:
                logger.info(f"Duplicate detected: {image_path.name}")
                return {"status": "duplicate", "hash": file_hash}
            
            # Step 2: OCR
            logger.info(f"Processing: {image_path.name}")
            transaction = self.ocr.extract_transaction(image_path)
            
            if not transaction:
                logger.warning(f"OCR failed: {image_path.name}")
                return {"status": "ocr_failed", "path": str(image_path)}
            
            # Step 3: Validate
            if not self._is_valid(transaction):
                logger.warning(f"Validation failed: {image_path.name}")
                return {"status": "invalid", "path": str(image_path)}
            
            # Step 4: Suggest category
            merchant = transaction.get("merchant_normalized", "")
            if merchant:
                category, conf = self.learning.suggest_category(merchant)
                if category:
                    transaction["category"] = category
                    transaction["confidence"] = conf
            
            # Step 5: Calculate target filename (for CSV)
            target_path = self._calculate_target_path(image_path, transaction)
            
            # Step 6: Add to pending CSV FIRST (before rename)
            row = {
                "file_hash": file_hash,
                "filename": target_path.name,
                "filepath": str(target_path),
                "date_raw": transaction.get("date_raw", ""),
                "amount_raw": transaction.get("amount_raw", ""),
                "merchant_raw": transaction.get("merchant_raw", ""),
                "merchant_normalized": transaction.get("merchant_normalized", ""),
                "category": transaction.get("category", "Other"),
                "description": "",  # To be filled by user
                "status": "pending",
                "confidence": transaction.get("confidence", 0.0)
            }
            
            self.pending_csv.append_row(row)
            
            # Step 7: NOW rename the file (CSV already has entry)
            if target_path != image_path:
                try:
                    image_path.rename(target_path)
                    logger.info(f"Renamed: {image_path.name} -> {target_path.name}")
                except Exception as e:
                    # Rename failed but CSV already has entry
                    # Log error but don't fail - file is still at original path
                    logger.error(f"Rename failed after CSV write: {e}")
                    logger.warning(f"File remains at original path: {image_path}")
                    # Update CSV with original path
                    row["filename"] = image_path.name
                    row["filepath"] = str(image_path)
                    self.pending_csv.write_all(self.pending_csv.read_all())
            
            # Step 8: Notify GUI
            if gui_callback:
                gui_callback(row)
            
            logger.info(f"Processed: {target_path.name} -> {row['merchant_raw']}")
            return {"status": "success", "transaction": row}
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return {"status": "error", "error": str(e), "path": str(image_path)}
    
    def _find_by_hash(self, file_hash: str) -> bool:
        """Check if hash exists in pending or completed."""
        try:
            pending = self.pending_csv.read_all()
            for row in pending:
                if row.get("file_hash") == file_hash:
                    return True
            
            # Check completed too
            completed = AtomicCSV("completed.csv", self.pending_csv.fieldnames)
            for row in completed.read_all():
                if row.get("file_hash") == file_hash:
                    return True
        except Exception:
            pass
        return False
    
    def _is_valid(self, transaction: dict) -> bool:
        """Basic validation of OCR results."""
        # Must have at least date, amount, merchant
        if not transaction.get("date_raw"):
            return False
        if not transaction.get("amount_raw"):
            return False
        if not transaction.get("merchant_raw"):
            return False
        return True
    
    def _calculate_target_path(self, image_path: Path, transaction: dict) -> Path:
        """
        Calculate target path for renamed file (without renaming).
        Returns target path or original path if date parsing fails.
        """
        try:
            date_str = transaction.get("date_raw", "")
            merchant = transaction.get("merchant_raw", "Unknown")
            amount = transaction.get("amount_raw", "")
            
            # Parse date to ISO format
            iso_date = self._parse_date_to_iso(date_str)
            if not iso_date:
                logger.warning(f"Could not parse date: {date_str}, will keep original name")
                return image_path
            
            # Sanitize merchant name
            safe_merchant = self._sanitize_filename(merchant)
            
            # Generate new filename
            new_name = f"{iso_date}_{safe_merchant}_{amount}{image_path.suffix}"
            new_path = image_path.parent / new_name
            
            # Handle duplicates by adding counter
            counter = 1
            original_new_path = new_path
            while new_path.exists():
                stem = original_new_path.stem
                new_path = image_path.parent / f"{stem}_{counter}{image_path.suffix}"
                counter += 1
            
            return new_path
            
        except Exception as e:
            logger.error(f"Failed to calculate target path: {e}")
            return image_path
    
    def _parse_date_to_iso(self, date_str: str) -> Optional[str]:
        """Convert OCR date (e.g., '13 May 2025') to ISO format (YYYY-MM-DD)."""
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        
        # Pattern: DD Mmm YYYY
        pattern = r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
        match = re.match(pattern, date_str, re.IGNORECASE)
        
        if match:
            day, month, year = match.groups()
            month_num = month_map.get(month.lower(), '00')
            day_num = day.zfill(2)
            return f"{year}-{month_num}-{day_num}"
        
        return None
    
    def _sanitize_filename(self, text: str, max_length: int = 30) -> str:
        """Convert text to safe filename."""
        # Remove unsafe characters including:
        # - Windows reserved: \ / : * ? " < > |
        # - Shell special: & ; $ ` ! ( ) [ ] { } | * ? < > # @
        # - OCR artifacts: = ~ ^ % +
        # - Quotes: ' " `
        text = re.sub(r'[\\/*?:"<>|()\[\]{}&;!$`~^%+=@#\'"]', '', text)
        text = re.sub(r'\s+', '-', text)
        text = re.sub(r'-+', '-', text)
        text = text.strip('-')
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length]
        
        return text


class FileSystemWatcher(QObject):
    """
    File system watcher using watchdog (5s polling).
    
    Emits signal when new screenshot detected.
    """
    
    file_detected = Signal(str)  # Emits file path
    
    def __init__(self, watch_path: str = "."):
        super().__init__()
        self.watch_path = Path(watch_path)
        self.observer = None
        self._running = False
    
    def start(self):
        """Start watching for new files."""
        if not HAS_WATCHDOG:
            logger.warning("Watchdog not available, file watching disabled")
            return False
        
        if self._running:
            return True
        
        self._running = True
        
        # Create event handler
        handler = ScreenshotHandler(self.file_detected)
        
        # Create observer (polling every 5 seconds)
        self.observer = Observer(timeout=5)
        self.observer.schedule(handler, str(self.watch_path), recursive=True)
        self.observer.start()
        
        logger.info(f"File watching started: {self.watch_path}")
        return True
    
    def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self._running = False
        logger.info("File watching stopped")


class ScreenshotHandler(FileSystemEventHandler if HAS_WATCHDOG else object):
    """Event handler for new screenshot files."""
    
    def __init__(self, signal):
        self.signal = signal
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        # Check if it"s a screenshot file
        path = Path(event.src_path)
        if path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            logger.debug(f"New file detected: {path.name}")
            self.signal.emit(str(path))


class Orchestrator(QObject):
    """
    Main orchestrator - coordinates file watching, processing, and GUI.
    
    This is the central coordinator that ties everything together.
    """
    
    # Signals for GUI communication
    transaction_ready = Signal(dict)  # New transaction processed
    backup_created = Signal(str)      # Backup path
    error_occurred = Signal(str)      # Error message
    
    def __init__(self, screenshots_dir: str = "screenshots"):
        super().__init__()
        
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(exist_ok=True)
        
        # Components
        self.backup_manager = BackupManager()
        self.pipeline = ProcessingPipeline()
        self.watcher = FileSystemWatcher(self.screenshots_dir)
        
        # Connect signals
        self.watcher.file_detected.connect(self._on_file_detected)
    
    def startup(self) -> Optional[Path]:
        """
        Application startup sequence.
        
        1. Create backup
        2. Start file watching
        
        Returns:
            Backup path or None
        """
        # Step 1: Backup
        backup_path = self.backup_manager.startup_backup()
        if backup_path:
            self.backup_created.emit(str(backup_path))
        
        # Step 2: Start watching
        self.watcher.start()
        
        return backup_path
    
    def shutdown(self):
        """Application shutdown - cleanup."""
        self.watcher.stop()
        logger.info("Orchestrator shutdown complete")
    
    def process_file(self, filepath: str) -> dict:
        """
        Manually process a file (for "Check New Screenshots" button).
        
        Returns:
            Pipeline result dict
        """
        return self.pipeline.process(filepath, self._on_transaction_ready)
    
    def _on_file_detected(self, filepath: str):
        """Handle new file detected by watcher."""
        logger.info(f"Auto-processing: {filepath}")
        result = self.pipeline.process(filepath, self._on_transaction_ready)
        
        if result["status"] != "success":
            self.error_occurred.emit(f"Failed to process {filepath}: {result.get("status")}")
    
    def _on_transaction_ready(self, transaction: dict):
        """Forward transaction to GUI."""
        self.transaction_ready.emit(transaction)


# Convenience function for simple usage
def create_orchestrator(screenshots_dir: str = "screenshots") -> Orchestrator:
    """Factory function to create and configure orchestrator."""
    return Orchestrator(screenshots_dir)
