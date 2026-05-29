# Disk Usage Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `disk` — a bash script that analyzes disk usage and interactively cleans known hogs (snapper snapshots, pacman cache, journal, home cache) on this Arch Linux btrfs system.

**Architecture:** Single bash script with `analyze` and `clean [--dry-run]` subcommands. Four clean modules run sequentially, each confirming before acting. `--dry-run` echoes commands instead of running them. Stowed via dotfiles to `~/.local/bin/disk`.

**Tech Stack:** Bash 5, snapper, paccache (pacman-contrib), journalctl, btrfs-progs, GNU coreutils

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `.local/bin/disk` | Create | Main script — all subcommands |
| `.stow-local-ignore` | No change | `.local` not ignored — verified |

---

### Task 1: Script skeleton with arg parsing

**Files:**
- Create: `.local/bin/disk`

- [ ] **Step 1: Create the script file**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT=$(basename "$0")

usage() {
  cat <<EOF
Usage: $SCRIPT <subcommand> [options]

Subcommands:
  analyze          Show disk usage breakdown
  clean            Interactively clean disk hogs
  clean --dry-run  Show what clean would do without making changes
EOF
  exit 1
}

cmd_analyze() {
  echo "analyze: not yet implemented"
  exit 1
}

cmd_clean() {
  echo "clean: not yet implemented"
  exit 1
}

[[ $# -eq 0 ]] && usage

CMD="$1"
shift

case "$CMD" in
  analyze) cmd_analyze "$@" ;;
  clean)   cmd_clean "$@" ;;
  *)       usage ;;
esac
```

- [ ] **Step 2: Make executable and stow**

```bash
chmod +x .local/bin/disk
cd ~/dotfiles && ./apply.sh
```

- [ ] **Step 3: Verify skeleton**

```bash
disk
# Expected: usage message, exits 1

disk analyze
# Expected: "analyze: not yet implemented", exits 1

disk foo
# Expected: usage message, exits 1
```

- [ ] **Step 4: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add script skeleton with arg parsing"
```

---

### Task 2: Implement `analyze` subcommand

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Replace `cmd_analyze` with full implementation**

```bash
cmd_analyze() {
  local bold='\033[1m' reset='\033[0m'

  echo -e "\n${bold}=== Disk Overview ===${reset}"
  df -h /

  echo -e "\n${bold}=== Known Hogs ===${reset}"

  local snap_count
  snap_count=$(sudo snapper list 2>/dev/null | tail -n +3 | grep -c . || echo "0")
  printf "Snapper snapshots:  %s\n" "$snap_count"

  local pkg_cache
  pkg_cache=$(sudo du -sh /var/cache/pacman/pkg/ 2>/dev/null | cut -f1 || echo "unknown")
  printf "Pacman cache:       %s\n" "$pkg_cache"

  local journal_line
  journal_line=$(journalctl --disk-usage 2>/dev/null | grep -oP 'take up \K[^\.]+' || echo "unknown")
  printf "Systemd journal:    %s\n" "$journal_line"

  local home_cache
  home_cache=$(du -sh ~/.cache 2>/dev/null | cut -f1 || echo "unknown")
  printf "~/.cache:           %s\n" "$home_cache"

  local downloads
  downloads=$(du -sh ~/Downloads 2>/dev/null | cut -f1 || echo "(not found)")
  printf "~/Downloads:        %s\n" "$downloads"

  echo -e "\n${bold}=== Top 10 Dirs in ~ ===${reset}"
  du -sh ~/.[^.]* ~/* 2>/dev/null | sort -rh | head -10

  echo -e "\n${bold}=== btrfs Subvolumes ===${reset}"
  sudo btrfs subvolume list / 2>/dev/null || echo "(requires sudo)"

  echo -e "\n${bold}=== btrfs Filesystem Usage ===${reset}"
  sudo btrfs filesystem usage / 2>/dev/null || echo "(requires sudo)"
}
```

- [ ] **Step 2: Run and verify**

```bash
disk analyze
# Expected: all sections print without unhandled errors
# Sudo prompt appears for btrfs commands
```

