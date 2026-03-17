#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共编译脚本：Git 钩子自动编译（Python 3 版本）

功能：
  - 读取编译命令配置文件（build-config）
  - 按顺序执行编译命令
  - 任何命令失败时停止并报错

使用：
  python3 build-on-hook.py <hook-name>
  例如：python3 build-on-hook.py post-checkout

配置文件：
  build-config - 存储编译命令列表（每行一条）
"""

import sys
import subprocess
from pathlib import Path

# 颜色定义
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def log_info(msg):
    print(f"{BLUE}ℹ️  {msg}{NC}")

def log_success(msg):
    print(f"{GREEN}✅ {msg}{NC}")

def log_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{NC}")

def log_error(msg):
    print(f"{RED}❌ {msg}{NC}")

def main():
    # 获取脚本所在目录（即 .git/hooks 目录）
    hooks_dir = Path(__file__).resolve().parent
    config_file = hooks_dir / 'build-config'
    # 获取 hook 名称
    hook_name = sys.argv[1] if len(sys.argv) > 1 else 'unknown'

    # 检查配置文件是否存在
    if not config_file.is_file():
        log_warning(f"编译配置文件不存在: {config_file}")
        log_info(f"跳过编译步骤。请创建 {config_file} 文件来指定编译命令。")
        return 0

    log_info(f"========================== 自动编译开始 (Hook: {hook_name}) ==========================")

    total_commands = 0
    command_index = 0

    # 读取并执行配置文件中的编译命令
    with config_file.open(encoding='utf-8') as f:
        for line in f:
            command = line.strip()
            # 跳过空行和注释行
            if not command or command.startswith('#'):
                continue
            total_commands += 1
            command_index += 1
            # 为了在子 shell 中使 goenv 命令可用，需要先初始化 goenv
            # 如果 goenv 不可用（如非 Go 项目的环境），也不会影响后续命令执行
            full_command = f'eval "$(goenv init -)" 2>/dev/null || true; {command}'
            log_info(f"[{command_index}] 执行命令: {command}")
            try:
                result = subprocess.run(full_command, shell=True, check=True)
                log_success(f"[{command_index}] 命令执行成功")
            except subprocess.CalledProcessError as e:
                log_error(f"[{command_index}] 命令执行失败 (退出码: {e.returncode})")
                log_info(f"========================== 自动编译完成 ==========================")
                log_error(f"{total_commands} 条命令中有 1 条失败，已停止编译。")
                return e.returncode

    print()
    log_info(f"========================== 自动编译完成 ==========================")
    if total_commands == 0:
        log_warning(f"未找到任何编译命令（{config_file} 为空或只包含注释）。")
        return 0
    else:
        log_success(f"{total_commands} 条编译命令全部执行成功！")
        return 0

if __name__ == "__main__":
    sys.exit(main())
