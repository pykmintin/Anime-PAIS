import csv

# The titles and their AniList URLs that I found from searches
corrections = {
    "Vivy -Fluorite Eye's Song-": "https://anilist.co/anime/136256",
    "Mob Psycho 100 II": "https://anilist.co/anime/101338",
    "Ranking of Kings": "https://anilist.co/anime/113717",
    "Darker than Black": "https://anilist.co/anime/2025",
    "INUYASHIKI LAST HERO": "https://anilist.co/anime/97922",
    "Talentless Nana": "https://anilist.co/anime/117343",
    "Buddy Daddies": "https://anilist.co/anime/155907",
    "K": "https://anilist.co/anime/14467"
}

rows = []
with open('animelist_enriched4.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print("=== CURRENT STATUS OF ANIME I FOUND ===\n")
for i, row in enumerate(rows, 1):
    title = row['Title']
    if title in corrections:
        print(f"Row {i}: {title}")
        print(f"  Current AniList_URL: {row['AniList_URL']}")
        print(f"  Should be: {corrections[title]}")
        print()

# Check row 178 specifically
print("=== ROW 178 (where I incorrectly put K's URL) ===")
print(f"Title: {rows[177]['Title']}")
print(f"Current AniList_URL: {rows[177]['AniList_URL']}")
print()

# Check if there are any other rows with 14467
print("=== CHECKING FOR OTHER INCORRECT 14467 ENTRIES ===")
found = False
for i, row in enumerate(rows, 1):
    if '14467' in str(row.get('AniList_URL', '')):
        print(f"Row {i}: {row['Title']} has AniList_URL with 14467")
        found = True
if not found:
    print("No other entries with 14467 found")
