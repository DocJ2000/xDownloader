import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from typing import Dict, List, Tuple

from .logger import log


def _parse_folder_name(folder_name: str) -> Tuple[str, str]:
    m = re.search(r'@(\S+)$', folder_name)
    if m:
        handle = m.group(1)
        display_name = folder_name[:m.start()]
        return handle, display_name
    return None, folder_name


def _merge_pickle_cache(target_path: str, source_path: str):
    target_file = os.path.join(target_path, 'cache_data.log')
    source_file = os.path.join(source_path, 'cache_data.log')

    target_data = set()
    if os.path.exists(target_file):
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                target_data = set(json.load(f))
        except Exception:
            target_data = set()

    if os.path.exists(source_file):
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source_data = set(json.load(f))
        except Exception:
            source_data = set()
    else:
        return

    merged = source_data | target_data

    with open(target_file, 'w', encoding='utf-8') as f:
        json.dump(list(merged), f)

    log.info(f"  合并缓存: {len(merged)} 条记录")


def _merge_csv_files(target_path: str, source_path: str):
    csv_files = [f for f in os.listdir(source_path) if f.endswith('.csv')]
    for csv_file in csv_files:
        src = os.path.join(source_path, csv_file)
        dst = os.path.join(target_path, csv_file)

        if not os.path.exists(src):
            continue

        if not os.path.exists(dst):
            shutil.move(src, dst)
            log.info(f"  移动CSV: {csv_file}")
            continue

        with open(src, 'r', encoding='utf-8-sig') as f_src:
            src_lines = f_src.readlines()
        with open(dst, 'r', encoding='utf-8-sig') as f_dst:
            dst_lines = f_dst.readlines()

        header = dst_lines[0] if dst_lines else ''
        meta_rows = [l for l in dst_lines[1:] if l.startswith('#')]
        data_rows_dst = [l for l in dst_lines[1:] if not l.startswith('#')]
        data_rows_src = [l for l in src_lines[1:] if not l.startswith('#')]

        existing_urls = set()
        for row in data_rows_dst:
            parts = row.split(',', 2)
            if len(parts) >= 2:
                existing_urls.add((parts[0].strip(), parts[1].strip()))

        new_rows = []
        for row in data_rows_src:
            parts = row.split(',', 2)
            if len(parts) >= 2:
                key = (parts[0].strip(), parts[1].strip())
                if key not in existing_urls:
                    new_rows.append(row)

        if new_rows:
            with open(dst, 'w', encoding='utf-8-sig', newline='') as f_dst:
                f_dst.write(header)
                for line in meta_rows:
                    f_dst.write(line)
                for line in data_rows_dst:
                    f_dst.write(line)
                for line in new_rows:
                    f_dst.write(line)
            log.info(f"  合并CSV {csv_file}: +{len(new_rows)} 条新记录")
        else:
            log.info(f"  合并CSV {csv_file}: 无新记录")

        os.remove(src)


def merge_user_folders(download_root: str, dry_run: bool = False, screen_name: str = ""):
    groups = _find_duplicates(download_root, screen_name)

    if not groups:
        log.info("没有发现需要合并的重复文件夹")
        return

    total_merged = 0
    total_files = 0

    for handle, folders in groups.items():
        target = max(folders, key=lambda f: _count_files(os.path.join(download_root, f)))
        sources = [f for f in folders if f != target]

        target_path = os.path.join(download_root, target)
        file_count = 0

        log.info(f"\n合并 @{handle} ({len(folders)} 个文件夹) -> {target}")

        for src_folder in sources:
            src_path = os.path.join(download_root, src_folder)

            log.info(f"  处理: {src_folder}")

            _merge_pickle_cache(target_path, src_path)
            _merge_csv_files(target_path, src_path)

            if _is_empty_except_cache_csv(src_path):
                log.info(f"  无媒体文件，合并缓存/CSV后删除")
                if not dry_run:
                    try:
                        shutil.rmtree(src_path)
                    except Exception:
                        pass
                continue

            moved = _move_media_files(target_path, src_path, dry_run)
            file_count += moved

            remaining = os.listdir(src_path)
            remaining = [f for f in remaining if f not in ('cache_data.log',)]
            if not remaining:
                if not dry_run:
                    try:
                        shutil.rmtree(src_path)
                    except Exception:
                        pass
                log.info(f"  已清空并删除目录: {src_folder}")
            else:
                log.info(f"  有残留文件({len(remaining)}项)，保留目录: {src_folder}")

        total_merged += len(sources)
        total_files += file_count
        log.info(f"  完成，移动了 {file_count} 个文件")

    action = "将要合并" if dry_run else "已合并"
    log.info(f"\n{action} {total_merged} 个重复文件夹，共移动 {total_files} 个文件")


