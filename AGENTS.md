# Deployment workflow

Work on source code in the local checkout. Saving local files must not deploy them.

Deploy source changes to Vultr only through Git: commit and push the user's branch, then explicitly pull that branch in `/root/HackUTA` on the instance. Inspect the instance's Git status first and preserve any uncommitted work. Do not push, pull, or restart services merely because a file was saved.

Do not copy source files to the instance using SCP, rsync, SFTP, sync watchers, or direct remote edits. Do not enable automatic deployment or file synchronization. If a different deployment method is necessary, explain why and obtain the user's explicit authorization first.

Read-only SSH diagnostics are permitted. Keep environment files, credentials, databases, and runtime state out of Git; any required configuration changes are separate from source deployment and must be explicitly requested. Restart affected services after an authorized Git deployment when needed, avoiding interruption of active calls.
