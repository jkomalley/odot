# VHS demo tape for odot — render from the repo root with: vhs assets/demo.tape
#
# Self-contained: the hidden setup puts this checkout's odot (.venv/bin) first
# on PATH and seeds a throwaway database, so the recording is reproducible.
Output "assets/demo.gif"

Set Shell "zsh"
Set FontSize 16
Set Width 900
Set Height 500
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type 'export PATH="$PWD/.venv/bin:$PATH" ODOT_DB_PATH=/tmp/odot_demo/db.sqlite'
Enter
Type "rm -rf /tmp/odot_demo && odot init-db >/dev/null"
Enter
Type "odot add 'Submit quarterly report' -p high -c work >/dev/null"
Enter
Type "odot add 'Review pull requests' -p medium -c work >/dev/null"
Enter
Type "odot add 'Buy groceries' -p medium -c home >/dev/null"
Enter
Type "odot add 'Call the dentist' -p low -c personal >/dev/null"
Enter
Sleep 2s
Type "clear"
Enter
Sleep 500ms
Show

# Add a task interactively: named priority levels, then pick an existing category
Type "odot add"
Enter
Sleep 800ms
Type "Plan weekend hike"
Sleep 500ms
Enter
Sleep 1s
Down
Sleep 700ms
Enter
Sleep 1.2s
Down
Sleep 700ms
Enter
Sleep 2s

# List by priority, highest first
Type "odot list --sort priority --reverse"
Enter
Sleep 3s

# Search
Type "odot search report"
Enter
Sleep 2.5s

# Complete a task by picking it from a menu
Type "odot done"
Enter
Sleep 2.5s
Enter
Sleep 1.5s

# Delete with confirmation
Type "odot rm 4"
Enter
Sleep 1s
Type "y"
Enter
Sleep 1.5s

# Final state
Type "odot list"
Enter
Sleep 3.5s
