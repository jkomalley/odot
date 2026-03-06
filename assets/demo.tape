# VHS demo tape for odot
Output "assets/demo.gif"

Set Shell "zsh"
Set FontSize 16
Set Width 900
Set Height 500
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Env PATH "/Users/kyle/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
Env ODOT_DB_PATH "/tmp/odot_demo/db.sqlite"

# Add a task
Type "odot add 'Plan weekend hike' -p 1 -c personal"
Enter
Sleep 1.5s

# List all tasks
Type "odot list"
Enter
Sleep 2.5s

# Filter to open tasks only
Type "odot list --todo --sort priority"
Enter
Sleep 2.5s

# Search
Type 'odot search "report"'
Enter
Sleep 2s

# Mark a task done
Type "odot update 3 --done"
Enter
Sleep 1.5s

# Show final state
Type "odot list"
Enter
Sleep 3s
