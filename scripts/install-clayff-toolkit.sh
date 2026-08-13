#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/install-clayff-toolkit.sh [options]

Install ClayFF-Toolkit as a persistent user command.

Options:
  --no-gui          Install only CLI dependencies, without GUI extras.
  --bin-dir DIR     Install the clayff-toolkit launcher into DIR.
                   Default: $HOME/.local/bin
  --venv DIR        Create or reuse the virtual environment at DIR.
                   Default: <repo>/.venv
  --desktop-dir DIR Install the Linux desktop entry into DIR.
                   Default: $HOME/.local/share/applications
  --no-shell-rc     Do not update Bash startup files with the bin directory.
  -h, --help        Show this help message.

Environment:
  PYTHON            Python executable used to create the virtual environment.
                   Default: python3
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

python_bin="${PYTHON:-python3}"
venv_dir="${CLAYFF_TOOLKIT_VENV:-$repo_root/.venv}"
bin_dir="${CLAYFF_TOOLKIT_BIN_DIR:-$HOME/.local/bin}"
desktop_dir="${CLAYFF_TOOLKIT_DESKTOP_DIR:-$HOME/.local/share/applications}"
install_gui=1
update_shell_rc=1
python_args=()

while (($#)); do
  case "$1" in
    --no-gui)
      install_gui=0
      shift
      ;;
    --bin-dir)
      (($# >= 2)) || die "--bin-dir requires a directory"
      bin_dir="$2"
      shift 2
      ;;
    --venv)
      (($# >= 2)) || die "--venv requires a directory"
      venv_dir="$2"
      shift 2
      ;;
    --desktop-dir)
      (($# >= 2)) || die "--desktop-dir requires a directory"
      desktop_dir="$2"
      shift 2
      ;;
    --no-shell-rc)
      update_shell_rc=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

command -v "$python_bin" >/dev/null 2>&1 || die "Python executable not found: $python_bin"

if ((install_gui == 0)); then
  python_args+=(--no-gui)
fi
if ((update_shell_rc == 0)); then
  python_args+=(--no-path-update)
fi

"$python_bin" "$script_dir/install_clayff_toolkit.py" \
  --platform posix \
  --repo-root "$repo_root" \
  --python "$python_bin" \
  --venv "$venv_dir" \
  --bin-dir "$bin_dir" \
  --desktop-dir "$desktop_dir" \
  --shell-rc "$HOME/.bashrc" \
  --shell-rc "$HOME/.profile" \
  "${python_args[@]}"
