# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
# ]
# ///

import argparse
import json
import os
import subprocess

import openai


class ToolDefinition:
    def __init__(self, name, description, input_schema, function):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.function = function


read_file_input_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The relative path of a file in the working directory.",
        }
    },
    "required": ["path"],
}


def read_file(input_json):
    try:
        if isinstance(input_json, str):
            input_data = json.loads(input_json)
        else:
            input_data = input_json

        path = input_data.get("path", "")

        with open(path, "r") as file:
            content = file.read()

        return content, None
    except Exception as e:
        return "", e


read_file_definition = ToolDefinition(
    name="read_file",
    description="Read the contents of a given relative file path. Use this when you want to see what's inside a file. Do not use this with directory names.",
    input_schema=read_file_input_schema,
    function=read_file,
)

bash_command_input_schema = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "The bash command to execute."}
    },
    "required": ["command"],
}


def execute_bash_command(input_json):
    """Execute a bash command and return its output."""
    try:
        if isinstance(input_json, str):
            input_data = json.loads(input_json)
        else:
            input_data = input_json

        command = input_data.get("command", "")

        # Execute the command and capture output
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,  # Timeout after 30 seconds
        )

        # Prepare the response
        if result.returncode == 0:
            return result.stdout, None
        else:
            return (
                result.stdout,
                f"Command failed with exit code {result.returncode}. Error: {result.stderr}",
            )

    except subprocess.TimeoutExpired:
        return "", "Command timed out after 30 seconds"
    except Exception as e:
        return "", str(e)


bash_command_definition = ToolDefinition(
    name="execute_bash",
    description="Execute a bash command and get its output. Use this for running system commands, checking files, or other shell operations.",
    input_schema=bash_command_input_schema,
    function=execute_bash_command,
)
# First, let's define the input schema for edit_file
edit_file_input_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The relative path of a file in the working directory.",
        },
        "old_str": {
            "type": "string",
            "description": "Text to search for - must match exactly.",
        },
        "new_str": {
            "type": "string",
            "description": "Text to replace old_str with.",
        },
    },
    "required": ["path", "old_str", "new_str"],
}


# Now, let's implement the edit_file function
def edit_file(input_json):
    """Edit a file by replacing text or create a new file."""
    try:
        if isinstance(input_json, str):
            input_data = json.loads(input_json)
        else:
            input_data = input_json

        path = input_data.get("path", "")
        old_str = input_data.get("old_str", "")
        new_str = input_data.get("new_str", "")

        # Validate inputs
        if not path:
            return "", "Path cannot be empty"
        if old_str == new_str:
            return "", "old_str and new_str must be different"

        # Create file if it doesn't exist and old_str is empty
        if not os.path.exists(path) and old_str == "":
            # Create directory if needed
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Write the new file
            with open(path, "w") as file:
                file.write(new_str)
            return f"Successfully created file {path}", None

        # Read existing file
        try:
            with open(path, "r") as file:
                content = file.read()
        except FileNotFoundError:
            return "", f"File {path} not found"

        # Replace text
        new_content = content.replace(old_str, new_str)

        # Check if any replacements were made
        if new_content == content and old_str != "":
            return "", "old_str not found in file"

        # Write updated content back to file
        with open(path, "w") as file:
            file.write(new_content)

        return "OK", None
    except Exception as e:
        return "", str(e)


# Create the tool definition
edit_file_definition = ToolDefinition(
    name="edit_file",
    description="Make edits to a text file. Replaces 'old_str' with 'new_str' in the given file. "
    "If 'old_str' is empty and the file doesn't exist, a new file will be created with 'new_str' as content. "
    "'old_str' and 'new_str' must be different from each other.",
    input_schema=edit_file_input_schema,
    function=edit_file,
)


def format_assistant_message(message):
    """Pure function that formats assistant message"""
    return f"\033[93mAssistant\033[0m: {message}"


def format_tool_call(function_name, function_args):
    """Pure function that formats tool call"""
    return f"\033[92mtool\033[0m: {function_name}({json.dumps(function_args)})"


def format_tool_result(tool_name, result, error=None):
    """Pure function that formats tool execution results"""
    if error:
        return f"\033[91mtool result ({tool_name})\033[0m: Error - {error}"
    else:
        display_result = result
        if isinstance(result, str) and len(result) > 500:
            display_result = result[:500] + "... [truncated]"
        return f"\033[96mtool result ({tool_name})\033[0m: {display_result}"


def format_debug_info(message):
    """Format debug information in gray."""
    return f"\033[90m[DEBUG] {message}\033[0m"


def add_message(conversation, message):
    """Pure function that returns a new conversation with the message added"""
    return conversation + [message]


