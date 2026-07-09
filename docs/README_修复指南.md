# X/Twitter 下载器 - 修复和维护指南

## 已修复的问题

### 1. 多来源媒体遗漏
- **问题**：之前只从第一个来源（extended_entities）提取媒体，导致 entities 或 note_tweet 中的媒体被遗漏
- **修复**：现在从三个来源全部提取并去重：
  - extended_entities
  - entities  
  - note_tweet
- **文件**：`src/twitter_api.py`

### 2. 纯文本推文丢失
- **问题**：之前 CSV 只保存有媒体的推文，纯文本推文被丢弃
- **修复**：现在纯文本推文也会保存到统一的 CSV 文件中
- **文件**：`src/csv_output.py`

### 3. 重复文件和孤儿文件处理工具
- **工具**：`_fix_single_folder.py`
- **功能**：
  - 删除重复文件（保留哈希命名版本）
  - 将孤儿文件（磁盘有但CSV无）恢复到CSV
  - 删除过期的CSV记录（指向不存在文件）

## 如何使用修复工具处理现有文件夹

### 1. 查看所有有问题的文件夹
```bash
cd f:\x\X-download
python _scan_all.py
```

### 2. 修复单个用户文件夹
```bash
cd f:\x\X-download
python _fix_single_folder.py "文件夹名称"
```
例如：
```bash
python _fix_single_folder.py "看众生@lionman513"
```

## 如何确保未来下载不会遗漏

### 1. 使用最新版本的程序
确保使用已修复的代码重新打包的 EXE

### 2. 定期扫描和修复
建议定期运行 `_scan_all.py` 扫描，发现问题及时修复

### 3. 验证下载完整性
每次下载完成后，可以再次运行扫描确认无新问题

## 文件说明

- `_scan_all.py`：扫描所有用户文件夹，显示问题统计
- `_fix_single_folder.py`：修复单个用户文件夹
- `_fix_single_folder.py` 会自动为每个修复的CSV创建 `.bak` 备份文件

## 问题类型说明

- **孤儿文件**：磁盘上有但CSV中没有记录的文件
- **重复文件**：内容相同但文件名不同的文件（通常一个是数字后缀，一个是哈希后缀）
- **过期记录**：CSV中有记录但磁盘上已不存在的文件