- [ ] **Step 3: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): implement analyze subcommand"
```

---

### Task 3: `clean` scaffolding — sudo, dry-run, helpers

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Add helper functions above `cmd_clean` (before the case statement)**

```bash
# Ask y/N — returns 0 for yes, 1 for no
confirm() {
  local prompt="$1"
  read -r -p "$prompt [y/N] " ans
  [[ "${ans,,}" == "y" ]]
}

# dry_run=true: echo the command. Otherwise: run it.
run_cmd() {
  local dry_run="$1"
  shift
  if [[ "$dry_run" == "true" ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

module_snapper()    { echo "(snapper module not yet implemented)"; }
module_pacman()     { echo "(pacman module not yet implemented)"; }
module_journal()    { echo "(journal module not yet implemented)"; }
module_home_cache() { echo "(home cache module not yet implemented)"; }
```

- [ ] **Step 2: Replace `cmd_clean` stub**

```bash
cmd_clean() {
  local dry_run=false
  [[ "${1:-}" == "--dry-run" ]] && dry_run=true

  local yellow='\033[33m' bold='\033[1m' reset='\033[0m'

  if $dry_run; then
    echo -e "${yellow}DRY RUN — no changes will be made${reset}\n"
  else
    echo "Checking sudo access..."
    sudo -v || { echo "sudo required. Exiting."; exit 1; }
  fi

  module_snapper    "$dry_run"
  module_pacman     "$dry_run"
  module_journal    "$dry_run"
  module_home_cache "$dry_run"

  echo -e "\n${bold}Done.${reset}"
}
```

- [ ] **Step 3: Verify scaffolding**

```bash
disk clean --dry-run
# Expected: "DRY RUN" header, then stub messages for each module, no sudo prompt

disk clean
# Expected: sudo prompt, then stub messages
```

- [ ] **Step 4: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add clean scaffolding with dry-run and confirm helpers"
```

---

### Task 4: Snapper module

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Replace `module_snapper` stub**

```bash
module_snapper() {
  local dry_run="$1"
  local bold='\033[1m' reset='\033[0m'

  echo -e "\n${bold}--- Snapper Snapshots ---${reset}"

  local -a snap_nums
  mapfile -t snap_nums < <(sudo snapper list --columns number 2>/dev/null \
    | tail -n +2 \
    | tr -d ' ' \
    | grep -v '^0$' \
    | grep -v '^$')

  local total="${#snap_nums[@]}"

  if [[ $total -eq 0 ]]; then
    echo "No snapshots found."
    return
  fi

  local keep=3
  echo "Found $total snapshot(s). Keeping $keep newest."

  if [[ $total -le $keep ]]; then
    echo "Nothing to delete ($total ≤ $keep)."
    return
  fi

  local -a to_delete=("${snap_nums[@]:0:$((total - keep))}")
  echo "Will delete: ${to_delete[*]}"

  confirm "Delete ${#to_delete[@]} snapshot(s)?" || { echo "Skipped."; return; }

  for num in "${to_delete[@]}"; do
    run_cmd "$dry_run" sudo snapper delete "$num"
  done
  echo "Done."
}
```

- [ ] **Step 2: Test dry-run**

```bash
disk clean --dry-run
# Expected: "Will delete: <ids>" then "[dry-run] sudo snapper delete <N>" per snapshot
```

- [ ] **Step 3: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add snapper clean module"
```

---

### Task 5: Pacman cache module

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Ensure paccache is available**

```bash
pacman -Q pacman-contrib 2>/dev/null || echo "Need to install: sudo pacman -S pacman-contrib"
# Install if missing before proceeding
```

- [ ] **Step 2: Replace `module_pacman` stub**

```bash
module_pacman() {
  local dry_run="$1"
  local bold='\033[1m' reset='\033[0m'

  echo -e "\n${bold}--- Pacman Cache ---${reset}"

  if ! command -v paccache &>/dev/null; then
    echo "paccache not found — install pacman-contrib to enable this module."
    return
  fi

  echo "Preview (keeping 2 versions per package):"
  sudo paccache -dk2 2>/dev/null | tail -5

  confirm "Run paccache -rk2?" || { echo "Skipped."; return; }

  run_cmd "$dry_run" sudo paccache -rk2
}
```

- [ ] **Step 3: Test dry-run**

```bash
disk clean --dry-run
# Expected: paccache preview lines, then "[dry-run] sudo paccache -rk2"
```

- [ ] **Step 4: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add pacman cache clean module"
```

---

### Task 6: Journal module

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Replace `module_journal` stub**

```bash
module_journal() {
  local dry_run="$1"
  local bold='\033[1m' reset='\033[0m'

  echo -e "\n${bold}--- Systemd Journal ---${reset}"

  local current
  current=$(journalctl --disk-usage 2>/dev/null \
    | grep -oP 'take up \K[^\.]+' || echo "unknown")
  echo "Current size: $current"
  echo "Target:       200M"

  confirm "Vacuum journal to 200M?" || { echo "Skipped."; return; }

  run_cmd "$dry_run" sudo journalctl --vacuum-size=200M
}
```

- [ ] **Step 2: Test dry-run**

```bash
disk clean --dry-run
# Expected: "Current size: 507.9M", "Target: 200M", then "[dry-run] sudo journalctl --vacuum-size=200M"
```

- [ ] **Step 3: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add journal clean module"
```

---

### Task 7: Home cache module

**Files:**
- Modify: `.local/bin/disk`

- [ ] **Step 1: Replace `module_home_cache` stub**

```bash
module_home_cache() {
  local dry_run="$1"
  local bold='\033[1m' reset='\033[0m'

  echo -e "\n${bold}--- Home Cache (~/.cache) ---${reset}"

  local total
  total=$(du -sh ~/.cache 2>/dev/null | cut -f1 || echo "unknown")
  echo "Total ~/.cache: $total"
  echo ""

  local -a dirs sizes
  while IFS=$'\t' read -r size dir; do
    sizes+=("$size")
    dirs+=("$dir")
  done < <(du -sh ~/.cache/*/ 2>/dev/null | sort -rh | head -20)

  local count="${#dirs[@]}"

  if [[ $count -eq 0 ]]; then
    echo "No subdirectories found."
    return
  fi

  for i in "${!dirs[@]}"; do
    printf "  %2d) %-8s %s\n" "$((i+1))" "${sizes[$i]}" "${dirs[$i]}"
  done

  echo ""
  read -r -p "Numbers to delete (space-separated), or Enter to skip: " input
  [[ -z "$input" ]] && { echo "Skipped."; return; }

  for n in $input; do
    local idx=$((n - 1))
    if [[ $idx -lt 0 || $idx -ge $count ]]; then
      echo "Invalid: $n — skipping"
      continue
    fi
    local target="${dirs[$idx]}"
    echo "Deleting: $target"
    run_cmd "$dry_run" rm -rf "$target"
  done
  echo "Done."
}
```

- [ ] **Step 2: Test dry-run**

```bash
disk clean --dry-run
# Enter some numbers when prompted
# Expected: "[dry-run] rm -rf ~/.cache/<subdir>" for each selected
```

- [ ] **Step 3: Commit**

```bash
git add .local/bin/disk
git commit -m "feat(disk): add home cache clean module"
```

---

### Task 8: Integration verify

**Files:**
- Verify symlink via stow

- [ ] **Step 1: Confirm symlink is live**

```bash
ls -la ~/.local/bin/disk
# Expected: lrwxrwxrwx ... -> /home/keroqq/dotfiles/.local/bin/disk
```

- [ ] **Step 2: Full end-to-end dry-run (safe — no changes made)**

```bash
disk analyze
disk clean --dry-run
# Walk through all modules, enter numbers at the home cache prompt
# Verify all 4 modules show [dry-run] commands
```

- [ ] **Step 3: Verify PATH**

```bash
which disk
# Expected: /home/keroqq/.local/bin/disk
```

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat(disk): complete disk usage analysis and cleanup tool"
```
