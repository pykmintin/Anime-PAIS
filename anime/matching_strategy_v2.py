#!/usr/bin/env python3
"""
BULLETPROOFED Progressive Cascade Matching Strategy v2
Incorporates: Performance indexing, Data integrity checks, Debug visibility
"""

import json
import csv
import re
import time
import random
from collections import defaultdict

# ============================================
# CONFIGURATION
# ============================================
TEST_SIZE = 30  # Number of entries to test
CHUNKS_TO_LOAD = 3  # Start with 3 chunks (~12k entries)
CONFIDENCE_THRESHOLD = 0.7  # Flag matches below this for review

# ============================================
# NORMALIZATION FUNCTIONS (with safety checks)
# ============================================

def safe_normalize(title):
    """Base normalization with null safety"""
    if not title or not isinstance(title, str):
        return ""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def extract_tokens(title):
    """Split into word tokens, remove common words"""
    common_words = {'the', 'a', 'an', 'and', 'or', 'of', 'is', 'to', 'in', 'on', 'at', 'with', 'for'}
    normalized = safe_normalize(title)
    if not normalized:
        return []
    tokens = normalized.split()
    return [t for t in tokens if t not in common_words and len(t) > 1]

def get_anchors(title):
    """Get first and last meaningful word"""
    tokens = extract_tokens(title)
    if not tokens:
        return [], []
    if len(tokens) == 1:
        return tokens, []
    return [tokens[0]], [tokens[-1]]

def ngrams_safe(title, n=3):
    """Generate character n-grams with safety"""
    text = safe_normalize(title).replace(' ', '')
    if len(text) < n:
        return set()
    return set(text[i:i+n] for i in range(len(text)-n+1))

def calc_overlap(set1, set2):
    """Calculate overlap percentage with zero-division protection"""
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    if not union:
        return 0.0
    return len(intersection) / len(union)

def expand_title(title):
    """Generate variations with improved season detection"""
    if not title:
        return [""]
    
    variations = [title]
    
    # More comprehensive season patterns (case-insensitive)
    season_patterns = [
        (r'\s+season\s+\d+', ' season marker'),
        (r'\s+s\d+\b', ' s marker'),
        (r'\s+part\s+\d+', ' part marker'),
        (r'\s+\d+nd\s+season', ' nd season'),
        (r'\s+\d+rd\s+season', ' rd season'),
        (r'\s+\d+th\s+season', ' th season'),
        (r':\s*the\s+final', ' final season'),
        (r'\s+final\s+season', ' final season'),
        (r':\s*ultra\s+romantic', ' subtitle'),
        (r':\s*beyond\s+.*', ' subtitle'),
    ]
    
    base = title
    for pattern, _ in season_patterns:
        base = re.sub(pattern, '', base, flags=re.IGNORECASE)
    
    base = base.strip()
    if base and base != title and len(base) > 3:
        variations.append(base)
    
    return variations

# ============================================
# PRE-COMPUTATION & INDEXING
# ============================================

def precompute_entry(entry):
    """Pre-compute all matching signals for a DB entry"""
    title = entry.get('title', '')
    if not title:
        return None
    
    tokens = extract_tokens(title)
    first, last = get_anchors(title)
    
    entry['_tokens'] = set(tokens)
    entry['_anchors_first'] = set(first)
    entry['_anchors_last'] = set(last)
    entry['_3grams'] = ngrams_safe(title, 3)
    entry['_expanded'] = expand_title(title)
    
    return entry

def build_anchor_index(db_entries):
    """Build index mapping first anchor word to entries"""
    index = defaultdict(list)
    for entry in db_entries:
        if '_anchors_first' in entry and entry['_anchors_first']:
            for anchor in entry['_anchors_first']:
                index[anchor].append(entry)
    return index

# ============================================
# MATCHING APPROACHES (optimized versions)
# ============================================

