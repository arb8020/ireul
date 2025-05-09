#!/usr/bin/env python3
import argparse
import fnmatch
import glob
import json
import os
import sys

import argcomplete

# --- Core prompt functions ---


def create_prompt():
    """Create an empty prompt."""
    return {
        "files": [],  # List of file paths included
        "instruction": "",  # User instruction/question
        "personas": [],  # List of persona names
        "format": "xml",  # Default format
    }


def add_files_to_prompt(prompt, file_patterns, exclude_patterns=None):
    """Add files matching patterns to prompt, excluding any specified patterns."""
    new_prompt = prompt.copy()

    # Process each file pattern
    files_to_add = []
    for pattern in file_patterns:
        # Expand glob patterns
        matching_files = glob.glob(pattern, recursive=True)

        if not matching_files:
            print(f"Warning: No files match pattern '{pattern}'")
            continue

        files_to_add.extend(matching_files)

    # Apply exclusions if specified
    if exclude_patterns:
        for exclude in exclude_patterns:
            files_to_add = [f for f in files_to_add if not fnmatch.fnmatch(f, exclude)]

    # Add unique files to the prompt
    existing_files = set(new_prompt["files"])
    new_files = []

    for file_path in files_to_add:
        if os.path.isfile(file_path) and file_path not in existing_files:
            new_files.append(file_path)
            existing_files.add(file_path)

    new_prompt["files"] = new_prompt["files"] + new_files

    return new_prompt, new_files


def count_tokens(text):
    """Count tokens in text (simple approximation)."""
    # Simple approximation: ~4 characters per token for English text
    return len(text) // 4


def remove_files_from_prompt(prompt, file_patterns):
    """Remove files matching patterns from prompt."""
    new_prompt = prompt.copy()

    # Expand file patterns to get full paths
    files_to_remove = set()
    for pattern in file_patterns:
        # If pattern contains wildcard, use glob
        if "*" in pattern or "?" in pattern:
            matching_files = glob.glob(pattern, recursive=True)
            files_to_remove.update(matching_files)
        else:
            # Otherwise, just add the exact path
            files_to_remove.add(pattern)

    # Remove the files
    original_count = len(new_prompt["files"])
    new_prompt["files"] = [f for f in new_prompt["files"] if f not in files_to_remove]
    removed_count = original_count - len(new_prompt["files"])

    return new_prompt, removed_count


def add_instruction_to_prompt(prompt, instruction):
    """Add an instruction to the prompt."""
    new_prompt = prompt.copy()
    new_prompt["instruction"] = instruction
    return new_prompt


def add_persona_to_prompt(prompt, persona):
    """Add a persona to the prompt."""
    new_prompt = prompt.copy()
    if persona not in new_prompt["personas"]:
        new_prompt["personas"].append(persona)
    return new_prompt


