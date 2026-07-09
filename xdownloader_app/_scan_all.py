import csv, os, re, glob, json

root = os.environ.get('XDL_DOWNLOAD_ROOT', os.path.join(os.getcwd(), 'downloads'))
result = []

for folder_name in os.listdir(root):
    folder = os.path.join(root, folder_name)
    if not os.path.isdir(folder) or '@' not in folder_name:
        continue
    
    handle = folder_name.rsplit('@', 1)[1]
    csv_path = os.path.join(folder, f'{handle}.csv')
    
    # Collect disk media files
    disk_files = set()
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith('.csv') or fname == 'cache_data.log':
            continue
        disk_files.add(fname)
    
    # Collect CSV local files
    csv_files = set()
    if os.path.isfile(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                for row in csv.reader(f):
                    if len(row) >= 7 and row[6]:
                        csv_files.add(row[6])
        except Exception:
            pass
    
    orphans = disk_files - csv_files
    stale = csv_files - disk_files  # CSV records pointing to deleted files
    
    # Check for literal duplicates (same content, different name)
    # Quick check: same prefix with one numeric suffix one hash suffix
    numeric_suffix = {}
    hash_suffix = {}
    for fname in disk_files:
        m = re.match(r'(.+?)_(\d+)\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fname, re.I)
        if m:
            numeric_suffix.setdefault(m.group(1), []).append(fname)
        m = re.match(r'(.+?)_([0-9a-fA-F]{8})\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fname, re.I)
        if m:
            hash_suffix.setdefault(m.group(1), []).append(fname)
    
    dupe_pairs = 0
    for prefix, nlist in numeric_suffix.items():
        if prefix in hash_suffix:
            dupe_pairs += 1
    
    if orphans or stale or dupe_pairs:
        result.append({
            'folder': folder_name,
            'disk': len(disk_files),
            'csv': len(csv_files),
            'orphans': len(orphans),
            'stale': len(stale),
            'dupes': dupe_pairs,
            'orphan_list': sorted(orphans)[:5],
        })

print(f'Total user folders scanned: {len(result)}')
total_orphans = sum(r['orphans'] for r in result)
total_stale = sum(r['stale'] for r in result)
total_dupes = sum(r['dupes'] for r in result)
total_broken = sum(1 for r in result if r['orphans'] > 0 or r['dupes'] > 0)

print(f'Folders with issues: {total_broken}')
print(f'Total orphan files: {total_orphans}')
print(f'Total stale CSV records: {total_stale}')
print(f'Total duplicate pairs: {total_dupes}')
print()

for r in result:
    flags = []
    if r['orphans']: flags.append(f"orphan={r['orphans']}")
    if r['dupes']: flags.append(f"dupe={r['dupes']}")
    if r['stale'] > 50: flags.append(f"stale={r['stale']}")
    if flags:
        print(f"  {r['folder']}: disk={r['disk']} csv={r['csv']} {', '.join(flags)}")
        if r['orphan_list']:
            for fn in r['orphan_list']:
                print(f"    {fn}")
