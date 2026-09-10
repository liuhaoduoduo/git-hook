"""Git hook 脚本共享的公共函数库。"""

import os
import subprocess
import sys
from pathlib import Path

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"



def log_info(msg: str) -> None:
    """输出信息日志（蓝色）"""
    print(f"{BLUE}ℹ️  {msg}{NC}")


def log_success(msg: str) -> None:
    """输出成功日志（绿色）"""
    print(f"{GREEN}✅ {msg}{NC}")


def log_warning(msg: str) -> None:
    """输出警告日志（黄色）"""
    print(f"{YELLOW}⚠️  {msg}{NC}")


def log_error(msg: str) -> None:
    """输出错误日志（红色）"""
    print(f"{RED}❌ {msg}{NC}")

# 通用超时配置（秒）
TIMEOUT_DEFAULT = 60       # 长时间操作的默认超时（编译/测试等）


def get_auto_pull_env_var_name(repo_path: str = "") -> str:
    """
    生成自动拉取标记的环境变量名称。
    
    参数：
      repo_path: Git 仓库路径（可选，不提供时使用当前工作目录）
    
    返回：
      环境变量名称，格式为 "GIT_HOOK_REPO_PATH:AutoPull"（路径分隔符用'.'替代）
    """
    if not repo_path:
        repo_path = os.getcwd()
    
    # 将路径分隔符替换为 '.'
    normalized_path = repo_path.replace(os.sep, '.')
    return f"GIT_HOOK_REPO_{normalized_path}:AutoPull"


def set_auto_pull_flag(repo_path: str = "") -> None:
    """
    设置自动拉取标记（环境变量）。
    
    参数：
      repo_path: Git 仓库路径（可选，不提供时使用当前工作目录）
    """
    env_var_name = get_auto_pull_env_var_name(repo_path)
    os.environ[env_var_name] = "1"


def has_auto_pull_flag(repo_path: str = "") -> bool:
    """
    检查是否设置了自动拉取标记。
    
    参数：
      repo_path: Git 仓库路径（可选，不提供时使用当前工作目录）
    
    返回：
      True 如果环境变量存在，False 否则
    """
    env_var_name = get_auto_pull_env_var_name(repo_path)
    return env_var_name in os.environ


def clear_auto_pull_flag(repo_path: str = "") -> None:
    """
    清除自动拉取标记（删除环境变量）。
    
    参数：
      repo_path: Git 仓库路径（可选，不提供时使用当前工作目录）
    """
    env_var_name = get_auto_pull_env_var_name(repo_path)
    if env_var_name in os.environ:
        del os.environ[env_var_name]


