**TECHNICAL INTEGRATION MEMO: Corelink → PAIS Asset Reuse**

**Date:** 2026-02-03  
**Purpose:** Reference document for implementation phase  
**Prerequisite:** Design Specification Document v1.0 (PAIS) + Corelink v6.3.15 codebase

---

## EXECUTIVE SUMMARY

The Corelink system (`CoreCompile.py`, `Corelink.py`, `Corelink_schema.json`) contains battle-tested implementations of safety-critical file operations. Do not reimplement these for PAIS. Extract and adapt the following specific functions:

---

## MANDATORY REUSE (Do Not Rewrite)

### 1. Atomic File Write with Archival
**Source:** `CoreCompile.py`  
**Function:** `safe_write(target_path, content, category)`  
**Purpose:** All JSON persistence in PAIS (taste_profile.json, watch_history.json, etc.)

**Integration Points:**
- Replace PAIS Design Spec Section 2.3 "Atomic Write Pattern" with this implementation
- Change `category` parameter to `data_type` ("taste", "history", "planning", "audit")
- Archive directory: `user_data/Archive/[data_type]/`
- Keeps timestamped backups automatically

**Critical Features Included:**
- Zero-byte write detection (corruption prevention)
- Automatic archival before overwrite
- Cleanup on failure (.tmp unlink)
- Integrated logging call

---

### 2. Append-Only Audit Logging
**Source:** `CoreCompile.py`  
**Function:** `log_event(action, context)`  
**Purpose:** PAIS audit trail (user ratings, skips, additions)

**Integration Points:**
- Use for PAIS `user_data/Archive/Audit/audit.jsonl`
- Called automatically by safe_write()
- Also call manually for GUI actions (button clicks, skips, etc.)
- JSONL format (one JSON object per line, append-only)

---

### 3. Error Dialog with Forensics
**Source:** `Corelink.py`  
**Function:** `error_dbox(title, error_msg)`  
**Purpose:** All PAIS GUI error reporting

**Integration Points:**
- Convert from Tkinter to PySide6 (QDialog, QTextEdit, QPushButton)
- Keep the **Copy to Clipboard** button (critical for debugging)
- Keep timestamp inclusion in copied text
- Use for: File write failures, JSON parse errors, offline DB load failures

---

### 4. Verification Dialog Pattern
**Source:** `Corelink.py`  
**Function:** `verify_dbox(title, msg, action_type)`  
**Purpose:** Destructive action confirmation in PAIS GUI

**Integration Points:**
- Batch operations (delete multiple planning items)
- Taste profile reset/rollback
- Import overwrite confirmation
- Keep color coding: Red for write operations, Green for read-only
- Keep explicit action button labels ("EXECUTE WRITE" vs "CONTINUE")

---

### 5. Directory Structure Convention
**Source:** `Corelink.py` (ROOT_DIR, BASE_DIR, ARCHIVE_DIR pattern)  
**Purpose:** PAIS file organization

**Adopt This Structure:**
```
user_data/
├── taste_profile.json          # Current
├── watch_history.json          # Current
├── planning.json               # Current
└── Archive/                    # Auto-created by safe_write
    ├── taste/                  # Timestamped taste_profile backups
    ├── history/                # Watch history snapshots
    ├── planning/               # Planning list backups
    └── Audit/                  # audit.jsonl location
```

---

## ADAPTATION NOTES

### Parameter Changes
| Corelink Original | PAIS Adaptation |
|-------------------|-----------------|
| `category="CoreLink"` | `data_type="taste"` |
| `archive_dir = Path("Archive")/category` | `archive_dir = USER_DATA/"Archive"/data_type` |
| `log_file = Path("Archive/Logs/queue_log.jsonl")` | `log_file = USER_DATA/"Archive"/"Audit"/"audit.jsonl"` |

### GUI Conversion (Tkinter → PySide6)
- `tk.Toplevel()` → `QDialog()`
- `tk.Text()` → `QTextEdit()` (setReadOnly(True))
- `tk.Button()` → `QPushButton()`
- `pyperclip.copy()` → `QApplication.clipboard().setText()`
- Modal behavior: `transient()`/`grab_set()`/`wait_window()` → `exec_()` (PySide6 modal)

---

## DO NOT REUSE (Out of Scope)

These Corelink features are **not needed** for PAIS:
- `action_queue` / `process_queue()` (PAIS is interactive, not batch)
- `self_update_from_clipboard()` (PAIS updates via Git/manual)
- `launch_vtt()` (voice transcription unrelated)
- `validate_payload()` (no JSON clipboard workflows in PAIS)
- Subprocess execution patterns (PAIS is monolithic)

---

## IMPLEMENTATION CHECKLIST

When implementing PAIS `database.py`:
- [ ] Copy `safe_write()` logic from CoreCompile.py
- [ ] Copy `log_event()` logic from CoreCompile.py  
- [ ] Create `user_data/Archive/` directory structure
- [ ] In GUI layer, adapt `error_dbox()` from Corelink.py to PySide6
- [ ] In GUI layer, adapt `verify_dbox()` from Corelink.py to PySide6
- [ ] Test zero-byte detection (write empty dict, verify it rejects)
- [ ] Test archival (modify file twice, verify two backups exist)

---

## RATIONALE

Why reuse these specific functions:
1. **Proven in production** - Corelink has executed these thousands of times without data loss
2. **Corner case coverage** - Zero-byte detection, permission errors, atomic rename failures already handled
3. **Audit compliance** - Every operation logged automatically
4. **User experience** - Error dialogs include copy-to-clipboard for easy bug reporting

**Time savings:** ~4-6 hours of debugging file corruption issues avoided by using these reference implementations.

---

**End of Memo**