def get_file_content(file_path):
    """Get content of a file with basic error handling."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def get_current_prompt():
    """Get the current prompt or create a default if none exists."""
    name = get_current_prompt_name()

    if not name:
        # No current prompt, create a default
        name = "default"
        prompt = create_prompt()
        save_prompt(name, prompt)
        set_current_prompt_name(name)
        return name, prompt

    prompt = load_prompt(name)
    if prompt is None:
        # Current prompt name exists but file is missing
        prompt = create_prompt()
        save_prompt(name, prompt)

    return name, prompt


def generate_file_map(files):
    """Generate a file map showing directory structure."""
    if not files:
        return "No files added to prompt."

    # Get common prefix
    common_prefix = os.path.commonpath([os.path.abspath(f) for f in files])

    # Build file map
    file_map = f"{common_prefix}\n"

    # Sort files for a predictable output
    sorted_files = sorted(files)

    for file_path in sorted_files:
        abs_path = os.path.abspath(file_path)
        rel_path = os.path.relpath(abs_path, common_prefix)
        indent = "  " * (rel_path.count(os.sep))
        file_name = os.path.basename(file_path)
        file_map += f"{indent}├── {file_name}\n"

    return file_map


def format_prompt_as_xml(prompt, files_content, patch_type=None):
    """Format prompt as XML."""
    xml = ""

    # Add patch formatting instructions if requested
    if patch_type:
        patch_instructions = load_patch_instructions(patch_type)
        if patch_instructions:
            xml += "<xml_formatting_instructions>\n"
            xml += patch_instructions
            xml += "\n</xml_formatting_instructions>\n\n"

    # Add file map if files exist
    if prompt["files"]:
        xml += "<file_map>\n"
        xml += generate_file_map(prompt["files"])
        xml += "</file_map>\n\n"

    # Add file contents
    if files_content:
        xml += "<file_contents>\n"
        for file_path, content in files_content.items():
            xml += f"File: {file_path}\n"
            xml += "```\n"
            xml += content
            xml += "\n```\n\n"
        xml += "</file_contents>\n\n"

    # Add personas
    if prompt["personas"]:
        for i, persona_name in enumerate(prompt["personas"], 1):
            persona = load_persona(persona_name)
            if persona:
                xml += f"<meta prompt {i} = \"{persona.get('name', f'[{persona_name}]')}\">\n"
                xml += persona.get("content", f"Role: {persona_name}")
                xml += "\n</meta prompt " + str(i) + ">\n"

    # Add instruction
    if prompt["instruction"]:
        xml += "<user_instructions>\n"
        xml += prompt["instruction"]
        xml += "\n</user_instructions>\n"

    return xml


# --- Storage functions ---


def get_persona_dir(user_dir=True):
    """Get the directory where personas are stored.

    Args:
        user_dir: If True, returns user customization directory.
                 If False, returns bundled defaults directory.
    """
    if user_dir:
        # User customizations directory
        home_dir = os.path.expanduser("~")
        persona_dir = os.path.join(home_dir, ".ireul", "personas")
        os.makedirs(persona_dir, exist_ok=True)
        return persona_dir
    else:
        # Bundled defaults directory
        package_dir = os.path.dirname(__file__)
        return os.path.join(package_dir, "personas")


def load_persona(name):
    """Load a persona by name."""
    # First check user directory
    user_dir = get_persona_dir(user_dir=True)
    user_path = os.path.join(user_dir, f"{name}.yaml")

    # Then check bundled directory
    pkg_dir = get_persona_dir(user_dir=False)
    pkg_path = os.path.join(pkg_dir, f"{name}.yaml")

    # Try user path first, then package path
    for path in [user_path, pkg_path]:
        if os.path.exists(path):
            try:
                import yaml

                with open(path, "r") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Error loading persona '{name}' from {path}: {str(e)}")
                # Continue to try next path

    return None


def get_patch_dir(user_dir=True):
    """Get the directory where patch instructions are stored."""
    if user_dir:
        # User customizations directory
        home_dir = os.path.expanduser("~")
        patch_dir = os.path.join(home_dir, ".ireul", "patching")
        os.makedirs(patch_dir, exist_ok=True)
        return patch_dir
    else:
        # Bundled defaults directory
        package_dir = os.path.dirname(__file__)
        return os.path.join(package_dir, "patching")


def load_patch_instructions(patch_type="xml"):
    """Load patch instructions of the specified type."""
    # Check user directory
    user_dir = get_patch_dir(user_dir=True)
    user_path = os.path.join(user_dir, f"{patch_type}.txt")

    # Check bundled directory
    pkg_dir = get_patch_dir(user_dir=False)
    pkg_path = os.path.join(pkg_dir, f"{patch_type}.txt")

    # Also check legacy location
    package_dir = os.path.dirname(__file__)
    legacy_path = os.path.join(package_dir, "..", f"{patch_type}prompt.txt")

    # Try paths in order of preference
    for path in [user_path, pkg_path, legacy_path]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(
                    f"Warning: Error reading patch instructions from {path}: {str(e)}"
                )
                # Continue to try next path

    print(f"Warning: No patch instructions found for '{patch_type}'")
    return ""


def get_prompt_dir():
    """Get the directory where prompts are stored."""
    home_dir = os.path.expanduser("~")
    prompt_dir = os.path.join(home_dir, ".ireul", "prompts")
    os.makedirs(prompt_dir, exist_ok=True)
    return prompt_dir


def list_personas():
    """List available personas."""
    persona_dir = get_persona_dir()
    persona_files = glob.glob(os.path.join(persona_dir, "*.yaml"))
    return [os.path.basename(f).replace(".yaml", "") for f in persona_files]


def get_current_prompt_path():
    """Get path to the current prompt file."""
    prompt_dir = get_prompt_dir()
    return os.path.join(prompt_dir, "current_prompt.json")


def get_prompt_path(name):
    """Get path for a specific prompt."""
    prompt_dir = get_prompt_dir()
    return os.path.join(prompt_dir, f"{name}.json")


def save_prompt(name, prompt):
    """Save a prompt to disk."""
    prompt_path = get_prompt_path(name)
    with open(prompt_path, "w") as f:
        json.dump(prompt, f, indent=2)


def load_prompt(name):
    """Load a prompt from disk."""
    prompt_path = get_prompt_path(name)
    if not os.path.exists(prompt_path):
        return None

    with open(prompt_path, "r") as f:
        return json.load(f)


def get_current_prompt_name():
    """Get the name of the current prompt."""
    current_prompt_path = get_current_prompt_path()

    if not os.path.exists(current_prompt_path):
        return None

    with open(current_prompt_path, "r") as f:
        return f.read().strip()


def set_current_prompt_name(name):
    """Set the current prompt name."""
    current_prompt_path = get_current_prompt_path()

    with open(current_prompt_path, "w") as f:
        f.write(name)


def list_available_prompts():
    """List all available prompts."""
    prompt_dir = get_prompt_dir()
    prompt_files = glob.glob(os.path.join(prompt_dir, "*.json"))
    return [
        os.path.basename(f).replace(".json", "")
        for f in prompt_files
        if os.path.basename(f) != "current_prompt.json"
    ]


# --- Command handlers ---


def handle_create(args):
    """Handle 'ireul prompt create' command."""
    name = args.name
    prompt_path = get_prompt_path(name)

    if os.path.exists(prompt_path):
        print(f"Prompt '{name}' already exists.")
        user_input = input(f"Do you want to switch to '{name}'? (y/n): ")
        if user_input.lower() in ("y", "yes"):
            return handle_switch(args)
        return 1

    # Create new prompt
    prompt = create_prompt()
    save_prompt(name, prompt)

    # Set as current
    set_current_prompt_name(name)

    print(f"Created and switched to prompt: {name}")
    return 0


def handle_switch(args):
    """Handle 'ireul prompt switch' command."""
    name = args.name
    prompt_path = get_prompt_path(name)

    if not os.path.exists(prompt_path):
        print(f"Prompt '{name}' does not exist.")
        prompts = list_available_prompts()
        if prompts:
            print("\nAvailable prompts:")
            for p in prompts:
                print(f"  {p}")
        return 1

    set_current_prompt_name(name)
    print(f"Switched to prompt: {name}")
    return 0


def handle_add(args):
    """Handle 'ireul prompt add' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    if not args.files:
        print("Error: No files specified.")
        return 1

    # Add files to prompt
    updated_prompt, new_files = add_files_to_prompt(prompt, args.files, args.exclude)

    # Count how many new files were added
    num_added = len(new_files)

    # Save updated prompt
    save_prompt(name, updated_prompt)

    print(f"Added {num_added} files to prompt '{name}'.")
    print(f"Total files in prompt: {len(updated_prompt['files'])}")

    return 0


