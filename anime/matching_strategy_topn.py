#!/usr/bin/env python3
"""
TOP-N CANDIDATE MATCHING STRATEGY
Returns multiple potential matches for human verification
Uses full dataset (not chunks) for complete coverage
"""

import json
import csv
import re
import time
from collections import defaultdict

# ============================================
# CONFIGURATION
# ============================================
TOP_N = 5  # Number of candidates to return per approach
MAX_CANDIDATES = 100  # Limit candidates for performance

# ============================================
# NORMALIZATION FUNCTIONS
# ============================================

def safe_normalize(title):
    if not title or not isinstance(title, str):
        return ""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def extract_tokens(title):
    common_words = {'the', 'a', 'an', 'and', 'or', 'of', 'is', 'to', 'in', 'on', 'at', 'with', 'for', 'by'}
    normalized = safe_normalize(title)
    if not normalized:
        return []
    tokens = normalized.split()
    return [t for t in tokens if t not in common_words and len(t) > 1]

def get_anchors(title):
    tokens = extract_tokens(title)
    if not tokens:
        return [], []
    if len(tokens) == 1:
        return tokens, []
    return [tokens[0]], [tokens[-1]]

def calc_overlap(set1, set2):
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    if not union:
        return 0.0
    return len(intersection) / len(union)

def expand_title(title):
    """Generate variations by removing season markers"""
    if not title:
        return [""]
    
    variations = [title]
    season_patterns = [
        r'\s+season\s+\d+', r'\s+s\d+\b', r'\s+part\s+\d+',
        r'\s+\d+nd\s+season', r'\s+\d+rd\s+season', r'\s+\d+th\s+season',
        r':\s*the\s+final', r'\s+final\s+season',
        r':\s*ultra\s+romantic', r':\s*beyond\s+.*',
    ]
    
    base = title
    for pattern in season_patterns:
        base = re.sub(pattern, '', base, flags=re.IGNORECASE)
    
    base = base.strip()
    if base and base != title and len(base) > 3:
        variations.append(base)
    
    return variations

# ============================================
# PRE-COMPUTATION
# ============================================

def precompute_entry(entry):
    title = entry.get('title', '')
    if not title:
        return None
    
    tokens = extract_tokens(title)
    first, last = get_anchors(title)
    
    entry['_tokens'] = set(tokens)
    entry['_anchors_first'] = set(first)
    entry['_anchors_last'] = set(last)
    entry['_expanded'] = expand_title(title)
    
    return entry

def build_anchor_index(db_entries):
    index = defaultdict(list)
    for entry in db_entries:
        if '_anchors_first' in entry and entry['_anchors_first']:
            for anchor in entry['_anchors_first']:
                index[anchor].append(entry)
    return index

# ============================================
# TOP-N MATCHING APPROACHES
# ============================================

def approach_1_token_topn(csv_entry, candidate_entries, n=TOP_N):
    """Return top N matches by token overlap"""
    csv_tokens = csv_entry.get('_tokens', set())
    if not csv_tokens:
        return []
    
    scored = []
    for db_entry in candidate_entries:
        db_tokens = db_entry.get('_tokens', set())
        if not db_tokens:
            continue
        
        overlap = calc_overlap(csv_tokens, db_tokens)
        if overlap > 0.3:  # Minimum threshold
            scored.append((db_entry, overlap, 'token'))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:n]

def approach_2_anchor_topn(csv_entry, candidate_entries, n=TOP_N):
    """Return top N matches by anchor+scoring"""
    csv_first = csv_entry.get('_anchors_first', set())
    csv_last = csv_entry.get('_anchors_last', set())
    csv_tokens = csv_entry.get('_tokens', set())
    csv_title = csv_entry.get('title', '')
    
    scored = []
    for db_entry in candidate_entries:
        db_first = db_entry.get('_anchors_first', set())
        db_last = db_entry.get('_anchors_last', set())
        
        first_match = bool(csv_first & db_first)
        last_match = bool(csv_last & db_last)
        
        if not first_match and not last_match:
            continue
        
        anchor_score = (0.4 if first_match else 0) + (0.2 if last_match else 0)
        db_tokens = db_entry.get('_tokens', set())
        token_score = calc_overlap(csv_tokens, db_tokens) * 0.4
        len_ratio = min(len(csv_title), len(db_entry.get('title', ''))) / max(len(csv_title), 1) if csv_title else 0
        len_score = len_ratio * 0.2
        
        total = anchor_score + token_score + len_score
        
        if total > 0.4:  # Minimum threshold
            scored.append((db_entry, total, 'anchor'))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:n]

