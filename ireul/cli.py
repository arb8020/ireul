#!/usr/bin/env python3
import argparse
import sys


def agent_command(args):
    """Run the Ireul agent."""
    from ireul.agent import main as agent_main

    return agent_main(
        api_key=args.api_key,
        provider=args.provider,
        model=args.model,
        require_confirmation=not args.no_confirm,
    )


def prompt_command(args):
    """Run the Ireul prompt command."""
    # Preserve the original sys.argv
    original_argv = sys.argv.copy()

    # Reconstruct the arguments for the prompt module
    # Replace "ireul prompt" with just "prompt" at the beginning
    new_argv = ["prompt"] + original_argv[original_argv.index("prompt") + 1 :]
    sys.argv = new_argv

    # Import and run the prompt module
    from ireul.prompt import main as prompt_main

    result = prompt_main()

    # Restore original argv
    sys.argv = original_argv

    return result


def main():
    # Create the top-level parser
    parser = argparse.ArgumentParser(
        description="Ireul - An Evangelion-inspired AI coding assistant"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Create subparsers for each command
    subparsers = parser.add_subparsers(
        title="commands", dest="command", help="Command to run"
    )

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Run the Ireul agent")
    agent_parser.add_argument(
        "--api-key",
        type=str,
        help="API key (if not provided, will use OPENAI_API_KEY for OpenAI)",
    )
    agent_parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "google"],
        default="openai",
        help="Model provider (default: openai)",
    )
    agent_parser.add_argument(
        "--model",
        type=str,
        help="Model name (default: gpt-4.1-mini for OpenAI, gemini-2.0-flash for Google)",
    )
    agent_parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Disable confirmation before executing tools",
    )

    # Prompt command
    prompt_parser = subparsers.add_parser(
        "prompt", help="Create and manage prompts for LLMs"
    )
    # Add a catch-all argument to prevent errors
    prompt_parser.add_argument(
        "prompt_args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS
    )

    # Parse arguments
    args = parser.parse_args()

    # If no command is specified, print help
    if not args.command:
        parser.print_help()
        return 0

    # Execute the appropriate command
    if args.command == "agent":
        return agent_command(args)
    elif args.command == "prompt":
        return prompt_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