def handle_remove(args):
    """Handle 'ireul prompt remove' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    if not args.files:
        print("Error: No files specified.")
        return 1

    # Remove files from prompt
    updated_prompt, removed_count = remove_files_from_prompt(prompt, args.files)

    # Save updated prompt
    save_prompt(name, updated_prompt)

    print(f"Removed {removed_count} files from prompt '{name}'.")
    print(f"Files remaining in prompt: {len(updated_prompt['files'])}")

    return 0


def handle_status(args):
    """Handle 'ireul prompt status' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    # Read file contents for token counting
    files_content = {}
    for file_path in prompt["files"]:
        content = get_file_content(file_path)
        files_content[file_path] = content

    # Format the prompt to get total tokens
    formatted_prompt = format_prompt_as_xml(prompt, files_content)
    total_tokens = count_tokens(formatted_prompt)

    # Display branch-like header
    print(f"On prompt \033[1;32m{name}\033[0m")
    print()

    # Show available prompts
    available_prompts = list_available_prompts()
    if available_prompts:
        print("Available prompts:")
        for p in available_prompts:
            if p == name:
                print(
                    f"* \033[1;32m{p}\033[0m"
                )  # Current prompt in green with asterisk
            else:
                print(f"  {p}")
        print()

    # Display summary
    print(f"Files: {len(prompt['files'])} files added")

    if prompt["instruction"]:
        print(f"Instruction: \"{prompt['instruction']}\"")
    else:
        print("Instruction: None")

    if prompt["personas"]:
        print(f"Personas: {', '.join(prompt['personas'])}")
    else:
        print("Personas: None")

    print(f"Format: {prompt['format']}")
    print(f"Total estimated tokens: \033[1;33m{total_tokens}\033[0m")

    # Show warning if token count is high
    if total_tokens > 32000:
        print(
            "\033[1;31mWarning: Token count exceeds typical effective model context window (32K)\033[0m"
        )

    # File details
    if prompt["files"]:
        print("\nFiles added:")
        for file_path in sorted(prompt["files"]):
            file_tokens = count_tokens(files_content[file_path])
            print(f"  \033[1;36m{file_path}\033[0m ({file_tokens} tokens)")

    # Show usage hint
    print("\nReady to export with 'ireul prompt export'")

    return 0


