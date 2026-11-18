#!/usr/bin/env bash
#
# install-hooks.sh — Git Hooks 交互式安装脚本（方案1：原生 core.hooksPath）
#
# 功能：
#   1. 由使用者输入目标项目目录
#   2. 询问是否将 hook 脚本纳入版本控制
#      - 否：将全部 hook 及依赖文件复制到目标项目的 .git/hooks
#      - 是：在目标项目根目录创建 .githooks，复制文件并配置 core.hooksPath
#
# 用法：
#   bash install-hooks.sh
#   ./install-hooks.sh   （需先 chmod +x install-hooks.sh）

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

# ---------- 源文件清单 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Git 生命周期钩子脚本
HOOK_FILES=(
  post-checkout
  post-commit
  post-merge
  post-rebase
  post-rewrite
  pre-commit
  pre-merge
  pre-push
  pre-rebase
)

# 钩子运行依赖的公共文件
SUPPORT_FILES=(
  git_utils.py
  build-on-hook.py
  build-config
  branch-protection.conf
)

# 克隆后激活脚本（仅入库模式需要，随 .githooks 一起分发）
BOOTSTRAP_FILES=(
  activate-hooks.sh
)

# 基础文件（两种模式都安装）
BASE_FILES=("${HOOK_FILES[@]}" "${SUPPORT_FILES[@]}")
ALL_FILES=("${BASE_FILES[@]}")
EXECUTABLE_FILES=("${HOOK_FILES[@]}" build-on-hook.py)

# 校验源文件齐全（含激活脚本）
for f in "${BASE_FILES[@]}" "${BOOTSTRAP_FILES[@]}"; do
  if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
    error "源文件缺失：$SCRIPT_DIR/$f"
    exit 1
  fi
done

# ---------- 1. 目标项目目录（由使用者输入） ----------
default_target="$(pwd)"
printf '%s请输入目标项目目录（回车默认：%s）：%s' "$BLUE" "$default_target" "$NC"
read -r target_input
target_raw="${target_input:-$default_target}"

# 支持相对路径，统一转成绝对路径
target="$(cd "$target_raw" 2>/dev/null && pwd)" || {
  error "目录不存在：$target_raw"
  exit 1
}

if ! git -C "$target" rev-parse --git-dir >/dev/null 2>&1; then
  error "$target 不是一个 Git 仓库"
  exit 1
fi

# ---------- 2. 询问是否将 hook 脚本纳入版本控制 ----------
printf '%s是否将 hook 脚本纳入版本控制？[y/N]：%s' "$BLUE" "$NC"
read -r versioned_answer
versioned=false
case "${versioned_answer:-}" in
  y | Y | yes | YES) versioned=true ;;
  *) versioned=false ;;
esac

if $versioned; then
  # 入库模式：目标项目根目录下的 .githooks
  dest_dir="$target/.githooks"
  # 额外携带激活脚本，供其他克隆者执行一次使钩子生效
  ALL_FILES+=("${BOOTSTRAP_FILES[@]}")
  EXECUTABLE_FILES+=("${BOOTSTRAP_FILES[@]}")
else
  # 不入库模式：Git 实际的 hooks 目录（兼容 worktree，返回值可能是相对路径）
  hooks_rel="$(git -C "$target" rev-parse --git-path hooks)"
  case "$hooks_rel" in
    /*) dest_dir="$hooks_rel" ;;
    *)  dest_dir="$target/$hooks_rel" ;;
  esac
fi

# ---------- 3. 冲突检测与覆盖确认 ----------
conflicts=()
for f in "${ALL_FILES[@]}"; do
  [[ -e "$dest_dir/$f" ]] && conflicts+=("$f")
done

overwrite=false
if [[ ${#conflicts[@]} -gt 0 ]]; then
  warn "目标目录已存在以下文件：${conflicts[*]}"
  printf '%s是否覆盖已有文件？[y/N]：%s' "$YELLOW" "$NC"
  read -r overwrite_answer
  case "${overwrite_answer:-}" in
    y | Y | yes | YES) overwrite=true ;;
  esac
fi

# ---------- 4. 复制安装 ----------
mkdir -p "$dest_dir"

is_executable() {
  local name="$1"
  for e in "${EXECUTABLE_FILES[@]}"; do
    [[ "$e" == "$name" ]] && return 0
  done
  return 1
}

installed=0
skipped=0
for f in "${ALL_FILES[@]}"; do
  if [[ -e "$dest_dir/$f" && $overwrite == false ]]; then
    warn "跳过（已存在）：$f"
    skipped=$((skipped + 1))
    continue
  fi
  cp -p "$SCRIPT_DIR/$f" "$dest_dir/$f"
  if is_executable "$f"; then
    chmod +x "$dest_dir/$f"
  fi
  installed=$((installed + 1))
done

# ---------- 5. 入库模式配置 core.hooksPath ----------
if $versioned; then
  git -C "$target" config core.hooksPath .githooks
fi

# ---------- 结果汇总 ----------
echo
if $versioned; then
  ok "安装完成：文件已复制到 $dest_dir"
  info "已执行 git config core.hooksPath .githooks"
  info ".githooks 受版本控制，可执行 git add .githooks 提交后随仓库共享"
  info "其他成员克隆后需执行一次：bash .githooks/activate-hooks.sh"
else
  ok "安装完成：文件已复制到 $dest_dir"
  warn "该目录不受版本控制，仅在本机生效"
fi
info "安装文件数：${installed}，跳过：${skipped}"
