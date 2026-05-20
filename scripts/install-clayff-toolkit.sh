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
install_extras="[gui]"
update_shell_rc=1

while (($#)); do
  case "$1" in
    --no-gui)
      install_extras=""
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

mkdir -p "$bin_dir"
"$python_bin" -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install -e "$repo_root$install_extras"

launcher_path="$bin_dir/clayff-toolkit"
cat >"$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$venv_dir/bin/python" -m clayff_toolkit "\$@"
EOF
chmod +x "$launcher_path"

if ((update_shell_rc)); then
  begin_marker="# >>> ClayFF-Toolkit user command path >>>"
  end_marker="# <<< ClayFF-Toolkit user command path <<<"

  for rc_file in "$HOME/.bashrc" "$HOME/.profile"; do
    touch "$rc_file"
    tmp_rc="$(mktemp)"
    awk -v begin="$begin_marker" -v end="$end_marker" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$rc_file" >"$tmp_rc"
    {
      cat "$tmp_rc"
      printf '\n%s\n' "$begin_marker"
      printf 'export PATH="%s:$PATH"\n' "$bin_dir"
      printf '%s\n' "$end_marker"
    } >"$rc_file"
    rm -f "$tmp_rc"
  done
fi

printf 'Installed ClayFF-Toolkit launcher: %s\n' "$launcher_path"
printf 'Verify with: clayff-toolkit --help\n'
if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
  printf 'Open a new terminal or run: export PATH="%s:$PATH"\n' "$bin_dir"
fi
