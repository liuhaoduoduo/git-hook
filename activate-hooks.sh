#!/usr/bin/env bash
#
# activate-hooks.sh — 克隆后激活脚本（仅用于 .githooks 入库模式）
#
# 背景：
#   .githooks 目录随仓库纳入版本控制，但 core.hooksPath 配置保存在每个
#   克隆本地的 .git/config 中，不会随仓库分发。因此新成员克隆仓库后，
#   需要执行本脚本一次，使 .githooks 中的钩子真正生效。
#
# 用法：
#   bash .githooks/activate-hooks.sh
#   ./.githooks/activate-hooks.sh
#
# 特性：幂等，可重复执行；已激活时不会重复改写配置。

set -euo pipefail

# ---------- 颜色与输出 ----------
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
NC=$'\033[0m'

info()  { printf '%sℹ️  %s%s\n' "$BLUE" "$1" "$NC"; }
ok()    { printf '%s✅ %s%s\n' "$GREEN" "$1" "$NC"; }
warn()  { printf '%s⚠️  %s%s\n' "$YELLOW" "$1" "$NC"; }
error() { printf '%s❌ %s%s\n' "$RED" "$1" "$NC" >&2; }

# ---------- 定位仓库 ----------
# 本脚本位于 <repo-root>/.githooks/ 目录下
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$(basename "$SCRIPT_DIR")" != ".githooks" ]]; then
  error "本脚本应位于仓库的 .githooks 目录中，当前位置：$SCRIPT_DIR"
  exit 1
fi

if ! git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  error "$REPO_ROOT 不是一个 Git 仓库"
  exit 1
fi

# ---------- 配置 core.hooksPath（幂等） ----------
current_path="$(git -C "$REPO_ROOT" config core.hooksPath || true)"
if [[ "$current_path" == ".githooks" ]]; then
  ok "钩子已处于激活状态（core.hooksPath=.githooks），无需重复配置"
else
  git -C "$REPO_ROOT" config core.hooksPath .githooks
  ok "已配置 core.hooksPath=.githooks"
fi

# ---------- 修复可执行位（clone 通常保留权限位，此处兜底） ----------
fixed=0
for f in "$SCRIPT_DIR"/*; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  # 配置类文件不需要可执行位
  case "$name" in
    build-config | *.conf | *.config) continue ;;
  esac
  if [[ ! -x "$f" ]]; then
    chmod +x "$f"
    fixed=$((fixed + 1))
  fi
done

# ---------- 结果汇总 ----------
echo
info "仓库根目录：$REPO_ROOT"
info "当前 core.hooksPath：$(git -C "$REPO_ROOT" config core.hooksPath)"
if [[ $fixed -gt 0 ]]; then
  warn "已补全 ${fixed} 个文件的可执行权限"
fi
ok "激活完成，.githooks 中的钩子现已生效"