class Agent:
    def __init__(self, client, get_user_message, tools, require_confirmation=True):
        self.client = client
        self.get_user_message = get_user_message
        self.tools = tools
        self.require_confirmation = require_confirmation

    # ---- PURE STATE TRANSFORMATION METHODS ----

    def add_message(self, conversation, message):
        """Pure function: Add a message to the conversation."""
        return conversation + [message]

    def execute_tool(self, name, input_data):
        """Execute a tool by name. Returns (result, is_error, was_rejected)."""
        tool_def = None
        for tool in self.tools:
            if tool.name == name:
                tool_def = tool
                break

        if tool_def is None:
            return "", "Tool not found", False

        # Check for confirmation if required
        if self.require_confirmation:
            if not self.get_user_confirmation(name, input_data):
                return "", "Tool execution denied by user", True

        result, error = tool_def.function(input_data)
        return result, error, False

    def process_tool_calls(self, conversation, tool_calls):
        """Process tool calls: display, confirm, execute, and add results to conversation."""
        new_conversation = conversation.copy()
        tools_rejected = False

        for tool_call in tool_calls:
            function_call = tool_call.function
            function_name = function_call.name
            function_args = json.loads(function_call.arguments)

            # Display the tool call
            print(format_tool_call(function_name, function_args))

            if tools_rejected:
                # Skip execution if a previous tool was rejected
                result = ""
                error = "Skipped - previous tool was rejected"
                print(format_debug_info("Skipping tool execution due to previous rejection"))
            else:
                # Execute the tool (includes confirmation if required)
                result, error, rejected = self.execute_tool(function_name, function_args)
                tools_rejected = rejected

            # Add the tool response to the conversation
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": result if not error else error,
            }
            new_conversation = self.add_message(new_conversation, tool_response)

            # Display the result
            print(format_tool_result(function_name, result, error))

        return new_conversation

    def get_user_confirmation(self, tool_name, args):
        """Ask for and return user confirmation to execute a tool."""
        formatted_args = json.dumps(args, indent=2)
        print(f"\033[95mConfirmation required\033[0m: Execute '{tool_name}' with arguments:")
        print(f"\033[95m{formatted_args}\033[0m")
        print("\033[95mAllow? (y/n):\033[0m ", end="")
        try:
            response = input().strip().lower()
            return response == 'y' or response == 'yes'
        except EOFError:
            return False

    def run_inference(self, conversation):
        """External operation: Make an API call to get a response."""
        openai_tools = []
        for tool in self.tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )

        return self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=conversation,
            tools=openai_tools,
            tool_choice="auto",
        )

    def get_assistant_response(self, conversation):
        """Get a single response from the assistant and add it to the conversation."""
        # Get assistant response (API call)
        response = self.run_inference(conversation)
        message = response.choices[0].message

        # Update conversation with assistant message
        new_conversation = self.add_message(conversation, message)

        # Display assistant message
        if message.content:
            print(format_assistant_message(message.content))
        elif hasattr(message, "tool_calls") and message.tool_calls:
            print(
                format_debug_info("Assistant requested tools without message content")
            )

        return new_conversation, message

    def handle_assistant_turn(self, conversation):
        """Handle a complete assistant turn including any tool calls."""
        iteration = 0
        has_tool_calls = False

        while True:
            iteration += 1
            if iteration > 1:
                print(
                    format_debug_info(
                        f"Processing follow-up response (iteration {iteration})"
                    )
                )

            # Get assistant response
            conversation, message = self.get_assistant_response(conversation)

            # Check for tool calls
            has_tool_calls = hasattr(message, "tool_calls") and message.tool_calls
            if not has_tool_calls:
                break

            # Handle tool calls
            conversation = self.process_tool_calls(conversation, message.tool_calls)

        return conversation, has_tool_calls

    def run_step(self, conversation, user_input):
        """Process a single conversation turn."""
        conversation = self.add_message(
            conversation, {"role": "user", "content": user_input}
        )

        conversation, _ = self.handle_assistant_turn(conversation)

        return conversation

    def run(self):
        """Main conversation loop with I/O operations."""
        conversation = []

        print("Chat with OpenAI (use 'ctrl-c' to quit)")

        while True:
            print("\033[94mYou\033[0m: ", end="")
            user_input, ok = self.get_user_message()
            if not ok:
                break

            conversation = self.run_step(conversation, user_input)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Chat with OpenAI with functional programming principles"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (if not provided, will use OPENAI_API_KEY environment variable)",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Disable confirmation before executing tools (by default, confirmation is required)",
    )
    return parser.parse_args()


def main(api_key=None, require_confirmation=True):
    """Main function with explicit API key parameter"""
    client = openai.OpenAI(api_key=api_key)

    def get_user_message():
        try:
            message = input()
            return message, True
        except EOFError:
            return "", False

    tools = [read_file_definition, bash_command_definition, edit_file_definition]
    agent = Agent(
        client, get_user_message, tools, require_confirmation=require_confirmation
    )
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    args = parse_arguments()
    main(api_key=args.api_key, require_confirmation=not args.no_confirm)