def handle_instruct(args):
    """Handle 'ireul prompt instruct' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    # Normalize instruction (replace newlines with spaces)
    instruction = " ".join(args.instruction.split())

    # Add instruction to prompt
    updated_prompt = add_instruction_to_prompt(prompt, instruction)

    # Save updated prompt
    save_prompt(name, updated_prompt)

    print(f"Added instruction to prompt '{name}':")
    print(f'  "{instruction}"')

    return 0


def handle_persona(args):
    """Handle 'ireul prompt persona' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    # If no personas specified, show available ones
    if not (args.architect or args.engineer) and not args.add:
        available_personas = list_personas()
        current_personas = prompt["personas"]

        print(f"Current prompt: {name}")
        print(
            f"Active personas: {', '.join(current_personas) if current_personas else 'None'}"
        )
        print("\nAvailable personas:")

        for p in available_personas:
            if p in current_personas:
                print(f"* {p}")
            else:
                print(f"  {p}")

        return 0

    # Add personas to prompt
    updated_prompt = prompt.copy()

    if args.architect:
        updated_prompt = add_persona_to_prompt(updated_prompt, "architect")

    if args.engineer:
        updated_prompt = add_persona_to_prompt(updated_prompt, "engineer")

    if args.add:
        for persona in args.add:
            if persona in list_personas():
                updated_prompt = add_persona_to_prompt(updated_prompt, persona)
            else:
                print(f"Warning: Persona '{persona}' not found.")

    # Save updated prompt
    save_prompt(name, updated_prompt)

    print(f"Added personas to prompt '{name}': {', '.join(updated_prompt['personas'])}")

    return 0


