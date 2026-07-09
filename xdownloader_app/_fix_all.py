import csv
import os
import re
import hashlib
import shutil
import time

ROOT = os.environ.get('XDL_DOWNLOAD_ROOT', os.path.join(os.getcwd(), 'downloads'))

def get_file_md5(fpath):
    hash_md5 = hashlib.md5()
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def fix_single_folder(folder_path, handle):
    csv_path = os.path.join(folder_path, f'{handle}.csv')
    folder_name = os.path.basename(folder_path)

    csv_rows = []
    csv_files_map = {}
    if os.path.isfile(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                csv_rows.append(row)
                if len(row) >= 7 and row[6]:
                    csv_files_map[row[6]] = row

    disk_files = []
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith('.csv') or fname == 'cache_data.log':
            continue
        disk_files.append(fname)

    file_md5_map = {}
    md5_groups = {}

    for fname in disk_files:
        fpath = os.path.join(folder_path, fname)
        try:
            md5 = get_file_md5(fpath)
            file_md5_map[fname] = md5
            md5_groups.setdefault(md5, []).append(fname)
        except OSError:
            continue

    removed_dupes = 0
    for md5, fnames in md5_groups.items():
        if len(fnames) > 1:
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

            for fn in fnames:
                if fn != keep:
                    try:
                        os.remove(os.path.join(folder_path, fn))
                        removed_dupes += 1
                    except OSError:
                        pass
                    if fn in csv_files_map:
                        del csv_files_map[fn]
                        for r in csv_rows:
                            if len(r) >= 7 and r[6] == fn:
                                r[6] = keep
                                csv_files_map[keep] = r
                                break

    disk_files = []
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith('.csv') or fname == 'cache_data.log':
            continue
        disk_files.append(fname)

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
            added_to_csv += 1

    current_disk_set = set(disk_files)
    stale_count = 0
    filtered_rows = []
    for row in csv_rows:
        if len(row) >= 7 and row[6]:
            if row[6] not in current_disk_set:
                stale_count += 1
                continue
        filtered_rows.append(row)

    if os.path.isfile(csv_path):
        backup_path = csv_path + '.bak'
        try:
            shutil.copy2(csv_path, backup_path)
        except OSError:
            pass

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(filtered_rows)

    return removed_dupes, added_to_csv, stale_count


def main():
    print("=" * 60, flush=True)
    print("  X/Twitter 一键修复工具 - 处理所有文件夹", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    total_folders = 0
    total_dupes_removed = 0
    total_orphans_added = 0
    total_stale_removed = 0
    fixed_folders = []
    skipped_folders = []

    all_folders = sorted([
        d for d in os.listdir(ROOT) if '@' in d
    ])

    print(f"发现 {len(all_folders)} 个用户文件夹，开始逐个检查...", flush=True)
    print(flush=True)

    for i, folder_name in enumerate(all_folders, 1):
        folder_path = os.path.join(ROOT, folder_name)
        if not os.path.isdir(folder_path):
            continue

        handle = folder_name.rsplit('@', 1)[1]
        csv_path = os.path.join(folder_path, f'{handle}.csv')

        # Quick pre-check: count orphans and dupes without MD5 (fast scan)
        disk_files = set()
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath):
                continue
            if fname.endswith('.csv') or fname == 'cache_data.log':
                continue
            disk_files.add(fname)

        csv_file_set = set()
        if os.path.isfile(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    for row in csv.reader(f):
                        if len(row) >= 7 and row[6]:
                            csv_file_set.add(row[6])
            except Exception:
                pass

        orphans_quick = disk_files - csv_file_set
        stale_quick = csv_file_set - disk_files

        # Check for potential numeric-vs-hash duplicates (name-based only)
        numeric_pre = set()
        hash_pre = set()
        for fname in disk_files:
            m = re.match(r'(.+?)_(\d+)\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fname, re.I)
            if m:
                numeric_pre.add(m.group(1))
            m = re.match(r'(.+?)_([0-9a-fA-F]{8})\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$', fname, re.I)
            if m:
                hash_pre.add(m.group(1))
        potential_dupes = len(numeric_pre & hash_pre)

        needs_fix = bool(orphans_quick) or bool(stale_quick) or potential_dupes > 0

        if needs_fix:
            progress = f"[{i}/{len(all_folders)}]"
            print(f"{progress} {folder_name}: orphan={len(orphans_quick)} stale={len(stale_quick)} dupe~{potential_dupes}  -> 修复中...", flush=True)

            t0 = time.time()
            d, o, s = fix_single_folder(folder_path, handle)
            elapsed = time.time() - t0

            total_dupes_removed += d
            total_orphans_added += o
            total_stale_removed += s
            total_folders += 1

            parts = []
            if d: parts.append(f"去重{d}")
            if o: parts.append(f"+{o}孤儿")
            if s: parts.append(f"-{s}过期")
            print(f"      -> 完成 ({elapsed:.1f}s): {' | '.join(parts)}", flush=True)
            fixed_folders.append(folder_name)
        else:
            skipped_folders.append(folder_name)

    print(flush=True)
    print("=" * 60, flush=True)
    print("  全部处理完成!", flush=True)
    print("=" * 60, flush=True)
    print(f"  已修复文件夹: {len(fixed_folders)}", flush=True)
    print(f"  无问题跳过:   {len(skipped_folders)}", flush=True)
    print(f"  删除重复文件: {total_dupes_removed}", flush=True)
    print(f"  补回孤儿记录: {total_orphans_added}", flush=True)
    print(f"  清理过期记录: {total_stale_removed}", flush=True)
    print(flush=True)
    print("  每个文件夹的原始CSV已备份为 .bak 文件", flush=True)
    print("=" * 60, flush=True)


if __name__ == '__main__':
    main()
