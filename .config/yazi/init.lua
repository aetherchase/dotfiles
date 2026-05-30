-- Persist per-folder preferences (sort, linemode, show_hidden) across sessions.
-- Plugin: boydaihungst/pref-by-location.yazi
-- Saved prefs live in the plugin's state dir; restored on revisit.
-- See keymap.toml for the bindings that trigger a save.
require("pref-by-location"):setup({})
