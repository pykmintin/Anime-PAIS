# PAIS - Personal Anime Intelligence System
## Design Specification Document v1.0
### Date: 2026-02-03
### Status: Architecture Complete, Implementation Pending

---

## 1. EXECUTIVE SUMMARY

**PAIS** is a local, self-hosted anime discovery and tracking system designed to replace AniList with AI-assisted recommendations. It operates entirely on the user's Windows machine using Python 3.14 and PySide6.

**Core Philosophy:**
- **Guided Discovery**: The system suggests, the user judges, but the system never assumes without asking
- **Auditability**: Every decision is logged and reversible
- **Echo Chamber Resistance**: Intentional injection of diverse recommendations
- **Offline-First**: Primary database is the 40,515-entry anime-offline-database (GitHub/manami-project)

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Technology Stack
- **Language**: Python 3.14
- **GUI Framework**: PySide6 (Qt6) - Professional native widgets
- **Storage**: Hierarchical JSON with atomic write patterns
- **Reference Data**: anime-offline-database-minified.json (58MB, 40,515 entries)

### 2.2 Directory Structure
```
PAIS_ROOT/
├── pais_core/
│   ├── __init__.py
│   ├── models.py              # Data classes (Anime, UserRating, TasteProfile)
│   ├── database.py            # JSON persistence layer with atomic writes
│   ├── recommender.py         # Scoring algorithms
│   ├── offline_db_loader.py   # Streaming loader for 58MB reference
│   └── audit_logger.py        # Decision logging
├── pais_gui/
│   ├── __init__.py
│   ├── main_window.py         # Primary PySide6 window
│   ├── recommendation_card.py # Anime display widget
│   ├── planning_view.py       # Planning list management
│   └── stats_view.py          # Taste profile visualization
├── user_data/
│   ├── taste_profile.json
│   ├── watch_history.json
│   ├── planning.json
│   ├── audit_log.jsonl        # Line-delimited for append-only
│   └── recommendations_cache.json
├── offline_db/
│   └── anime_offline_database.json  # Read-only reference
├── exports/
│   └── for_enrichment.csv     # For worker agent integration
└── backups/
    └── [timestamped backups]
```

### 2.3 Data Storage Strategy
**JSON-First**: All user data stored as JSON with atomic write pattern:
1. Write to `filename.json.tmp`
2. Verify JSON integrity
3. Rename to `filename.json`
4. Prevents corruption on crash

**No SQLite**: Explicitly rejected due to schema migration complexity and "heavy" feel.

---

## 3. DATA MODELS

### 3.1 Taste Profile Schema
```json
{
  "version": "string (ISO date)",
  "last_updated": "string (ISO timestamp)",
  "dimensions": {
    "narrative_structure": {
      "unpredictable": 0.0-1.0,
      "linear": 0.0-1.0,
      "episodic": 0.0-1.0
    },
    "emotional_tone": {
      "melancholic": 0.0-1.0,
      "comedic": 0.0-1.0,
      "tense": 0.0-1.0,
      "wholesome": 0.0-1.0
    },
    "visual_style": {
      "minimalist": 0.0-1.0,
      "detailed": 0.0-1.0,
      "experimental": 0.0-1.0
    },
    "pacing": {
      "slow_burn": 0.0-1.0,
      "fast_paced": 0.0-1.0
    }
  },
  "tag_weights": {
    "psychological": 0.0-1.0,
    "mecha": 0.0-1.0,
    "slice_of_life": 0.0-1.0
  },
  "studio_affinity": {
    "madhouse": 0.0-1.0,
    "kyoto_animation": 0.0-1.0
  },
  "confidence_scores": {
    "narrative_structure": 0.0-1.0,
    "tag_weights": 0.0-1.0,
    "studio_affinity": 0.0-1.0
  },
  "anti_patterns": {
    "tags_to_avoid": ["ecchi", "harem"],
    "studios_to_avoid": ["toei_animation"],
    "confidence": 0.0-1.0
  }
}
```

