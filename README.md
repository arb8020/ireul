# Ireul

<div>
<img align="right" width="200" src="https://github.com/user-attachments/assets/5ced0c8d-4361-44a7-bfe1-9ab091533c02">

inspired by Neon Genesis Evangelion's eleventh angel, [Iruel](https://evangelion.fandom.com/wiki/Ireul):
- infiltrates your codebase with `ireul agent`
- helps you create prompts to copy-paste to external LLMs with `ireul prompt`
- and more to come!

</div>

open-source, bring your own API keys!

## features

- **ireul agent**: Interactive AI coding assistant with tool capabilities
  - heavily inspired by [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)
  - (does not actually support Claude as a provider yet)
- **ireul prompt**: git-like workflow for creating context-rich LLM prompts
  - heavily inspired by [RepoPrompt](https://repoprompt.com/)
  - add/remove files with token counting
  - include specialized personas
  - export as formatted XML

## installation

```bash
# clone the repository
git clone https://github.com/arb8020/ireul.git
cd ireul

# install in dev mode with uv (required)
uv pip install -e .
```

## usage

### `ireul agent`

run the interactive agent:

```bash
ireul agent
```

make sure to: 

```bash
export OPENAI_API_KEY=
export GEMINI_API_KEY=
```

the agent can:
- read and edit files
- execute commands with bash
- search for files using grep/glob patterns

### `ireul prompt`

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

`ireul` uses YAML files in `~/.ireul/personas/` to define different roles for your prompts:

- `architect.yaml`: software architecture and implementation planning
- `engineer.yaml`: concrete code changes and implementation details
- add your own in the same directory!

## roadmap 

- `ireul agent`
  - support anthropic models
  - support openrouter
  - more intelligent context management
  - conversation persistence

- `ireul prompt`
  - static analysis/LSP something to make it easier to select relevant context without whole files

- more useful CLI commands to go with 'ireul agent' and 'ireul context' (not sure abt shape of this)

- `ireul.nvim`
  - copilot-like tab complete
  - command-k inspired inline edits

