"""
DATA UTILITIES MODULE
Atomic file operations and content hashing for NDIS Expense Assistant v2.0

Classes:
    AtomicCSV: Crash-atomic CSV read/write/append operations
    ContentHasher: MD5 hashing with chunked reading for duplicate detection

Usage:
    from data_utils import AtomicCSV, ContentHasher
    
    # Atomic CSV operations
    csv_handler = AtomicCSV("pending.csv", ["col1", "col2"])
    csv_handler.append_row({"col1": "value1", "col2": "value2"})
    
    # File hashing
    hasher = ContentHasher()
    file_hash = hasher.calculate_hash("screenshot.jpg")

Atomic Write Protocol:
    1. Backup existing file (.bak)
    2. Write to temp file (.tmp) with flush + fsync
    3. Atomic rename (.tmp → target)
    4. Remove backup on success
    5. On failure: restore from backup
    6. Always cleanup temp files

Crash Recovery:
    - .tmp exists → Remove (incomplete write)
    - .bak without main → Restore backup
    - .bak with main → Remove .bak (success case)

Author: NDIS Assistant v2.0
Date: 2026-02-05
Version: 2.0.0
"""

import os
import csv
import json
import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from logger_config import get_logger

logger = get_logger(__name__)


class AtomicCSV:
    """
    Crash-atomic CSV file operations.
    
    Uses write-to-temp-then-rename pattern with backup recovery
    to prevent data corruption during crashes, power loss, or disk errors.
    
    The atomic write protocol ensures data integrity:
        1. Create backup of existing file (.bak)
        2. Write new data to temp file (.tmp) with fsync
        3. Atomic rename temp file to target
        4. Remove backup on success
        5. On failure: restore from backup
    
    Attributes:
        filepath: Path to CSV file
        fieldnames: List of column names
        backup_path: Path to backup file (.bak)
        temp_path: Path to temp file (.tmp)
    
    Example:
        >>> csv_handler = AtomicCSV("pending.csv", ["date", "amount", "merchant"])
        >>> csv_handler.append_row({"date": "25092025", "amount": "-$28.70", "merchant": "Bakers Delight"})
    """
    
    def __init__(self, filepath: Union[str, Path], fieldnames: List[str]):
        """
        Initialize AtomicCSV handler.
        
        Args:
            filepath: Path to CSV file
            fieldnames: List of column names
        
        Raises:
            ValueError: If fieldnames is empty
        """
        if not fieldnames:
            raise ValueError("fieldnames cannot be empty")
        
        self.filepath = Path(filepath)
        self.fieldnames = fieldnames
        self.backup_path = self.filepath.with_suffix('.csv.bak')
        self.temp_path = self.filepath.with_suffix('.csv.tmp')
        
        # Ensure parent directory exists
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"AtomicCSV initialized for {self.filepath}")
    
    def read_all(self) -> List[Dict[str, str]]:
        """
        Read all rows from CSV with crash recovery.
        
        First checks for crash recovery indicators (.tmp or .bak files)
        and restores data if needed before reading.
        
        Returns:
            List of dictionaries (one per row), empty list if file doesn't exist
        
        Raises:
            IOError: If file cannot be read after recovery attempts
        
        Example:
            >>> rows = csv_handler.read_all()
            >>> for row in rows:
            ...     print(row['merchant'])
        """
        # Check for and perform crash recovery if needed
        self.check_and_recover()
        
        # If file doesn't exist, return empty list
        if not self.filepath.exists():
            logger.debug(f"File not found, returning empty list: {self.filepath}")
            return []
        
        rows = []
        try:
            with open(self.filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, fieldnames=self.fieldnames)
                # Skip header row if it matches fieldnames
                first_row = next(reader, None)
                if first_row:
                    # Check if this is actually data or a header
                    if set(first_row.keys()) == set(self.fieldnames):
                        # This might be a header row, check if values match keys
                        is_header = all(k == v for k, v in first_row.items())
                        if not is_header:
                            rows.append(first_row)
                    else:
                        rows.append(first_row)
                    
                    # Read remaining rows
                    for row in reader:
                        rows.append(row)
            
            logger.debug(f"Read {len(rows)} rows from {self.filepath}")
            return rows
            
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {self.filepath}: {e}")
            raise IOError(f"Cannot read {self.filepath}: encoding error") from e
        except Exception as e:
            logger.error(f"Error reading {self.filepath}: {e}")
            raise IOError(f"Cannot read {self.filepath}: {e}") from e
    
    def write_all(self, rows: List[Dict[str, str]]) -> None:
        """
        Write all rows to CSV atomically.
        
        Uses atomic write protocol to prevent data corruption:
            1. Backup existing file
            2. Write to temp file with fsync
            3. Atomic rename
            4. Remove backup on success
        
        Args:
            rows: List of dictionaries to write (each dict is a row)
        
        Raises:
            IOError: If write fails and cannot restore backup
            ValueError: If a row is missing required fields
        
        Example:
            >>> rows = [{"date": "25092025", "amount": "-$28.70", "merchant": "Bakers Delight"}]
            >>> csv_handler.write_all(rows)
        """
        # Validate all rows have required fields
        for i, row in enumerate(rows):
            missing_fields = set(self.fieldnames) - set(row.keys())
            if missing_fields:
                raise ValueError(f"Row {i} missing fields: {missing_fields}")
        
        # Step 1: Create backup of existing file
        backup_created = False
        if self.filepath.exists():
            try:
                shutil.copy2(self.filepath, self.backup_path)
                backup_created = True
                logger.debug(f"Created backup: {self.backup_path}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                raise IOError(f"Cannot create backup: {e}") from e
        
        # Step 2: Write to temp file
        try:
            with open(self.temp_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
                writer.writerows(rows)
                
                # Flush Python buffer
                f.flush()
                
                # Force OS to write to disk (fsync)
                os.fsync(f.fileno())
            
            # Step 3: Verify not zero-byte
            if self.temp_path.stat().st_size == 0:
                raise IOError("Zero-byte write detected")
            
            # Step 4: Atomic rename (POSIX: atomic, Windows: nearly atomic)
            os.replace(self.temp_path, self.filepath)
            
            # Step 5: Remove backup on success
            if backup_created and self.backup_path.exists():
                self.backup_path.unlink()
                logger.debug(f"Removed backup after successful write")
            
            logger.info(f"Wrote {len(rows)} rows to {self.filepath}")
            
        except Exception as e:
            logger.error(f"Write failed: {e}")
            
            # Cleanup temp file
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            
            # Step 6: Restore from backup on failure
            if backup_created and self.backup_path.exists():
                try:
                    shutil.copy2(self.backup_path, self.filepath)
                    logger.info(f"Restored {self.filepath} from backup")
                except Exception as restore_error:
                    logger.critical(f"Failed to restore backup: {restore_error}")
                    raise IOError(f"Write failed AND backup restore failed: {e}") from restore_error
            
            raise IOError(f"Failed to write {self.filepath}: {e}") from e
        
        finally:
            # Always cleanup temp file
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
    
    def append_row(self, row: Dict[str, str]) -> None:
        """
        Append a single row to CSV atomically.
        
        Reads all existing rows, appends the new row, and writes atomically.
        This ensures data integrity but is not optimal for very large files.
        
        Args:
            row: Dictionary to append (must have all fieldnames keys)
        
        Raises:
            ValueError: If row is missing required fields
            IOError: If write fails
        
        Example:
            >>> csv_handler.append_row({"date": "25092025", "amount": "-$28.70", "merchant": "Bakers Delight"})
        """
        # Validate row has all required fields
        missing_fields = set(self.fieldnames) - set(row.keys())
        if missing_fields:
            raise ValueError(f"Row missing fields: {missing_fields}")
        
        # Read existing rows
        rows = self.read_all()
        
        # Append new row
        rows.append(row)
        
        # Write all rows atomically
        self.write_all(rows)
        
        logger.debug(f"Appended row to {self.filepath}")
    
    def check_and_recover(self) -> bool:
        """
        Check for crash recovery indicators and restore data if needed.
        
        Detects and handles:
            - .tmp file exists → Remove (incomplete write)
            - .bak exists without main file → Restore backup
            - .bak exists with main file → Remove .bak (successful operation)
        
        Returns:
            True if recovery was performed
        
        Example:
            >>> if csv_handler.check_and_recover():
            ...     print("Recovery performed")
        """
        recovery_performed = False
        
        # Check for temp file (incomplete write)
        if self.temp_path.exists():
            try:
                self.temp_path.unlink()
                logger.warning(f"Removed incomplete temp file: {self.temp_path}")
                recovery_performed = True
            except Exception as e:
                logger.error(f"Failed to remove temp file: {e}")
        
        # Check for backup without main file (needs restore)
        if self.backup_path.exists() and not self.filepath.exists():
            try:
                shutil.copy2(self.backup_path, self.filepath)
                self.backup_path.unlink()
                logger.warning(f"Restored {self.filepath} from backup")
                recovery_performed = True
            except Exception as e:
                logger.error(f"Failed to restore from backup: {e}")
        
        # Check for backup with main file (successful operation, cleanup)
        elif self.backup_path.exists() and self.filepath.exists():
            try:
                self.backup_path.unlink()
                logger.debug(f"Cleaned up stale backup file: {self.backup_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup backup file: {e}")
        
        return recovery_performed


class ContentHasher:
    """
    Content-based duplicate detection using MD5 hashing.
    
    Uses chunked reading (4KB default) to handle large files efficiently
    without loading entire file into memory.
    
    Attributes:
        chunk_size: Size of chunks to read in bytes (default 4096)
    
    Example:
        >>> hasher = ContentHasher()
        >>> file_hash = hasher.calculate_hash("screenshot.jpg")
        >>> print(file_hash)  # "d41d8cd98f00b204e9800998ecf8427e"
    """
    
    def __init__(self, chunk_size: int = 4096):
        """
        Initialize ContentHasher.
        
        Args:
            chunk_size: Chunk size in bytes for reading (default 4096)
        
        Raises:
            ValueError: If chunk_size is not positive
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        
        self.chunk_size = chunk_size
        logger.debug(f"ContentHasher initialized with chunk_size={chunk_size}")
    
    def calculate_hash(self, filepath: Union[str, Path]) -> str:
        """
        Calculate MD5 hash of file contents.
        
        Reads file in chunks to handle large files efficiently.
        Returns hexadecimal MD5 hash string.
        
        Args:
            filepath: Path to file
        
        Returns:
            Hexadecimal MD5 hash string (32 characters)
        
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        
        Example:
            >>> hasher = ContentHasher()
            >>> hash1 = hasher.calculate_hash("file1.jpg")
            >>> hash2 = hasher.calculate_hash("file2.jpg")
            >>> if hash1 == hash2:
            ...     print("Files are identical")
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if not filepath.is_file():
            raise ValueError(f"Path is not a file: {filepath}")
        
        hasher = hashlib.md5()
        
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            
            hash_result = hasher.hexdigest()
            logger.debug(f"Calculated hash for {filepath}: {hash_result[:16]}...")
            return hash_result
            
        except Exception as e:
            logger.error(f"Error hashing {filepath}: {e}")
            raise IOError(f"Cannot hash {filepath}: {e}") from e
    
    def calculate_hash_bytes(self, data: bytes) -> str:
        """
        Calculate MD5 hash of byte data.
        
        Useful for hashing in-memory data without writing to file.
        
        Args:
            data: Byte data to hash
        
        Returns:
            Hexadecimal MD5 hash string (32 characters)
        
        Raises:
            TypeError: If data is not bytes
        
        Example:
            >>> hasher = ContentHasher()
            >>> data = b"Hello, World!"
            >>> hash_result = hasher.calculate_hash_bytes(data)
        """
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        
        hasher = hashlib.md5()
        hasher.update(data)
        return hasher.hexdigest()


# Module self-test
if __name__ == "__main__":
    import tempfile
    import os
    
    logger.info("=" * 50)
    logger.info("data_utils.py - Self Test")
    logger.info("=" * 50)
    
    # Test ContentHasher
    logger.info("Testing ContentHasher...")
    hasher = ContentHasher()
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test content for hashing")
        temp_file = f.name
    
    try:
        hash1 = hasher.calculate_hash(temp_file)
        hash2 = hasher.calculate_hash(temp_file)
        assert hash1 == hash2, "Hash consistency failed"
        logger.info(f"✓ ContentHasher: {hash1}")
        
        # Test bytes hashing
        data = b"Test content for hashing"
        hash_bytes = hasher.calculate_hash_bytes(data)
        logger.info(f"✓ ContentHasher (bytes): {hash_bytes}")
    finally:
        os.unlink(temp_file)
    
    # Test AtomicCSV
    logger.info("Testing AtomicCSV...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "test.csv"
        fieldnames = ["date", "amount", "merchant"]
        
        csv_handler = AtomicCSV(csv_path, fieldnames)
        
        # Test write and read
        rows = [
            {"date": "25092025", "amount": "-$28.70", "merchant": "Bakers Delight"},
            {"date": "26092025", "amount": "-$15.00", "merchant": "Shell"}
        ]
        
        csv_handler.write_all(rows)
        read_rows = csv_handler.read_all()
        assert len(read_rows) == 2, "Read/write failed"
        logger.info(f"✓ AtomicCSV write/read: {len(read_rows)} rows")
        
        # Test append
        csv_handler.append_row({"date": "27092025", "amount": "-$42.50", "merchant": "Woolworths"})
        read_rows = csv_handler.read_all()
        assert len(read_rows) == 3, "Append failed"
        logger.info(f"✓ AtomicCSV append: {len(read_rows)} rows")
        
        # Test crash recovery (simulate .tmp file)
        csv_handler.temp_path.touch()
        assert csv_handler.check_and_recover(), "Recovery should detect .tmp"
        assert not csv_handler.temp_path.exists(), "Temp file should be removed"
        logger.info("✓ AtomicCSV crash recovery (.tmp)")
    
    logger.info("=" * 50)
    logger.info("All tests passed!")
    logger.info("=" * 50)