### 3.2 Watch History Entry
```json
{
  "entry_id": "uuid",
  "anime_title": "string",
  "normalized_title": "string (lowercase, no punctuation)",
  "user_rating": 1-5,
  "rating_date": "ISO timestamp",
  "date_first_watched": "ISO timestamp or 'unknown_prior'",
  "source": "recommendation|manual_search|planning_queue",
  "recommendation_id": "uuid or null",
  "tags_at_time": ["array", "of", "strings"],
  "offline_db_id": "string (optional)",
  "mal_url": "string (optional)",
  "anilist_url": "string (optional)",
  "would_recommend_to_others": true|false,
  "notes": "string (optional)"
}
```

### 3.3 Planning Queue Entry
```json
{
  "entry_id": "uuid",
  "anime_title": "string",
  "normalized_title": "string",
  "date_added": "ISO timestamp",
  "source": "recommendation|manual_add|imported",
  "priority_score": 0.0-1.0,
  "match_reasoning": "string (why recommended)",
  "enriched": {
    "mal_url": "string",
    "anilist_url": "string",
    "mal_score": 0.0-10.0,
    "anilist_score": 0.0-10.0,
    "enrichment_date": "ISO timestamp"
  },
  "status": "pending|enriched|deferred"
}
```

### 3.4 Audit Log Entry (Line-Delimited JSON)
```json
{
  "timestamp": "ISO timestamp",
  "session_id": "uuid",
  "action": "rated|skipped|added_to_planning|deferred|enriched",
  "anime_title": "string",
  "previous_state": {},
  "new_state": {},
  "reason": "user_explicit_choice|system_recommendation",
  "ui_context": "recommendation_view|planning_view|search"
}
```

---

## 4. RECOMMENDATION ENGINE SPECIFICATIONS

### 4.1 Scoring Algorithm (Multi-Strategy)

**Strategy 1: Taste Vector Similarity** (60% weight)
- Convert anime tags to vector space (one-hot encoding)
- Cosine similarity against taste profile dimensions
- **Decay function**: Ratings older than 6 months have 50% weight in taste profile calculation
- Formula: `score = Σ(dimension_match * dimension_weight * confidence)`

**Strategy 2: Graph Traversal** (25% weight)
- For each anime in watch_history with rating >=4, check `relatedAnime` in offline DB
- Boost candidates that appear in relatedAnime of highly-rated watches
- **Prerequisite Validation**: If candidate is sequel/related, check if prequel is in watch_history
  - If prequel NOT watched: Reduce score by 80% (discourage starting mid-series)
  - If prequel watched AND rated highly: Boost score by 20%

**Strategy 3: Serendipity Injection** (15% weight)
- Random selection from offline DB meeting criteria:
  - Status: FINISHED
  - Score > 7.0 (arithmeticMean)
  - Similarity to taste profile < 0.6 (not too similar)
  - Tags include at least one "cold" tag (never rated by user)
- Ensures system doesn't trap user in filter bubble

### 4.2 Rating System: 5-Star Scale
- **1 Star**: Disliked (actively harmful to taste profile, strong negative signal)
- **2 Stars**: Below Average (weak negative signal)
- **3 Stars**: Average/Decent (neutral, confirms tag interest)
- **4 Stars**: Good (strong positive signal)
- **5 Stars**: Masterpiece (maximum signal, defines taste profile)

**Update Logic (Bayesian)**:
```python
for tag in anime_tags:
    current = taste_profile.tag_weights[tag]
    confidence = taste_profile.confidence_scores[tag]
    rating_norm = user_rating / 5.0  # 0.2, 0.4, 0.6, 0.8, 1.0
    
    # Weighted update
    new_weight = (current * confidence + rating_norm * (1 - confidence))
    new_confidence = min(confidence + 0.05, 1.0)
    
    taste_profile.tag_weights[tag] = new_weight
    taste_profile.confidence_scores[tag] = new_confidence
```

### 4.3 "Have You Seen This?" Detection Logic

