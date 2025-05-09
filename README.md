# Ireul

## features

- **ireul agent**: Interactive AI coding assistant with tool capabilities
  - inspired by claude code
- **ireul prompt**: git-like workflow for creating context-rich LLM prompts
  - inspired by repoprompt
  - add/remove files with token counting
  - include specialized personas
  - export as formatted XML

## installation

```bash
# clone the repository
git clone https://github.com/arb8020/ireul.git
cd ireul

# install in dev mode with uv (~~recommended~~ required)
uv pip install -e .

```

## usage

### iruel agent 

run the interactive agent:

```bash
ireul agent
```

the agent can:
- read and edit files
- execute commands with bash
- search for files using grep/glob patterns

### ireul prompt 

create and manage prompts for LLMs with a Git-like workflow:

```bash
# Create a new prompt
ireul prompt create my-review

# Add files to the prompt
ireul prompt add *.py --exclude "tests/*"

# Check status (with token counts)
ireul prompt status

# Add specialized personas
ireul prompt persona --architect --engineer

# Add an instruction
ireul prompt instruct "Review this code for performance issues"

# Remove files
ireul prompt remove unwanted_file.py

# Export the formatted prompt
ireul prompt export -o prompt.txt
```

## personas

Ireul uses YAML files in `~/.ireul/personas/` to define different roles for your prompts:

- `architect.yaml`: software architecture and implementation planning
- `engineer.yaml`: concrete code changes and implementation details
- add your own in the same directory!

## roadmap 

- more useful CLI commands to go with 'ireul agent' and 'ireul context'
- static analysis or something to make it easier to select context without whole files
- nvim for working into the editor (tab complete, inline LLM-powered edits)

