#!/usr/bin/env bash
# Kaomoji picker — pick a Japanese-style text emoticon from a Walker dmenu list
# and copy it to the clipboard. Bound to SUPER CTRL K (see bindings.conf).
# Sibling to Omarchy's unicode emoji picker (SUPER CTRL E = walker -m symbols),
# which only does 😀-style glyphs, not text emoticons.
#
# Why --index: `walker --dmenu` returns the chosen line verbatim, so the visible
# search keywords would land on the clipboard along with the kaomoji. --index
# returns the row number instead, so we copy the clean kaomoji value by index
# while keeping the keywords searchable in the list.
#
# Data format below: <kaomoji><TAB><search keywords>, one per line, in a quoted
# heredoc (<<'KAOMOJI') so backslashes / $ / parens are all literal — no escaping.
# The TAB is the field separator (kaomoji never contain a literal tab); keep the
# separators as real tab characters. Keywords are search-only, never copied.
set -euo pipefail

display=()
values=()
while IFS=$'\t' read -r kao kw; do
  [[ -z $kao ]] && continue
  values+=("$kao")
  display+=("$kao   $kw")
done <<'KAOMOJI'
¯\_(ツ)_/¯	shrug whatever dunno idk meh
ʕ•ᴥ•ʔ	bear cute teddy
(╯°□°)╯︵ ┻━┻	tableflip rage flip angry table
┬─┬ ノ( ゜-゜ノ)	unflip calm putback table fix
( ͡° ͜ʖ ͡°)	lenny smug suggestive face
(◕‿◕)	happy smile cute
(◠‿◠)	smile content happy
(╥﹏╥)	cry sob sad tears
(ಥ﹏ಥ)	cry sob crying tears
(っ◔◡◔)っ ♥	hug love give heart
(づ｡◕‿‿◕｡)づ	hug cuddle embrace
( •_•)>⌐■-■	deal sunglasses cool put on
(⌐■_■)	cool sunglasses deal with it
ಠ_ಠ	disapprove stare look judging
ಠ_ಥ	disappointed sad disapprove
(ノಠ益ಠ)ノ	angry rage furious mad
(ง'̀-'́)ง	fight fists ready determined
(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧	excited magic sparkle yay celebrate
ヽ(´▽`)/	cheer happy excited yay
(づ￣ ³￣)づ	kiss love smooch
(｡♥‿♥｡)	love inlove hearts adore
(✿◠‿◠)	flower smile cute happy
(¬‿¬)	smug smirk sly side eye
(¬_¬)	annoyed unamused side eye
(╬ Ò﹏Ó)	furious rage seething angry
(ㆆ_ㆆ)	suspicious skeptical doubt
(°ロ°)	shock surprised gasp
(⊙_⊙)	stare wide eyes surprised
(╯︵╰,)	sad disappointed down
(；一_一)	skeptical unimpressed doubtful
(´･_･`)	worried unsure concerned
(￣ヘ￣)	annoyed grumpy unamused
(•́﹏•̀)	pleading sad nervous
(っ˘ω˘ς )	sleepy tired cozy
(－_－) zzz	sleep tired zzz sleepy
(ᵔᴥᵔ)	dog cute happy pet
(=^･ω･^=)	cat meow kitty cute
(=｀ω´=)	cat angry kitty
ฅ^•ﻌ•^ฅ	cat paws kitty cute
><(((°>	fish swim ocean
ʕノ•ᴥ•ʔノ ︵ ┻━┻	bearflip tableflip bear rage
\(^o^)/	yay hooray excited cheer
\(°□°)/	panic shock surprised aaah
(•_•)	blank stare neutral nothing
(¦3[▓▓]	dead tired sleep flop exhausted
(˘･_･˘)	shy nervous unsure
(◍•ᴗ•◍)	adorable happy cute blush
(*≧ω≦)	excited squee happy delight
(╯✧▽✧)╯	starstruck excited amazed wow
(ノ_<。)	crying sob hide ashamed
(ง •̀_•́)ง	determined ready fight pumped
(•ω•)	cute neutral content
( ˘ ³˘)♥	kiss love heart
(ᴗ_ᴗ)	bow sorry apologize thanks
(°°)~	tadpole misc swim
(ノ°ο°)ノ	yell shout panic
(；´Д｀)	exhausted stressed phew overwhelmed
( ✜︵✜ )	confused dizzy what
〴⋋_⋌〵	angry mad furious
(っ▀¯▀)つ	cool creep sneaky
(☞ﾟヮﾟ)☞	point you finger guns
~(˘▾˘~)	dance party happy groove
KAOMOJI

idx=$(printf '%s\n' "${display[@]}" | omarchy-launch-walker --dmenu --index -p "Kaomoji…" 2>/dev/null) || true

# Esc / no selection → walker prints nothing (or non-numeric). Bail silently.
[[ -z ${idx:-} || ! $idx =~ ^[0-9]+$ ]] && exit 0

kao="${values[$idx]}"
printf '%s' "$kao" | wl-copy
omarchy swayosd client --custom-message "Copied  $kao" --custom-icon edit-copy-symbolic