def _find_duplicates(download_root: str, screen_name: str = "") -> Dict[str, List[str]]:
    if not os.path.isdir(download_root):
        log.error(f"下载目录不存在: {download_root}")
        return {}

    all_folders = [f for f in os.listdir(download_root)
                   if os.path.isdir(os.path.join(download_root, f))]

    groups = defaultdict(list)
    for folder in all_folders:
        handle, _ = _parse_folder_name(folder)
        if handle:
            groups[handle].append(folder)

    result = {k: v for k, v in groups.items() if len(v) > 1}
    if screen_name:
        result = {k: v for k, v in result.items() if k.lower() == screen_name.lower()}
    return result


def _count_files(path: str) -> int:
    count = 0
    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                count += 1
    except Exception:
        pass
    return count


def _is_empty_except_cache_csv(path: str) -> bool:
    try:
        items = [f for f in os.listdir(path)
                 if not f.endswith('.csv') and f != 'cache_data.log']
        return len(items) == 0
    except Exception:
        return False


def _move_media_files(target_path: str, source_path: str, dry_run: bool) -> int:
    moved = 0
    for filename in os.listdir(source_path):
        if filename in ('cache_data.log',):
            continue
        if filename.endswith('.csv'):
            continue

        src = os.path.join(source_path, filename)
        if not os.path.isfile(src):
            continue

        dst = os.path.join(target_path, filename)

        if os.path.exists(dst):
            src_size = os.path.getsize(src)
            dst_size = os.path.getsize(dst)
            if src_size == dst_size:
                if not dry_run:
                    os.remove(src)
                log.info(f"  跳过重复: {filename}")
                continue
            else:
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(target_path, f"{base}_{counter}{ext}")
                    counter += 1
                log.info(f"  重名但大小不同，重命名为: {os.path.basename(dst)}")

        if not dry_run:
            shutil.move(src, dst)
        moved += 1

    return moved


def find_existing_folder(download_root: str, screen_name: str) -> str:
    if not os.path.isdir(download_root):
        return ""
    for folder in os.listdir(download_root):
        folder_path = os.path.join(download_root, folder)
        if not os.path.isdir(folder_path):
            continue
        handle, _ = _parse_folder_name(folder)
        if handle == screen_name:
            return folder_path
    return ""


def list_duplicates(download_root: str, screen_name: str = ""):
    groups = _find_duplicates(download_root, screen_name)
    if not groups:
        log.info("没有发现重复文件夹")
        return

    log.info(f"\n发现 {len(groups)} 组重复文件夹:\n")

    for handle, folders in sorted(groups.items()):
        target = max(folders, key=lambda f: _count_files(os.path.join(download_root, f)))
        log.info(f"@{handle} ({len(folders)} 个):")
        for f in folders:
            count = _count_files(os.path.join(download_root, f))
            marker = " <- [保留]" if f == target else "     [删除]"
            log.info(f"  {marker} {f} ({count} 文件)")
        log.info("")


_RE_MEDIA_FILE = re.compile(
    r'^(.+?)_([0-9a-fA-F]{8}|[0-9]+)\.(jpg|jpeg|png|gif|webp|mp4|mov|mkv)$',
    re.IGNORECASE
)
_HASH_SUFFIX = re.compile(r'^[0-9a-fA-F]{8}$')
_NUMERIC_SUFFIX = re.compile(r'^\d+$')


def _get_file_md5(file_path: str, chunk_size: int = 65536) -> str:
    h = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _pick_best_file(dupes):
    hash_dupes = [x for x in dupes if _HASH_SUFFIX.match(x[3])]
    num_dupes = [x for x in dupes if _NUMERIC_SUFFIX.match(x[3])]

    if hash_dupes:
        cand = hash_dupes
    else:
        cand = num_dupes or dupes

    cand.sort(key=lambda x: (int(x[3]) if _NUMERIC_SUFFIX.match(x[3])
                              else int(x[3], 16), x[0]))
    return cand[0]


def _collect_remaining_files(folder_path):
    remaining = []
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if not os.path.isfile(fpath):
            continue
        m = _RE_MEDIA_FILE.match(fname)
        if not m:
            continue
        try:
            fsize = os.path.getsize(fpath)
        except OSError:
            continue
        remaining.append((fname, fpath, m.group(1), m.group(2), m.group(3),
                          fsize))
    return remaining