def approach_1_token(csv_entry, candidate_entries):
    """Token overlap matching - optimized with precomputed data"""
    csv_tokens = csv_entry.get('_tokens', set())
    if not csv_tokens:
        return None, 0, 0
    
    best = None
    best_score = 0
    best_pass = 0
    
    for db_entry in candidate_entries:
        db_tokens = db_entry.get('_tokens', set())
        if not db_tokens:
            continue
        
        overlap = calc_overlap(csv_tokens, db_tokens)
        
        # Pass 1: Exact token set match
        if overlap == 1.0 and csv_tokens == db_tokens:
            return db_entry, 1, 1.0
        
        # Track best by threshold
        if overlap >= 0.9 and best_pass < 2:
            best, best_score, best_pass = db_entry, overlap, 2
        elif overlap >= 0.7 and best_pass < 3:
            best, best_score, best_pass = db_entry, overlap, 3
        elif overlap >= 0.5 and best_pass < 4:
            best, best_score, best_pass = db_entry, overlap, 4
    
    return best, best_pass, best_score

def approach_2_anchor_score(csv_entry, candidate_entries):
    """Weighted anchor-first scoring"""
    csv_first = csv_entry.get('_anchors_first', set())
    csv_last = csv_entry.get('_anchors_last', set())
    csv_tokens = csv_entry.get('_tokens', set())
    csv_3grams = csv_entry.get('_3grams', set())
    csv_title = csv_entry.get('title', '')
    
    if not csv_first and not csv_last:
        return None, 0, 0
    
    best = None
    best_score = 0
    best_pass = 0
    
    for db_entry in candidate_entries:
        db_first = db_entry.get('_anchors_first', set())
        db_last = db_entry.get('_anchors_last', set())
        
        # Must share at least one anchor
        first_match = bool(csv_first & db_first)
        last_match = bool(csv_last & db_last)
        
        if not first_match and not last_match:
            continue
        
        # Calculate weighted score
        anchor_score = (0.4 if first_match else 0) + (0.2 if last_match else 0)
        
        db_tokens = db_entry.get('_tokens', set())
        token_score = calc_overlap(csv_tokens, db_tokens) * 0.3
        
        db_3grams = db_entry.get('_3grams', set())
        ngram_score = calc_overlap(csv_3grams, db_3grams) * 0.2
        
        len_ratio = min(len(csv_title), len(db_entry.get('title', ''))) / \
                    max(len(csv_title), 1) if csv_title else 0
        len_score = len_ratio * 0.1
        
        total = anchor_score + token_score + ngram_score + len_score
        
        # Track by pass threshold
        if total >= 0.9 and best_pass <= 1:
            best, best_score, best_pass = db_entry, total, 1
        elif total >= 0.75 and best_pass <= 2:
            best, best_score, best_pass = db_entry, total, 2
        elif total >= 0.6 and best_pass <= 3:
            best, best_score, best_pass = db_entry, total, 3
        elif total >= 0.45 and best_pass <= 4:
            best, best_score, best_pass = db_entry, total, 4
    
    return best, best_pass, best_score

def approach_3_expanded(csv_entry, candidate_entries):
    """Synonym-aware with expanded titles"""
    csv_expanded = csv_entry.get('_expanded', [csv_entry.get('title', '')])
    csv_tokens = csv_entry.get('_tokens', set())
    
    best = None
    best_score = 0
    best_pass = 0
    
    for db_entry in candidate_entries:
        db_expanded = db_entry.get('_expanded', [db_entry.get('title', '')])
        
        for csv_var in csv_expanded:
            csv_var_tokens = set(extract_tokens(csv_var))
            if not csv_var_tokens:
                continue
                
            for db_var in db_expanded:
                db_var_tokens = set(extract_tokens(db_var))
                if not db_var_tokens:
                    continue
                
                # Exact match on expanded
                if csv_var_tokens == db_var_tokens:
                    return db_entry, 1, 1.0
                
                # Subset/superset
                if csv_var_tokens <= db_var_tokens or db_var_tokens <= csv_var_tokens:
                    score = calc_overlap(csv_var_tokens, db_var_tokens)
                    if best_pass < 2:
                        best, best_score, best_pass = db_entry, score, 2
                
                # Overlap thresholds
                overlap = calc_overlap(csv_var_tokens, db_var_tokens)
                if overlap >= 0.7 and best_pass < 3:
                    best, best_score, best_pass = db_entry, overlap, 3
                elif overlap >= 0.5 and best_pass < 4:
                    best, best_score, best_pass = db_entry, overlap, 4
    
    return best, best_pass, best_score

# ============================================
# MAIN EXECUTION
# ============================================