def handle_export(args):
    """Handle 'ireul prompt export' command."""
    # Get current prompt
    name, prompt = get_current_prompt()

    if not prompt["files"]:
        print("Warning: No files in prompt.")

    # Read file contents
    files_content = {}
    for file_path in prompt["files"]:
        content = get_file_content(file_path)
        files_content[file_path] = content

    # Determine patch type (if any)
    patch_type = args.patch_type if args.patch else None

    # Format as XML
    formatted_prompt = format_prompt_as_xml(
        prompt, files_content, patch_type=patch_type
    )

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Use prompt name as default filename
        output_path = f"{name}.txt"

    # Output
    if args.stdout:
        # Print to stdout if explicitly requested
        print(formatted_prompt)
    else:
        # Otherwise, save to file
        with open(output_path, "w") as f:
            f.write(formatted_prompt)
        print(f"Exported prompt to {output_path}")

    return 0


# --- CLI entry point ---


def add_path_completer(parser):
    """Add path completion to parser arguments."""
    for action in parser._actions:
        if action.dest in ["files", "output"]:
            action.completer = argcomplete.completers.FilesCompleter()


def main():
    """Main entry point for the prompt command."""
    parser = argparse.ArgumentParser(
        prog="ireul prompt", description="Manage prompts for LLMs"
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    # Create subcommand
    create_parser = subparsers.add_parser("create", help="Create a new prompt")
    create_parser.add_argument("name", help="Name of the prompt")

    # Switch subcommand
    switch_parser = subparsers.add_parser("switch", help="Switch to a different prompt")
    switch_parser.add_argument("name", help="Name of the prompt to switch to")

    # Add subcommand
    add_parser = subparsers.add_parser("add", help="Add files to the current prompt")
    add_parser.add_argument("files", nargs="+", help="Files or glob patterns to add")
    add_parser.add_argument("--exclude", nargs="+", help="Patterns to exclude")

    # REmove subcommand
    remove_parser = subparsers.add_parser(
        "remove", help="Remove files from the current prompt"
    )
    remove_parser.add_argument(
        "files", nargs="+", help="Files or glob patterns to remove"
    )

    # Status subcommand
    status_parser = subparsers.add_parser("status", help="Show current prompt status")
    status_parser.add_argument(
        "--show-files", "-f", action="store_true", help="Show file list"
    )
    status_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )

    # Instruct subcommand
    instruct_parser = subparsers.add_parser(
        "instruct", help="Add an instruction to the prompt"
    )
    instruct_parser.add_argument("instruction", help="The instruction or question")

    # Persona subcommand
    persona_parser = subparsers.add_parser("persona", help="Add personas to the prompt")
    persona_parser.add_argument(
        "--architect", action="store_true", help="Add architect persona"
    )
    persona_parser.add_argument(
        "--engineer", action="store_true", help="Add engineer persona"
    )
    persona_parser.add_argument(
        "--add", nargs="+", help="Add specific personas by name"
    )

    # Export subcommand
    export_parser = subparsers.add_parser("export", help="Export the prompt as XML")
    export_parser.add_argument(
        "-o", "--output", help="Output file (defaults to <prompt_name>.txt)"
    )
    export_parser.add_argument(
        "--stdout", action="store_true", help="Print to stdout instead of file"
    )
    export_parser.add_argument(
        "--patch",
        action="store_true",
        help="Include instructions for generating code patches",
    )
    export_parser.add_argument(
        "--patch-type",
        choices=["xml"],
        default="xml",
        help="Specify the patch format type (default: xml)",
    )

    add_path_completer(add_parser)
    add_path_completer(remove_parser)
    add_path_completer(export_parser)

    # Enable tab completion
    argcomplete.autocomplete(parser)

    # If called with no arguments, show help
    if len(sys.argv) <= 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # Handle subcommands
    if args.subcommand == "create":
        return handle_create(args)
    elif args.subcommand == "switch":
        return handle_switch(args)
    elif args.subcommand == "add":
        return handle_add(args)
    elif args.subcommand == "remove":
        return handle_remove(args)
    elif args.subcommand == "status":
        return handle_status(args)
    elif args.subcommand == "instruct":
        return handle_instruct(args)
    elif args.subcommand == "persona":
        return handle_persona(args)
    elif args.subcommand == "export":
        return handle_export(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
