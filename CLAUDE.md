# Bash commands
uv run python <path_to_file>
uv run python -m <module>

# Code style
- if a method can be static and is class-specific, decorate it with `@staticmethod` but if is generic/reusable, make it a function outside the class
- use explicit naming for variables and functions
- use "_" prefix for private methods and variables 

# Workflow
- Always use uv for running commands and install packages
- Put unit tests always in `./tests/unit`
- Always work in current directory, all changes make on current repo and current branch