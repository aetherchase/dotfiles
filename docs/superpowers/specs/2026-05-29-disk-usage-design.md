# Disk Usage Analysis & Cleanup Tool

**Date**: 2026-05-29
**Status**: Approved

## Problem

Root btrfs partition (129G) filling unexpectedly. Known suspects: snapper timeline snapshots accumulating silently, pacman cache, systemd journal, home directory growth.

## Solution

Single `disk` bash script at `~/.local/bin/disk`, stowed via dotfiles.

## Usage

```
disk analyze          # ranked breakdown of disk hogs
disk clean            # interactive menu, confirm each action
disk clean --dry-run  # show what would be freed, touch nothing
```

## Architecture

### `analyze` subcommand

Prints in order:
1. `df -h /` summary
2. Per-category sizes: snapper snapshots, pacman cache, journal, `~/.cache`, `~/Downloads`
3. Top 10 largest dirs in `~` via `du`
4. btrfs subvolume list + allocated vs used (`btrfs filesystem usage /`)

### `clean` subcommand

Four modules run sequentially. Each prints what it will do, asks `y/N`, then acts.

| Module | Action | Command |
|--------|--------|---------|
| snapper | delete all snapshots except 3 newest | `snapper delete <ids>` |
| pacman cache | keep 2 versions per package | `paccache -rk2` |
| journal | vacuum to 200M | `journalctl --vacuum-size=200M` |
| home cache | show `~/.cache` subdirs by size as numbered list, user enters numbers to delete | `rm -rf` per selection |

`--dry-run` flag replaces all destructive calls with `echo` equivalents, printing what would run.

### Sudo handling

Script calls `sudo -v` upfront (refreshes ticket / prompts once). Snapper, paccache, and journal vacuum all require sudo. Home cache cleanup runs as current user.

## File location

```
dotfiles/
  .local/
    bin/
      disk        # the script
```

Stowed to `~/.local/bin/disk` via `./apply.sh`.

## Dependencies

- `snapper` (already installed)
- `pacman-contrib` (provides `paccache`)
- `btrfs-progs` (already installed)
- `sudo`

## Non-goals

- No systemd timer / automation
- No ncdu integration
- No Docker cleanup (Docker data on separate partition `/var/lib/docker`)
