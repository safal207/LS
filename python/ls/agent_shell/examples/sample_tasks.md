# LS Agent Shell sample tasks

- `ls-agent run "Review PR #387 and write feedback"`
- `ls-agent plan "Create investor opening slide for LS"`
- `ls-agent run "Prepare discovery outreach packet" --approval safe-write`
- `ls-agent list --status waiting_approval`
- `ls-agent approvals --task-id task-12345678`
- `ls-agent ltp-export task-12345678`
- `ls-agent ltp-export-all --status waiting_approval`
- `ls-agent ltp-inspect task-12345678`

See also: `python/ls/agent_shell/README.md`
