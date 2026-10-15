# Tool stack integrity

Assume most language- and framework-related tools don't exist on this system, include them in flake.nix when you need them.
Some general tools are exempted, such as `curl`, `git`, etc...

# Alternatives

These alternatives allow your workflow to continue when one method fails:

- `curl` when Web Fetch / Browse fails.

# Pause of auto mode

When working in auto mode, pause and inform me in the following situations:

- `sudo` needed.
- Network connection errors.
