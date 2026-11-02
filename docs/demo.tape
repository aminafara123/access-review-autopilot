# Renders docs/demo.gif with charmbracelet/vhs (needs vhs, ttyd and ffmpeg on PATH).
# Run from the repo root, with the deps installed in .venv:  vhs docs/demo.tape
# Follows DEMO.md: raw IAM export -> one command -> reviewer worksheet + audit summary -> offline tests.
Output docs/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 700
Set Padding 24
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 40ms

Hide
Type "VIRTUAL_ENV_DISABLE_PROMPT=1 source .venv/bin/activate"
Enter
Wait@120s
Type "rm -rf out"
Enter
Wait@120s
Type "clear"
Enter
Wait@120s
Show
Sleep 500ms

Type "cut -d, -f1,3,5,6,9 access_review/data/sample_users.csv | column -s, -t | head -12"
Sleep 400ms
Enter
Wait@120s
Sleep 3s

Type "access-review --as-of 2026-10-14"
Sleep 400ms
Enter
Wait@120s
Sleep 3s

Hide
Type "clear"
Enter
Sleep 200ms
Show
Type "cut -d, -f1,4-6 out/access_review_worksheet.csv | column -s, -t | head -8"
Sleep 400ms
Enter
Wait@120s
Sleep 3.5s

Hide
Type "clear"
Enter
Sleep 200ms
Show
Type "sed -n '1,20p' out/access_review_summary.md"
Sleep 400ms
Enter
Wait@120s
Sleep 4s

Type "pytest -q"
Sleep 400ms
Enter
Wait@120s
Sleep 2.5s

Sleep 1s