def check_remote_tracking_branch(branch: str) -> bool:
    """
    检查远程追踪分支是否存在。

    参数：
      branch: 分支名（如 'main', 'develop'）

    返回：
      True 远程分支存在，False 远程分支不存在或检查失败
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{branch}"],
            capture_output=True,
            timeout=TIMEOUT_DEFAULT,
            check=False,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def get_git_dir() -> str:
    """返回 Git 仓库目录的路径。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_current_branch() -> str:
    """返回当前检出的分支名称。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def load_protected_branches(config_path: Path) -> set[str]:
    """从配置文件中加载受保护的分支名称。"""
    protected: set[str] = set()

    if not config_path.exists():
        return protected

    try:
        with config_path.open(encoding="utf-8") as fh:
            for line in fh:
                branch = line.strip()
                if not branch or branch.startswith("#"):
                    continue
                protected.add(branch)
    except OSError:
        return protected

    return protected


def ref_to_branch_name(ref: str) -> str:
    """
    将 Git 引用转换为分支名称。

    支持的格式：
      - commit SHA -> 通过 git describe 尝试获取分支名
      - 分支名 -> 直接返回
      - origin/分支名 -> 移除 origin/ 前缀
      - refs/remotes/origin/分支名 -> 移除前缀
    """
    if not ref:
        return ""

    ref = ref.strip()

    # 已经是简单的分支名
    if '/' not in ref:
        return ref

    # origin/branch 或 refs/remotes/origin/branch 格式
    if ref.startswith('origin/'):
        return ref.replace('origin/', '')
    if ref.startswith('refs/remotes/origin/'):
        return ref.replace('refs/remotes/origin/', '')

    # 尝试通过 git describe 转换 commit SHA 为 branch name
    try:
        result = subprocess.run(
            ["git", "describe", "--all", "--exact-match", ref],
            capture_output=True,
            text=True,
            check=True
        )
        described = result.stdout.strip()
        # git describe 返回 "remotes/origin/branch" 格式
        if described.startswith('remotes/origin/'):
            return described.replace('remotes/origin/', '')
        if described.startswith('origin/'):
            return described.replace('origin/', '')
        return described
    except subprocess.CalledProcessError:
        pass

    # 降级：返回原始 ref
    return ref


def check_protected_branch(current_branch: str, target_ref: str, protected_branches: set) -> bool:
    """
    检查受保护分支的操作是否被允许。

    规则：
      - 若当前分支不在保护列表中，允许
      - 若当前分支在保护列表中：
        * 若 target_ref 等于当前分支（纯粹的同名分支或 origin/current_branch），允许
        * 否则禁止（拒绝其他分支的操作）

    参数：
      current_branch: 当前所在分支（如 'main'）
      target_ref: 操作的目标分支（如 'origin/main'、'feature-x' 等）
      protected_branches: 保护分支集合

    返回：
      True 允许，False 禁止
    """
    # 若配置为空或当前分支不在保护列表中，允许
    if not protected_branches or current_branch not in protected_branches:
        return True

    # 当前分支受保护，检查 target_ref 是否来自自身
    # 支持以下 target_ref 格式：main、origin/main、refs/remotes/origin/main
    target_branch = ref_to_branch_name(target_ref)

    return target_branch == current_branch


def abort_with_error(current_branch: str, target_ref: str, protected_branches: set, operation_type: str = "merge") -> int:
    """
    输出详细错误消息，阻止 merge/rebase 操作。

    参数：
      current_branch: 当前分支名
      target_ref: 目标/来源分支
      protected_branches: 保护分支集合
      operation_type: 操作类型，"merge" 或 "rebase"

    返回：
      1（非零退出码，表示操作被拒绝）
    """
    op_name = "Merge" if operation_type == "merge" else "Rebase"
    print()
    print(f"{RED}❌ {op_name} 操作被禁止！{NC}")
    print()
    print(f"{BLUE}当前分支:{NC} {current_branch}")
    print(f"{BLUE}目标分支:{NC} {target_ref}")
    print()

    if protected_branches:
        print(f"{BLUE}原因:{NC} 分支 '{current_branch}' 在保护列表中")
    else:
        print(f"{BLUE}原因:{NC} 所有分支都被保护（branch-protection.conf 为空）")

    print()
    print(f"{BLUE}规则:{NC}")
    print(f"  • 分支 '{current_branch}' 只允许 {operation_type} 自身（git {operation_type} origin/{current_branch}）")
    print(f"  • 不允许 {operation_type} 其他分支（如 '{target_ref}'）")
    print()
    print(f"{YELLOW}💡 提示:{NC} 如需修改此规则，请编辑 .git/hooks/branch-protection.conf")
    print()

    return 1


def validate_branch_operation(current_branch: str, target_ref: str, operation_type: str, config_path: Path | None = None) -> bool:
    """
    验证分支操作是否被允许（统一接口）。

    参数：
      current_branch: 当前分支
      target_ref: 目标/来源分支
      operation_type: 操作类型，"merge" 或 "rebase"
      config_path: 配置文件路径（可选，默认为自动查找）

    返回：
      True 允许，False 禁止（已输出错误消息）
    """
    if not config_path:
        git_dir = get_git_dir()
        if not git_dir:
            print(f"{RED}❌ 无法获取 Git 目录{NC}", file=sys.stderr)
            return False
        config_path = Path(git_dir) / "hooks" / "branch-protection.conf"

    protected_branches = load_protected_branches(config_path)

    if not check_protected_branch(current_branch, target_ref, protected_branches):
        _ = abort_with_error(current_branch, target_ref, protected_branches, operation_type)
        return False

    return True


def run_build_script(operation_type: str, git_dir: str | None = None) -> int:
    """
    执行编译脚本。

    参数：
      operation_type: 操作类型（"pre-push", "post-checkout" 等）
      git_dir: Git 目录路径（可选，不提供时自动查找）

    返回：
      0 成功或脚本不存在
      非0 执行失败的退出码
    """
    if not git_dir:
        git_dir = get_git_dir()
        if not git_dir:
            print(f"{RED}❌ 无法获取 Git 目录{NC}", file=sys.stderr)
            return 1

    build_script = Path(git_dir) / "hooks" / "build-on-hook.py"
    if not build_script.exists():
        return 0

    try:
        result = subprocess.run(
            ["python3", str(build_script), operation_type],
            check=False
        )
        return result.returncode
    except Exception as e:
        print(f"{RED}❌ 编译脚本执行失败: {e}{NC}", file=sys.stderr)
        return 1

def prompt_push() -> int:
    """编译成功后询问用户是否执行 git push"""
    try:
        # Git hook 中 stdin 被重定向，需要通过 /dev/tty 读取用户输入
        with open('/dev/tty', 'r') as tty:
            print(f"\n{GREEN}✅ 编译全部成功！{NC}")
            print(f"{YELLOW}是否执行 git push？[y/N]: {NC}", end='', flush=True)
            answer = tty.readline().strip().lower()
        if answer in ('y', 'yes'):
            print(f"{BLUE}ℹ️  正在执行 git push ...{NC}")
            result = subprocess.run(["git", "push"], capture_output=False)

            if result.returncode == 0:
                print(f"{GREEN}✅ Push 成功！{NC}")
            else:
                print(f"{RED}❌ Push 失败 (退出码: {result.returncode}){NC}")

            return result.returncode
        else:
            print(f"{BLUE}ℹ️  已跳过 push。{NC}")
            return 0
    except (OSError, IOError):
        return 1
