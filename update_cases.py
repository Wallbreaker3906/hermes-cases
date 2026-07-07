#!/usr/bin/env python3
"""
Hermes 案例网页更新脚本

用法1（LLM 生成 HTML 后调用）：
  python3 update_cases.py --html-file /tmp/new_day.html

用法2（直接从 daily-cases.md 读取，LLM 已生成好 HTML 片段）：
  python3 update_cases.py --html '<div class="day-section"...'

此脚本负责：
  1. 读取 LLM 生成的新 Day HTML 片段
  2. 插入到 index.html 的 DAILY_CASES_END 之前
  3. 自动更新累计天数/案例数/行业数
  4. Git commit + push
"""

import re
import sys
import subprocess
import argparse
import os
from datetime import datetime

REPO_DIR = os.path.expanduser('~/.hermes/hermes-cases')
INDEX_HTML = os.path.join(REPO_DIR, 'index.html')
SSH_KEY = os.path.expanduser('~/.ssh/id_ed25519_hermes')


def git_cmd(*args):
    """Run git command in repo dir."""
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = f'ssh -i {SSH_KEY} -o StrictHostKeyChecking=no'
    return subprocess.run(
        ['git'] + list(args),
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        env=env
    )


def extract_day_number(html_block):
    """Extract Day number from HTML block."""
    m = re.search(r'Day (\d+)', html_block)
    return int(m.group(1)) if m else None


def extract_industries(html_block):
    """Extract industry tags from HTML block."""
    return set(re.findall(r'class="tag industry">([^<]+)', html_block))


def main():
    parser = argparse.ArgumentParser(description='更新 Hermes 案例网页')
    parser.add_argument('--html-file', help='包含新 Day HTML 片段的文件路径')
    parser.add_argument('--html', help='新 Day HTML 片段（直接传入）')
    parser.add_argument('--dry-run', action='store_true', help='只预览不写入')
    args = parser.parse_args()

    # 获取 HTML 片段
    if args.html_file:
        with open(args.html_file, 'r') as f:
            new_html = f.read()
    elif args.html:
        new_html = args.html
    else:
        print("错误：需要 --html-file 或 --html 参数", file=sys.stderr)
        sys.exit(1)

    # 提取数据
    day_num = extract_day_number(new_html)
    new_industries = extract_industries(new_html)
    new_case_count = len(re.findall(r'class="case-card"', new_html))

    if not day_num:
        print("错误：无法从 HTML 中提取 Day 编号", file=sys.stderr)
        sys.exit(1)

    print(f"📋 检测到: Day {day_num}, {new_case_count} 个案例")
    print(f"🏭 新行业: {', '.join(sorted(new_industries))}")

    # 读取 index.html
    with open(INDEX_HTML, 'r') as f:
        html = f.read()

    # 获取当前统计
    days_match = re.search(r'累计 <strong id="days-count">(\d+)</strong>', html)
    cases_match = re.search(r'累计 <strong>(\d+)</strong> 个案例', html)
    
    old_days = int(days_match.group(1)) if days_match else 0
    old_cases = int(cases_match.group(1)) if cases_match else 0

    # 获取所有已有行业
    existing_industries = set(re.findall(r'class="tag industry">([^<]+)', html))
    all_industries = existing_industries | new_industries

    new_days = day_num  # 直接使用 HTML 中的 Day 编号
    new_cases = old_cases + new_case_count
    new_ind_count = len(all_industries)

    print(f"📊 更新前: {old_days}天 / {old_cases}案例 / {len(existing_industries)}行业")
    print(f"📊 更新后: {new_days}天 / {new_cases}案例 / {new_ind_count}行业")

    if args.dry_run:
        print("\n🔍 [Dry Run] 预览 HTML 片段（前500字）:")
        print(new_html[:500])
        sys.exit(0)

    # 插入 HTML
    insert_point = html.find('<!-- DAILY_CASES_END -->')
    if insert_point == -1:
        print("错误：找不到 DAILY_CASES_END 标记", file=sys.stderr)
        sys.exit(1)

    # 确保 new_html 以换行开头，以换行结尾
    new_html = new_html.strip()
    html = html[:insert_point] + '\n' + new_html + '\n' + html[insert_point:]

    # 更新统计
    html = re.sub(
        r'累计 <strong id="days-count">\d+</strong>',
        f'累计 <strong id="days-count">{new_days}</strong>',
        html
    )
    html = re.sub(
        r'累计 <strong>\d+</strong> 个案例',
        f'累计 <strong>{new_cases}</strong> 个案例',
        html
    )
    html = re.sub(
        r'覆盖 <strong id="industry-count">\d+</strong>',
        f'覆盖 <strong id="industry-count">{new_ind_count}</strong>',
        html
    )

    # 写回
    with open(INDEX_HTML, 'w') as f:
        f.write(html)

    print(f"✅ index.html 已更新 ({len(html)} bytes)")

    # Git 操作
    today = datetime.now().strftime('%Y-%m-%d')
    industries_str = ' | '.join(sorted(new_industries))

    # Add SSH key
    subprocess.run(['ssh-add', SSH_KEY], capture_output=True)

    # Commit
    result = git_cmd('add', 'index.html')
    if result.returncode != 0:
        print(f"❌ git add 失败: {result.stderr}")
        sys.exit(1)

    result = git_cmd('commit', '-m', f'📅 Day {day_num}: {industries_str}')
    if result.returncode != 0:
        print(f"❌ git commit 失败: {result.stderr}")
        sys.exit(1)

    print(f"📦 {result.stdout.strip()}")

    # Push
    result = git_cmd('push', 'origin', 'main')
    if result.returncode != 0:
        print(f"❌ git push 失败: {result.stderr}")
        sys.exit(1)

    print(f"🚀 {result.stdout.strip()}")
    print(f"\n🔗 https://wallbreaker3906.github.io/hermes-cases/")


if __name__ == '__main__':
    main()