**Rule 1: Never Assume (Except Prequels)**
- System must ASK user: "Have you watched this before?"
- Context: When user rates 4-5 stars on a recommendation
- User options: 
  - "Yes, watched it [timeframe]" → Add to history with original watch date
  - "No, just watched it now" → Add to history with today's date
  - "No, but I started it before" → Prompt for episode count, partial watch handling

**Rule 2: Prequel Assumption Exception**
- If user marks "Attack on Titan Season 4" as watched
- System can auto-mark Seasons 1-3 as watched IF:
  - User confirms: "Did you watch the previous seasons?"
  - User can modify individual season ratings if they differ

**Rule 3: Specials/OVAs/OVNs**
- Never assume for specials, OVAs, ONAs, movies
- Always ask: "Did you watch the special episode 'X'?"
- These often have different titles and are easily missed

### 4.4 Echo Chamber Mitigation

**The Problem**: User rates 10 psychological thrillers 5 stars → System only recommends psychological thrillers → User misses comedy masterpiece.

**Mitigation Strategies**:
1. **Cold Tag Injection**: Every 5th recommendation must include at least one tag the user has never rated
2. **Cross-Pollination**: Recommend anime combining loved tag + unexplored tag
   - Example: User loves "psychological" + cold tag "sports" → Recommend "One Outs" (psychological sports)
3. **Temporal Decay**: Tag weights decay 10% per month of non-engagement
4. **Explicit Re-Testing**: If tag weight drops below 0.3 due to decay, inject one "test" recommendation before excluding

---

## 5. GUI SPECIFICATIONS (PySide6)