def cleanup_duplicates(download_root: str, dry_run: bool = True,
                       screen_name: str = ""):
    if not os.path.isdir(download_root):
        log.error(f"下载目录不存在: {download_root}")
        return

    folders = [f for f in os.listdir(download_root)
               if os.path.isdir(os.path.join(download_root, f))]

    if screen_name:
        _, handle = _parse_folder_name(screen_name)
        if handle:
            handle = handle
        else:
            handle = screen_name
        folders = [f for f in folders if screen_name.lower() in f.lower()
                   or (_parse_folder_name(f)[0] or "").lower() == handle.lower()]

    if not folders:
        log.info("没有找到匹配的用户文件夹")
        return

    total_hash_deleted = 0
    total_md5_deleted = 0
    total_size_saved = 0
    affected_folders = 0

    for folder in sorted(folders):
        folder_path = os.path.join(download_root, folder)

        media_files = []
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath):
                continue
            m = _RE_MEDIA_FILE.match(fname)
            if m:
                media_files.append((fname, fpath, m))

        if not media_files:
            continue

        groups = defaultdict(list)
        for fname, fpath, m in media_files:
            prefix = m.group(1)
            suffix = m.group(2)
            ext = m.group(3)
            groups[prefix].append((fname, fpath, suffix, ext))

        folder_del = 0
        folder_size = 0

        for prefix, items in groups.items():
            if len(items) <= 1:
                continue

            hash_files = [(n, p, s, e) for n, p, s, e in items
                          if _HASH_SUFFIX.match(s)]
            num_files = [(n, p, s, e) for n, p, s, e in items
                         if _NUMERIC_SUFFIX.match(s)]

            if hash_files and num_files:
                seen_hashes = {s.lower() for _, _, s, _ in hash_files}
                for name, path, suffix, ext in num_files:
                    if suffix.lower() in seen_hashes:
                        continue
                    try:
                        fsize = os.path.getsize(path)
                    except OSError:
                        continue
                    if not dry_run:
                        os.remove(path)
                    folder_del += 1
                    folder_size += fsize
                    log.debug(f"  DEL (hash group): {name}")

            elif not hash_files and not num_files:
                continue

            elif num_files and len(num_files) > 1:
                size_map = defaultdict(list)
                for name, path, suffix, ext in num_files:
                    try:
                        size_map[os.path.getsize(path)].append(
                            (name, path, suffix, ext))
                    except OSError:
                        continue

                for fsize, same_size_files in size_map.items():
                    if len(same_size_files) <= 1:
                        continue

                    md5_map = {}
                    for name, path, suffix, ext in same_size_files:
                        h = _get_file_md5(path)
                        if not h:
                            continue
                        if h not in md5_map:
                            md5_map[h] = []
                        md5_map[h].append((name, path, suffix, ext))

                    for __, dupes in md5_map.items():
                        if len(dupes) <= 1:
                            continue
                        dupes.sort(key=lambda x: (int(x[2]), x[0]))
                        keep = dupes[0]
                        for name, path, suffix, ext in dupes[1:]:
                            if not dry_run:
                                os.remove(path)
                            folder_del += 1
                            folder_size += fsize
                            log.debug(
                                f"  DEL (MD5 dup): {name} (same as {keep[0]})"
                            )

        remaining = _collect_remaining_files(folder_path)
        if not remaining:
            if folder_del > 0:
                total_hash_deleted += folder_del
                total_size_saved += folder_size
                affected_folders += 1
                log.info(f"{folder}: {'[DRY] 将删除' if dry_run else '已删除'} "
                         f"{folder_del} 个重复文件 "
                         f"({folder_size / (1024*1024):.1f} MB)")
            continue

        size_map = defaultdict(list)
        for name, path, prefix, suffix, ext, fsize in remaining:
            size_map[fsize].append((name, path, prefix, suffix, ext))

        for fsize, same_size_files in size_map.items():
            if len(same_size_files) <= 1:
                continue

            md5_map = {}
            for name, path, prefix, suffix, ext in same_size_files:
                h = _get_file_md5(path)
                if not h:
                    continue
                if h not in md5_map:
                    md5_map[h] = []
                md5_map[h].append((name, path, prefix, suffix, ext))

            for __, dupes in md5_map.items():
                if len(dupes) <= 1:
                    continue
                keep = _pick_best_file(dupes)
                for name, path, prefix, suffix, ext in dupes:
                    if name == keep[0]:
                        continue
                    if not dry_run:
                        os.remove(path)
                    folder_del += 1
                    folder_size += fsize
                    log.debug(
                        f"  DEL (global MD5): {name} (same as {keep[0]})"
                    )

        if folder_del > 0:
            total_hash_deleted += folder_del
            total_size_saved += folder_size
            affected_folders += 1
            log.info(f"{folder}: {'[DRY] 将删除' if dry_run else '已删除'} "
                     f"{folder_del} 个重复文件 "
                     f"({folder_size / (1024*1024):.1f} MB)")

    action = "将要删除" if dry_run else "已删除"
    log.info(f"\n{action} {total_hash_deleted} 个重复文件，"
             f"节省 {total_size_saved / (1024*1024):.1f} MB，"
             f"涉及 {affected_folders} 个文件夹")


def preview_duplicates(download_root: str, screen_name: str = ""):
    cleanup_duplicates(download_root, dry_run=True, screen_name=screen_name)
