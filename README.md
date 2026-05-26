# dotfiles

Personal system configuration for Arch Linux + Omarchy + Hyprland.

## Install

```bash
git clone <repo-url> ~/dotfiles
cd ~/dotfiles
stow --target=$HOME .
```

## Structure

```
dotfiles/
  .config/
    hypr/
      bindings.conf   # keybindings (custom apps, lang switch)
      input.conf      # keyboard layouts, mouse accel
      monitors.conf   # display scaling
```

## Adding new configs

```bash
mkdir -p ~/dotfiles/.config/<app>
mv ~/.config/<app>/config ~/dotfiles/.config/<app>/
cd ~/dotfiles && stow --target=$HOME .
git add . && git commit -m "add <app> config"
```
