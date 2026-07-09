
import csv
import os
import re
import hashlib
import shutil

def get_file_md5(fpath):
    hash_md5 = hashlib.md5()
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def fix_single_folder(folder_path, handle):
    csv_path = os.path.join(folder_path, f'{handle}.csv')
    
    print(f"Processing: {os.path.basename(folder_path)}")
    print(f"  CSV: {csv_path}")
    
    # Step 1: Load CSV
    csv_rows = []
    csv_files_map = {}  # local_filename -> row
    if os.path.isfile(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                csv_rows.append(row)
                if len(row) >= 7 and row[6]:
                    csv_files_map[row[6]] = row
    
    # Step 2: List disk files
    disk_files = []
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith('.csv') or fname == 'cache_data.log':
            continue
        disk_files.append(fname)
    
    # Step 3: Group potential duplicates and compute MD5
    file_md5_map = {}
    md5_groups = {}
    
    for fname in disk_files:
        fpath = os.path.join(folder_path, fname)
        md5 = get_file_md5(fpath)
        file_md5_map[fname] = md5
        md5_groups.setdefault(md5, []).append(fname)
    
    # Step 4: Remove duplicates (keep one, prefer hash-named if exists)
    removed_dupes = 0
    for md5, fnames in md5_groups.items():
        if len(fnames) > 1:
            # Choose the one to keep: prefer hash suffix > numeric suffix > others
            keep = None
            for fn in fnames:
                if re.search(r'_[0-9a-fA-F]{8}\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fn, re.I):
                    keep = fn
                    break
            if not keep:
                for fn in fnames:
                    if re.search(r'_\d+\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fn, re.I):
                        keep = fn
                        break
            if not keep:
                keep = fnames[0]
            
            # Delete others
            for fn in fnames:
                if fn != keep:
                    os.remove(os.path.join(folder_path, fn))
                    print(f"  [DUP] Deleted duplicate: {fn} (kept {keep})")
                    removed_dupes += 1
                    # Also remove from csv_files_map if present
                    if fn in csv_files_map:
                        del csv_files_map[fn]
                        # Update the row to point to the kept file
                        row = csv_files_map.get(keep, None)
                        if not row:
                            # Find the row that had fn and update it
                            for r in csv_rows:
                                if len(r) >= 7 and r[6] == fn:
                                    r[6] = keep
                                    csv_files_map[keep] = r
                                    break
    
    # Step 5: Refresh disk_files after dedupe
    disk_files = []
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith('.csv') or fname == 'cache_data.log':
            continue
        disk_files.append(fname)
    
    # Step 6: Find orphans and try to recover them
    orphans = [f for f in disk_files if f not in csv_files_map]
    added_to_csv = 0
    
    for orphan in orphans:
        m = re.match(r'(\d{4}-\d{2}-\d{2}) (\d{2}-\d{2})-(img|vid)_', orphan, re.I)
        if m:
            date_str = m.group(1)
            time_str = m.group(2).replace('-', ':')
            text = f'[Recovered file: {orphan}]'
            media_type_str = 'Video' if m.group(3).lower() == 'vid' else 'Image'
            local_file = orphan
            
            similar_row = None
            for row in csv_rows:
                if len(row) >= 2 and date_str in row[0]:
                    similar_row = row
                    break
            
            display_name = ''
            user_name = ''
            tweet_url = ''
            likes = 0
            retweets = 0
            replies = 0
            if similar_row:
                if len(similar_row) >= 2 and similar_row[1]:
                    display_name = similar_row[1]
                if len(similar_row) >= 3 and similar_row[2]:
                    user_name = similar_row[2]
                if len(similar_row) >= 4 and similar_row[3]:
                    tweet_url = similar_row[3]
                if len(similar_row) >= 8 and similar_row[7]:
                    text = similar_row[7] + f' [+recovered file: {orphan}]'
                if len(similar_row) >= 9:
                    try: likes = int(similar_row[8])
                    except: pass
                if len(similar_row) >= 10:
                    try: retweets = int(similar_row[9])
                    except: pass
                if len(similar_row) >= 11:
                    try: replies = int(similar_row[10])
                    except: pass

            new_row = [
                f'{date_str} {time_str}',
                display_name,
                user_name,
                tweet_url,
                media_type_str,
                '',
                local_file,
                text,
                str(likes),
                str(retweets),
                str(replies)
            ]
            csv_rows.append(new_row)
            csv_files_map[local_file] = new_row
            print(f"  [ORPHAN] Added orphan to CSV: {orphan}")
            added_to_csv += 1
        else:
            print(f"  [WARN] Could not auto-recover orphan: {orphan}")
    
    # Step 7: Remove stale entries (CSV records pointing to non-existent files)
    # But first, refresh our view of current disk files
    current_disk_set = set(disk_files)
    stale_count = 0
    filtered_rows = []
    for row in csv_rows:
        if len(row) >= 7 and row[6]:
            if row[6] not in current_disk_set:
                stale_count += 1
                continue  # skip stale
        filtered_rows.append(row)
    
    if stale_count > 0:
        print(f"  [STALE] Removed {stale_count} stale CSV entries")
    
    # Step 8: Backup original CSV and write new one
    if os.path.isfile(csv_path):
        backup_path = csv_path + '.bak'
        shutil.copy2(csv_path, backup_path)
        print(f"  [BACKUP] Created backup: {backup_path}")
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(filtered_rows)
    
    print()
    print(f"Summary for {os.path.basename(folder_path)}:")
    print(f"  Duplicates removed: {removed_dupes}")
    print(f"  Orphans added to CSV: {added_to_csv}")
    print(f"  Stale entries removed: {stale_count}")
    print(f"  Final CSV rows: {len(filtered_rows)}")
    print()

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python _fix_single_folder.py <folder_name>")
        print('Example: python _fix_single_folder.py "UNCLE BBB@bbb_uncle"')
        sys.exit(1)
    
    root = os.environ.get('XDL_DOWNLOAD_ROOT', os.path.join(os.getcwd(), 'downloads'))
    folder_name = sys.argv[1]
    folder_path = os.path.join(root, folder_name)
    
    if '@' not in folder_name:
        print("Error: Folder name should be in format \"Name@handle\"")
        sys.exit(1)
    
    handle = folder_name.rsplit('@', 1)[1]
    
    if not os.path.isdir(folder_path):
        print(f"Error: Folder not found: {folder_path}")
        sys.exit(1)
    
    fix_single_folder(folder_path, handle)