### 5.1 Main Window Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ PAIS - Personal Anime Intelligence System         [Settings] [Exit]  │
├──────────────────┬───────────────────────────────────────────────────┤
│                  │                                                   │
│   STATISTICS     │   RECOMMENDATION CARD                             │
│   ─────────────  │   ─────────────────────                           │
│                  │                                                   │
│   Planning: 423  │   [Poster Image - Left]                           │
│   Completed: 127 │                                                   │
│   This Session:  │   Title: "The Tatami Galaxy"                      │
│   12 rated       │   Year: 2010 | Episodes: 11 | Type: TV            │
│                  │   Status: FINISHED                                │
│   ─────────────  │                                                   │
│                  │   Tags: psychological, comedy, time-loop,         │
│   CURRENT TASTE  │         coming-of-age, seinen                     │
│   ─────────────  │                                                   │
│   Top: Psych     │   Match: 89% | Source: Taste Vector               │
│   Avoid: Mecha   │                                                   │
│   Exploring:     │   Reasoning:                                      │
│   Sports (test)  │   • High match to your preferred tags             │
│                  │   • Similar to "Welcome to the NHK" (rated 5/5)   │
│   ─────────────  │   • From studio Madhouse (you rated 4+ avg)       │
│                  │                                                   │
│   [View          │                                                   │
│   Planning]      │   [5-Star Rating]                                 │
│   [Export for    │   ⭐ ⭐ ⭐ ⭐ ⭐                                  │
│   Enrichment]    │   [Love It] [Good] [Mid] [Skip] [Already Seen]    │
│                  │                                                   │
└──────────────────┴───────────────────────────────────────────────────┘
```

### 5.2 Rating Interface
- **5-Star Display**: Horizontal row of 5 star icons
- **Hover**: Preview highlight (1-5)
- **Click**: Set rating
- **Post-Click Popup**: "Have you seen this before?"
  - Buttons: `[Yes, watched prior]` `[No, new watch]` `[Partially watched]`

### 5.3 Keyboard Shortcuts
- `1-5`: Set rating (1-5 stars)
- `Space`: Show full synopsis
- `N`: Next recommendation (defer)
- `S`: Search manual entry
- `R`: Random surprise (force serendipity)
- `P`: Add to Planning (without rating)
- `Ctrl+Z`: Undo last rating (reverts taste profile)

### 5.4 Views
1. **Recommendation View** (Default): Single anime card with rating
2. **Planning View**: Sortable/filterable list of planning queue
   - Sort by: Taste match %, Year, Score, Date Added
   - Filter by: Tags, Type, Year range, Enriched status
   - Multi-select for batch operations
3. **Stats View**: Taste profile visualization (radar chart of dimensions)
4. **Audit View**: Timeline of all decisions with rollback option

---

## 6. OFFLINE DATABASE INTEGRATION

### 6.1 Reference Data Format
**Source**: manami-project/anime-offline-database
**File**: anime-offline-database-minified.json
**Size**: ~58MB
**Entries**: 40,515 anime

**Key Fields Used**:
- `title`: Primary title
- `synonyms`: Array of alternative titles (crucial for matching)
- `type`: TV, MOVIE, OVA, ONA, SPECIAL
- `episodes`: Integer
- `status`: FINISHED, ONGOING, UPCOMING
- `animeSeason`: {year, season}
- `score`: {arithmeticMean, median} (aggregate across providers)
- `sources`: Array of URLs (MAL, AniList, etc.)
- `tags`: Array of genre descriptors
- `relatedAnime`: Array of related entry URLs
- `studios`: Array of studio names

### 6.2 Loading Strategy
**Streaming, Not Full Load**:
- Do NOT load full 58MB into RAM as Python objects
- Use `ijson` library for streaming JSON parsing
- Build lookup indexes incrementally:
  - `title_index`: {normalized_title: entry}
  - `synonym_index`: {normalized_synonym: entry}
  - `tag_index`: {tag: [entries]} (for recommendation generation)

**Memory Target**: <200MB RAM usage during operation

### 6.3 Matching Algorithm
**Normalization Pipeline**:
1. Lowercase
2. Remove punctuation: `[^\w\s]`
3. Normalize whitespace
4. Remove common articles: "the", "a", "an" (from start only)

**Search Priority**:
1. Exact normalized title match
2. Exact normalized synonym match
3. Substring match (title contains query or vice versa)
4. Word-set match (80% of words overlap)

---

### 7. REVISED ENRICHMENT STRATEGY (Hybrid Architecture)

**Status:** ARCHITECTURE PIVOT - Post OfflineDB Integration

**Old Approach (Deprecated):** Worker agent discovers URLs via web search (slow, error-prone, cascade shift risk)
**New Approach:** Offline DB provides pre-mapped URLs → Local validation → Worker only for edge cases

#### 7.1 Three-Phase Pipeline

**Phase 1: Local URL Matching (Python Script)**
- Input: `animelist.csv` + `anime-offline-database.json` (58MB)
- Process: Fuzzy match titles against offline DB (title + synonyms fields)
- Output: 
  - `animelist_matched.csv` (380/411 entries with URLs pre-populated)
  - `exceptions.csv` (31 entries not found in offline DB)
- Tool: Local Python (no browser, fast file I/O)

**Phase 2: Local Validation (Playwright Script)**
- Input: `animelist_matched.csv`
- Process: 
  - Playwright navigates to each MAL/AniList URL
  - Scrapes live scores from page
  - Validates page title matches CSV title (fuzzy)
  - Flags mismatches/dead links for exceptions list
- Output: `animelist_validated.csv` with live scores
- Features: Progress bar, resume capability, incremental saves
- Rate: ~2-3 seconds/entry (~20 minutes for 400 entries)

**Phase 3: Edge Case Resolution (Kimi Worker - Minimal)**
- Input: `exceptions.csv` (unmatched + dead links only)
- Scope: 5-10% of list (20-40 entries max)
- Task: Web search for URLs not in offline DB (unreleased 2025+ anime)
- Output: `exceptions_resolved.csv`
- Merge: Combine with validated CSV → Final enriched dataset

#### 7.2 Rationale for Hybrid Approach

**Why Local for Bulk:**
- **Speed:** 20 minutes vs 40+ hours via Kimi
- **Reliability:** No browser timeouts/context limits
- **Data Integrity:** Offline DB URLs are community-validated (no cascade shift)
- **Cost:** Zero API quotas, runs overnight unattended

**Why Kimi for Edge Cases:**
- **Adaptability:** Handles novel/unreleased anime not in offline DB
- **Heuristic reasoning:** Searches for similar titles when exact match fails
- **Cognitive validation:** Can judge "close enough" title mismatches

#### 7.3 Technical Specifications

**Local Matching Script Requirements:**
- Load offline DB via streaming (ijson) - do not load 58MB into RAM
- Normalize titles: lowercase, remove punctuation, strip articles
- Match priority: exact → synonym → normalized → substring
- Export unmatched list with similarity scores for manual review

**Playwright Validation Script Requirements:**
- Persistent browser context (cookies/cache retained)
- Rate limiting: 1-second delay between requests (respect servers)
- Validation rules:
  - Page title must contain CSV title (± punctuation/subtitles)
  - Score must be numeric 1.0-10.0
  - Dead links (404) flagged but not deleted
- Atomic CSV writes: save every 10 entries (resume capability)

---

## 8. AUDIT & TRANSPARENCY

### 8.1 Decision Logging
Every user action logged to `audit_log.jsonl` (append-only):
- Timestamp
- Action type
- Anime identifier
- State changes (before/after)
- UI context

### 8.2 "Why?" Feature
Every recommendation must explain:
- Similarity percentage breakdown
- Which taste dimensions matched
- Related anime connections
- Randomness factor (calculated vs serendipity)

### 8.3 Bias Detection Reports
Monthly generated report:
- Tag concentration analysis ("80% of recommendations are psychological")
- Decay alerts ("You haven't rated comedy in 3 months")
- Re-testing suggestions ("Consider testing 'sports' again?")

### 8.4 Rollback Capability
- Taste profile versioned with timestamps
- Can revert to any previous state
- Undo last N actions (with Ctrl+Z in GUI)

---

## 9. CURRENT STATUS & NEXT STEPS

### 9.1 Completed Design Decisions
- [x] 5-star rating system (not 3-button)
- [x] PySide6 GUI framework
- [x] JSON storage (not SQLite)
- [x] Taste profile learned through interaction (not CSV mining)
- [x] "Have you seen this?" mandatory asking (except prequels)
- [x] Offline database integration (40k entries)
- [x] Worker agent enrichment pipeline
- [x] Echo chamber mitigation strategies

### 9.2 Pending Decisions (Backlog)
- [ ] Serendipity percentage (currently 15%, user may adjust)
- [ ] GUI aesthetic theme (dark/light, card vs table layout)
- [ ] Auto-backup frequency (daily/weekly/manual)
- [ ] "Retirement" policy (how many skips before permanent removal)

### 9.3 Implementation Phases

**Phase 0: Foundation** (Week 1)
- [ ] Set up project structure
- [ ] Implement atomic JSON persistence layer
- [ ] Create offline DB streaming loader
- [ ] Import existing CSV data to JSON format

**Phase 1: Core Loop** (Week 2)
- [ ] Build PySide6 main window
- [ ] Implement recommendation card widget
- [ ] Create 5-star rating component
- [ ] Build basic taste profile update logic
- [ ] Implement "Have you seen this?" dialog

**Phase 2: Intelligence** (Week 3)
- [ ] Implement graph traversal recommendations
- [ ] Add serendipity injection
- [ ] Create planning view with sorting/filtering
- [ ] Build stats view (taste visualization)

**Phase 3: Integration** (Week 4)
- [ ] Export for enrichment functionality
- [ ] Import enriched data
- [ ] Audit log viewer
- [ ] Keyboard shortcuts

**Phase 4: Polish** (Week 5+)
- [ ] Performance optimization
- [ ] Bias detection reports
- [ ] Backup/sync features
- [ ] AniList sync (optional, post-MVP)

### 9.4 Immediate Next Action
**Create project skeleton**:
1. Directory structure as specified
2. `requirements.txt` with PySide6, ijson, rapidfuzz
3. Basic `models.py` with dataclasses for core entities
4. `database.py` with atomic JSON write functions
5. Empty GUI modules ready for implementation

---

## 10. USER PREFERENCES SUMMARY

**From Conversation History**:
- User wants 5-star rating (not 3-button)
- User will manually indicate if already seen (system must ask)
- PySide6 GUI (professional, native feel)
- JSON storage only (no SQLite)
- Local system, self-contained
- Taste learned through interaction/interview (not CSV analysis)
- Planning list is the pool - keep everything there, filter/sort as needed
- User follows seasonal anime on streaming platforms, so system focuses on completed back-catalog discovery
- Training data (pre-April 2024) is primary reference, newer anime flagged
- Echo chamber resistance desired (random recommendations, diverse suggestions)
- Audit trails required for all decisions
- Worker agent integration for URL/score enrichment (CSV export/import)

---
### APPENDIX A: Worker Agent Lessons Learned

**Source:** Audit of `animelist_enriched4.csv` (Worker Agent v1.0)

**A.1 Critical Data Issues Detected**
- **Row 425 Corruption:** `given The Movie: Hiiragi Mix` contains concatenated data from `Kingdom Season 4` (two rows merged). Requires manual split before processing.
- **Index Misalignment:** Worker confused pandas indices with CSV row numbers (off-by-2 error). Future workers must verify `df.loc[idx, 'Title']` before writing.

**A.2 Failure Modes Observed**
1. **Browser Fragility:** Persistent connection issues after ~9 entries. Solution: Implement search-based fallback (web_search) when web_open_url fails.
2. **AniList Redirects:** Some AniList URLs redirected to different anime pages. Solution: Validate final URL matches requested anime ID.
3. **Zero-Byte Writes:** Risk of empty .tmp files on crash. Solution: Use Corelink `safe_write()` pattern (verify size > 0 before rename).

**A.3 Success Patterns**
- **Tier System Effective:** Worker correctly tracked 9/15 consecutive validations.
- **Adaptive Fallback:** When browser died, search-based extraction maintained 100% accuracy.
- **Audit Logging:** Timestamped logs enabled post-hoc debugging of cascade shifts.

**A.4 Deprecated Practices (Do Not Repeat)**
- Do NOT use Kimi for bulk URL discovery (too slow/expensive)
- Do NOT process entries 1-by-1 via context window (use local scripts)
- Do NOT skip title validation (prevents cascade shift errors)

---

### APPENDIX B: CSV Data Status (animelist_enriched4.csv)

**Current State:**
- Total entries: 411
- Fully enriched (both URLs + scores): 31 (7.5%)
- MAL_URL only: 66 (16.0%)
- AniList_URL only: ~0%
- FAILED_LOOKUP: ~294 (71.5%)
- UNRELEASED: 29 (correctly marked)

**Priority Queue for Next Enrichment:**
1. **High:** Entries 81-88 (have MAL_URL, need AniList_URL - easy wins)
2. **High:** Entries 98+ (clean data, browser was working here)
3. **Skip:** Row 425 (corrupted - fix manually first)
4. **Skip:** UNRELEASED entries (verify status only)

**Target:** 380 entries can be auto-matched from offline DB. Only ~31 need manual/Kimi intervention.

---

### APPENDIX C: Corelink Integration Checklist

**From Technical Integration Memo - Implementation Required:**

- [ ] Copy `safe_write()` from CoreCompile.py → `pais/database.py` (atomic writes + archival)
- [ ] Copy `log_event()` from CoreCompile.py → `pais/audit.py` (append-only JSONL)
- [ ] Adapt `error_dbox()` from Corelink.py → PySide6 error dialogs (copy-to-clipboard feature)
- [ ] Adapt `verify_dbox()` from Corelink.py → PySide6 confirmation dialogs (color-coded actions)
- [ ] Create `user_data/Archive/` structure (taste/, history/, planning/, Audit/)
- [ ] Implement zero-byte detection in all file writes
- [ ] Add automatic backup rotation (keep last 30 versions)

---

**Document End**
**Prepared for**: Next agent implementation
**Context Status**: Zero-context readable