def log_progress(current, total, label=""):
    """Print progress every 10%"""
    if total == 0:
        return
    pct = (current / total) * 100
    if current % max(1, total // 10) == 0 or current == total:
        print(f"  {label}: {current}/{total} ({pct:.0f}%)")

def main():
    print("=" * 80)
    print("BULLETPROOFED CASCADE MATCHING v2")
    print("=" * 80)
    print(f"\nConfig: TEST_SIZE={TEST_SIZE}, CHUNKS={CHUNKS_TO_LOAD}")
    
    # Phase 1: Load CSV
    print("\n📥 PHASE 1: Loading CSV entries...")
    csv_entries = []
    with open('animelist_enriched4.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['MAL_URL'] == 'FAILED_LOOKUP':
                csv_entries.append({
                    'title': row['Title'],
                    'type': row['Type'],
                    'notes': row['Notes']
                })
    
    print(f"   Found {len(csv_entries)} entries needing enrichment")
    
    # Precompute CSV entries too
    print("   Precomputing CSV entry signals...")
    for entry in csv_entries:
        precompute_entry(entry)
    
    # Phase 2: Load DB
    print(f"\n📥 PHASE 2: Loading {CHUNKS_TO_LOAD} offline DB chunks...")
    db_entries = []
    for i in range(CHUNKS_TO_LOAD):
        with open(f'chunks/chunk-0{i}.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            for entry in data['data']:
                db_entry = {
                    'title': entry['title'],
                    'sources': entry.get('sources', []),
                    'type': entry.get('type', ''),
                }
                if precompute_entry(db_entry):
                    db_entries.append(db_entry)
                
                # Add synonyms
                for syn in entry.get('synonyms', [])[:3]:  # Limit synonyms
                    syn_entry = {
                        'title': syn,
                        'sources': entry.get('sources', []),
                        'type': entry.get('type', ''),
                        'is_synonym': True
                    }
                    if precompute_entry(syn_entry):
                        db_entries.append(syn_entry)
        log_progress(i + 1, CHUNKS_TO_LOAD, "Chunks")
    
    print(f"   Loaded {len(db_entries)} DB entries (with synonyms)")
    
    # Phase 3: Build index
    print("\n🔧 PHASE 3: Building anchor index...")
    anchor_index = build_anchor_index(db_entries)
    print(f"   Index size: {len(anchor_index)} unique first words")
    print(f"   Avg entries per anchor: {len(db_entries)/max(len(anchor_index),1):.0f}")
    
    # Phase 4: Test matching
    test_entries = csv_entries[:TEST_SIZE]
    print(f"\n🧪 PHASE 4: Testing on {len(test_entries)} entries...")
    print("-" * 80)
    
    results = []
    start_time = time.time()
    
    for idx, csv_entry in enumerate(test_entries):
        csv_title = csv_entry['title']
        csv_first = csv_entry.get('_anchors_first', set())
        
        # Get candidate pool from index (or full DB if no anchor)
        if csv_first:
            candidates = []
            for anchor in csv_first:
                candidates.extend(anchor_index.get(anchor, []))
            candidates = list({id(c): c for c in candidates}.values())  # Deduplicate
        else:
            candidates = db_entries
        
        # Try all three approaches
        match1, pass1, score1 = approach_1_token(csv_entry, candidates)
        match2, pass2, score2 = approach_2_anchor_score(csv_entry, candidates)
        match3, pass3, score3 = approach_3_expanded(csv_entry, candidates)
        
        # Record results
        result = {
            'csv_title': csv_title,
            'csv_type': csv_entry.get('type', ''),
            'candidates_checked': len(candidates),
            'approach_1': {'match': match1['title'] if match1 else None, 'pass': pass1, 'score': score1},
            'approach_2': {'match': match2['title'] if match2 else None, 'pass': pass2, 'score': score2},
            'approach_3': {'match': match3['title'] if match3 else None, 'pass': pass3, 'score': score3},
        }
        results.append(result)
        
        # Progress
        if (idx + 1) % max(1, len(test_entries) // 5) == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed
            print(f"   Processed {idx + 1}/{len(test_entries)} ({rate:.1f} entries/sec)")
    
    total_time = time.time() - start_time
    
    # Phase 5: Analysis
    print("\n" + "=" * 80)
    print("📊 RESULTS ANALYSIS")
    print("=" * 80)
    
    # Count matches per approach
    stats = {
        'approach_1': {'matches': 0, 'by_pass': defaultdict(int), 'avg_score': []},
        'approach_2': {'matches': 0, 'by_pass': defaultdict(int), 'avg_score': []},
        'approach_3': {'matches': 0, 'by_pass': defaultdict(int), 'avg_score': []},
    }
    
    disagreements = []
    
    for r in results:
        for approach in ['approach_1', 'approach_2', 'approach_3']:
            data = r[approach]
            if data['match']:
                stats[approach]['matches'] += 1
                stats[approach]['by_pass'][data['pass']] += 1
                stats[approach]['avg_score'].append(data['score'])
        
        # Check for disagreements
        m1, m2, m3 = r['approach_1']['match'], r['approach_2']['match'], r['approach_3']['match']
        matches = [m for m in [m1, m2, m3] if m]
        if len(set(matches)) > 1:
            disagreements.append(r)
    
    # Print stats
    print(f"\nTiming: {total_time:.2f}s total ({total_time/len(test_entries):.3f}s per entry)")
    print(f"\n{'Approach':<15} {'Matches':>10} {'Rate':>8} {'Avg Score':>10}")
    print("-" * 50)
    for name, data in stats.items():
        matches = data['matches']
        rate = matches / len(test_entries) * 100
        avg = sum(data['avg_score']) / len(data['avg_score']) if data['avg_score'] else 0
        print(f"{name:<15} {matches:>10} {rate:>7.1f}% {avg:>9.3f}")
    
    print(f"\nPass distribution:")
    for name, data in stats.items():
        print(f"  {name}: {dict(data['by_pass'])}")
    
    # Show sample matches
    print("\n" + "-" * 80)
    print("🔍 SAMPLE MATCHES (first 5):")
    print("-" * 80)
    for r in results[:5]:
        print(f"\nCSV: '{r['csv_title']}'")
        print(f"  A1 (Token):  {r['approach_1']['match'] or 'NO MATCH'} (p{r['approach_1']['pass']}, {r['approach_1']['score']:.2f})")
        print(f"  A2 (Anchor): {r['approach_2']['match'] or 'NO MATCH'} (p{r['approach_2']['pass']}, {r['approach_2']['score']:.2f})")
        print(f"  A3 (Expand): {r['approach_3']['match'] or 'NO MATCH'} (p{r['approach_3']['pass']}, {r['approach_3']['score']:.2f})")
    
    # Show disagreements
    if disagreements:
        print("\n" + "-" * 80)
        print(f"⚠️  DISAGREEMENTS ({len(disagreements)} cases - approaches differ):")
        print("-" * 80)
        for r in disagreements[:3]:
            print(f"\nCSV: '{r['csv_title']}'")
            print(f"  A1: {r['approach_1']['match']}")
            print(f"  A2: {r['approach_2']['match']}")
            print(f"  A3: {r['approach_3']['match']}")
    
    # Export results
    output_file = 'matching_results.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['csv_title', 'a1_match', 'a1_pass', 'a1_score', 
                        'a2_match', 'a2_pass', 'a2_score',
                        'a3_match', 'a3_pass', 'a3_score', 'candidates'])
        for r in results:
            writer.writerow([
                r['csv_title'],
                r['approach_1']['match'], r['approach_1']['pass'], f"{r['approach_1']['score']:.3f}",
                r['approach_2']['match'], r['approach_2']['pass'], f"{r['approach_2']['score']:.3f}",
                r['approach_3']['match'], r['approach_3']['pass'], f"{r['approach_3']['score']:.3f}",
                r['candidates_checked']
            ])
    print(f"\n💾 Detailed results exported to: {output_file}")
    
    # Recommendation
    print("\n" + "=" * 80)
    print("🎯 RECOMMENDATION")
    print("=" * 80)
    best = max(stats, key=lambda x: stats[x]['matches'])
    print(f"Best approach: {best} ({stats[best]['matches']}/{len(test_entries)} matches)")
    
    if disagreements:
        print(f"\n⚠️  {len(disagreements)} entries have approach disagreements.")
        print("   Recommend: Manual review of disagreements to determine best approach")
    else:
        print("\n✅ All approaches agree - high confidence in results")

if __name__ == '__main__':
    main()