def approach_3_expand_topn(csv_entry, candidate_entries, n=TOP_N):
    """Return top N matches by expanded title matching"""
    csv_expanded = csv_entry.get('_expanded', [csv_entry.get('title', '')])
    
    scored = []
    for db_entry in candidate_entries:
        db_expanded = db_entry.get('_expanded', [db_entry.get('title', '')])
        
        best_overlap = 0
        for csv_var in csv_expanded:
            csv_tokens = set(extract_tokens(csv_var))
            if not csv_tokens:
                continue
            for db_var in db_expanded:
                db_tokens = set(extract_tokens(db_var))
                if not db_tokens:
                    continue
                overlap = calc_overlap(csv_tokens, db_tokens)
                best_overlap = max(best_overlap, overlap)
        
        if best_overlap > 0.5:  # Minimum threshold
            scored.append((db_entry, best_overlap, 'expand'))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:n]

# ============================================
# MAIN EXECUTION
# ============================================

def main():
    print("=" * 80)
    print("TOP-N CANDIDATE MATCHING - Full Dataset")
    print("=" * 80)
    
    # Phase 1: Load CSV
    print("\n📥 Loading CSV entries...")
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
    
    # Precompute CSV entries
    for entry in csv_entries:
        precompute_entry(entry)
    
    # Phase 2: Load FULL dataset (not chunks)
    print("\n📥 Loading FULL offline database (58MB)...")
    start = time.time()
    
    db_entries = []
    with open('anime-offline-database-minified.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        for entry in data['data']:
            db_entry = {
                'title': entry['title'],
                'sources': entry.get('sources', []),
                'type': entry.get('type', ''),
                'status': entry.get('status', ''),
            }
            if precompute_entry(db_entry):
                db_entries.append(db_entry)
            
            # Add synonyms
            for syn in entry.get('synonyms', [])[:3]:
                syn_entry = {
                    'title': syn,
                    'sources': entry.get('sources', []),
                    'type': entry.get('type', ''),
                    'status': entry.get('status', ''),
                    'is_synonym': True
                }
                if precompute_entry(syn_entry):
                    db_entries.append(syn_entry)
    
    load_time = time.time() - start
    print(f"   ✓ Loaded {len(db_entries)} entries in {load_time:.2f}s")
    
    # Phase 3: Build index
    print("\n🔧 Building anchor index...")
    anchor_index = build_anchor_index(db_entries)
    print(f"   Index: {len(anchor_index)} anchors, ~{len(db_entries)//len(anchor_index)} entries/anchor")
    
    # Phase 4: Match first 20 entries with full candidate visibility
    test_entries = csv_entries[:20]
    print(f"\n🧪 Matching {len(test_entries)} entries (showing top {TOP_N} candidates each)...")
    print("=" * 80)
    
    results = []
    
    for idx, csv_entry in enumerate(test_entries):
        csv_title = csv_entry['title']
        csv_first = csv_entry.get('_anchors_first', set())
        
        # Get candidates via index
        if csv_first:
            candidates = []
            for anchor in csv_first:
                candidates.extend(anchor_index.get(anchor, []))
            candidates = list({id(c): c for c in candidates}.values())
        else:
            candidates = db_entries[:MAX_CANDIDATES]  # Limit for no-anchor case
        
        # Get top N from each approach
        a1_results = approach_1_token_topn(csv_entry, candidates)
        a2_results = approach_2_anchor_topn(csv_entry, candidates)
        a3_results = approach_3_expand_topn(csv_entry, candidates)
        
        # Print results
        print(f"\n[{idx+1}] '{csv_title}'")
        print(f"    Type: {csv_entry.get('type', 'N/A')} | Candidates checked: {len(candidates)}")
        print(f"    Tokens: {list(csv_entry.get('_tokens', []))[:5]}")
        
        if a1_results:
            print(f"    ├─ Token Match:")
            for match, score, _ in a1_results[:3]:
                marker = " ✓" if score == 1.0 else ""
                print(f"    │  • {match['title'][:50]:<50} ({score:.2f}){marker}")
        
        if a2_results:
            print(f"    ├─ Anchor Match:")
            for match, score, _ in a2_results[:3]:
                marker = " ✓" if score >= 0.8 else ""
                print(f"    │  • {match['title'][:50]:<50} ({score:.2f}){marker}")
        
        if a3_results:
            print(f"    └─ Expand Match:")
            for match, score, _ in a3_results[:3]:
                marker = " ✓" if score >= 0.8 else ""
                print(f"       • {match['title'][:50]:<50} ({score:.2f}){marker}")
        
        if not a1_results and not a2_results and not a3_results:
            print(f"    └─ ❌ NO MATCHES FOUND")
        
        results.append({
            'csv_title': csv_title,
            'candidates': len(candidates),
            'a1_count': len(a1_results),
            'a2_count': len(a2_results),
            'a3_count': len(a3_results),
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    with_matches = sum(1 for r in results if r['a1_count'] + r['a2_count'] + r['a3_count'] > 0)
    print(f"\nEntries with at least one candidate: {with_matches}/{len(test_entries)} ({with_matches/len(test_entries)*100:.1f}%)")
    print(f"\nBreakdown:")
    print(f"  Token approach: {sum(r['a1_count'] for r in results)} total candidates")
    print(f"  Anchor approach: {sum(r['a2_count'] for r in results)} total candidates")
    print(f"  Expand approach: {sum(r['a3_count'] for r in results)} total candidates")
    
    # Export full results for all 285 entries
    print("\n" + "=" * 80)
    print(f"🚀 Processing ALL {len(csv_entries)} entries for export...")
    print("=" * 80)
    
    full_results = []
    for idx, csv_entry in enumerate(csv_entries):
        csv_title = csv_entry['title']
        csv_first = csv_entry.get('_anchors_first', set())
        
        if csv_first:
            candidates = []
            for anchor in csv_first:
                candidates.extend(anchor_index.get(anchor, []))
            candidates = list({id(c): c for c in candidates}.values())
        else:
            candidates = db_entries[:MAX_CANDIDATES]
        
        a1_results = approach_1_token_topn(csv_entry, candidates, n=3)
        a2_results = approach_2_anchor_topn(csv_entry, candidates, n=3)
        a3_results = approach_3_expand_topn(csv_entry, candidates, n=3)
        
        # Combine all candidates, deduplicate, sort by score
        all_candidates = {}
        for match, score, method in (a1_results + a2_results + a3_results):
            title = match['title']
            if title not in all_candidates or all_candidates[title]['score'] < score:
                all_candidates[title] = {
                    'title': title,
                    'score': score,
                    'method': method,
                    'sources': match.get('sources', [])
                }
        
        # Sort by score, take top 5
        top_candidates = sorted(all_candidates.values(), key=lambda x: x['score'], reverse=True)[:5]
        
        # Extract MAL and AniList URLs if available
        mal_url = ''
        anilist_url = ''
        if top_candidates:
            for src in top_candidates[0].get('sources', []):
                if 'myanimelist' in src:
                    mal_url = src
                elif 'anilist' in src:
                    anilist_url = src
        
        full_results.append({
            'csv_title': csv_title,
            'csv_type': csv_entry.get('type', ''),
            'top_candidate': top_candidates[0]['title'] if top_candidates else '',
            'top_score': top_candidates[0]['score'] if top_candidates else 0,
            'top_method': top_candidates[0]['method'] if top_candidates else '',
            'mal_url': mal_url,
            'anilist_url': anilist_url,
            'candidate_count': len(top_candidates),
        })
        
        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(csv_entries)}...")
    
    # Export to CSV
    output_file = 'matching_candidates_all.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'csv_title', 'csv_type', 'top_candidate', 'top_score', 
            'top_method', 'mal_url', 'anilist_url', 'candidate_count'
        ])
        writer.writeheader()
        writer.writerows(full_results)
    
    print(f"\n💾 Full results exported to: {output_file}")
    
    # Stats
    with_candidates = sum(1 for r in full_results if r['candidate_count'] > 0)
    high_confidence = sum(1 for r in full_results if r['top_score'] >= 0.8)
    print(f"\n📈 Final Stats:")
    print(f"  Total CSV entries: {len(full_results)}")
    print(f"  With candidates: {with_candidates} ({with_candidates/len(full_results)*100:.1f}%)")
    print(f"  High confidence (≥0.8): {high_confidence} ({high_confidence/len(full_results)*100:.1f}%)")

if __name__ == '__main__':
    main()
