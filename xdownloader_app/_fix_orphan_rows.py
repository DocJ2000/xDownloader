import csv
import os

ROOT = os.environ.get('XDL_DOWNLOAD_ROOT', os.path.join(os.getcwd(), 'downloads'))

def fix_orphan_rows():
    fixed_count = 0
    total_fixed_files = 0

    for folder_name in os.listdir(ROOT):
        if '@' not in folder_name:
            continue
        folder_path = os.path.join(ROOT, folder_name)
        handle = folder_name.rsplit('@', 1)[1]
        csv_path = os.path.join(folder_path, f'{handle}.csv')
        if not os.path.isfile(csv_path):
            continue

        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception:
            continue

        if len(rows) < 5:
            continue

        modified = False
        for i in range(4, len(rows)):
            row = rows[i]
            if len(row) < 8:
                continue
            media_type_col = row[4].strip() if len(row) > 4 else ''
            local_file_col = row[6].strip() if len(row) > 6 else ''
            content_col = row[7].strip() if len(row) > 7 else ''

            if (content_col == 'photo' or content_col == 'video') and not media_type_col:
                if local_file_col and os.path.isfile(os.path.join(folder_path, local_file_col)):
                    new_row = list(row)
                    while len(new_row) < 11:
                        new_row.append('')
                    new_row[4] = 'Video' if content_col == 'video' else 'Image'
                    new_row[5] = ''
                    new_row[6] = local_file_col
                    new_row[7] = f'[Recovered file: {local_file_col}]'
                    if len(new_row) < 9 or not new_row[8]:
                        new_row[8] = '0'
                    if len(new_row) < 10 or not new_row[9]:
                        new_row[9] = '0'
                    if len(new_row) < 11 or not new_row[10]:
                        new_row[10] = '0'
                    rows[i] = new_row
                    modified = True
                    fixed_count += 1

        if modified:
            backup = csv_path + '.bak2'
            try:
                with open(backup, 'w', encoding='utf-8-sig', newline='') as f:
                    csv.writer(f).writerows(rows)
                os.replace(backup, csv_path)
            except OSError:
                pass
            total_fixed_files += 1

    print(f"Fixed {fixed_count} orphan rows across {total_fixed_files} files")

if __name__ == '__main__':
    fix_orphan_rows()
