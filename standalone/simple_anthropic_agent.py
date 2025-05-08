# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
# ]
# ///
import sys
import anthropic
import readline  # For better input handling
import json

def main():
    client = anthropic.Anthropic()
    
    def get_user_message():
        try:
            message = input()
            return message, True
        except EOFError:
            return "", False
    
    tools = [read_file_definition]
    agent = Agent(client, get_user_message, tools)  # Pass tools to constructor
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")

class ToolDefinition:
    def __init__(self, name, description, input_schema, function):
        self.name = name  # json:"name"
        self.description = description  # json:"description"
        self.input_schema = input_schema  # json:"input_schema"
        self.function = function  # Function that takes JSON input and returns (result, error)

# Simply define the schema directly as a dictionary
read_file_input_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The relative path of a file in the working directory."
        }
    },
    "required": ["path"]
}

# File reading function
def read_file(input_json):
    try:
        # Parse JSON string if it's not already a dict
        if isinstance(input_json, str):
            input_data = json.loads(input_json)
        else:
            input_data = input_json
            
        path = input_data.get("path", "")
        
        with open(path, 'r') as file:
            content = file.read()
        
        return content, None
    except Exception as e:
        return "", e

# Create the tool definition
read_file_definition = ToolDefinition(
    name="read_file",
    description="Read the contents of a given relative file path. Use this when you want to see what's inside a file. Do not use this with directory names.",
    input_schema=read_file_input_schema,
    function=read_file
)

class Agent:
    def __init__(self, client, get_user_message, tools):  # Added tools parameter
        self.client = client
        self.get_user_message = get_user_message
        self.tools = tools  # Added tools field
    
    def run(self):
        conversation = []
        
        print("Chat with Claude (use 'ctrl-c' to quit)")
        
        read_user_input = True
        while True:
            if read_user_input:
                print("\033[94mYou\033[0m: ", end="")
                user_input, ok = self.get_user_message()
                if not ok:
                    break
                
                user_message = {"role": "user", "content": user_input}
                conversation.append(user_message)
            
            message = self.run_inference(conversation)
            
            # Add Claude's response to conversation history
            assistant_content = []
            for block in message.content:
                if block.type == "text":
                    assistant_content.append({"type": "text",
                                              "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({"type": "tool_use",
                                              "id":   block.id,        # ← keep it!
                                              "name": block.name,
                                              "input": block.input})

            assistant_message = {"role": "assistant", "content": assistant_content}
            conversation.append(assistant_message)
            
            # Process message content and handle tool use
            tool_results = []
            for content in message.content:
                if content.type == "text":
                    print(f"\033[93mClaude\033[0m: {content.text}")
                elif content.type == "tool_use":
                    result = self.execute_tool(content.id, content.name, content.input)
                    tool_results.append(result)
            
            if len(tool_results) == 0:
                read_user_input = True
                continue
            
            # Add tool results to conversation
            read_user_input = False
            tool_results_message = {"role": "user", "content": tool_results}
            conversation.append(tool_results_message)


    def execute_tool(self, id, name, input_data):
        # Find the tool by name
        tool_def = None
        for tool in self.tools:
            if tool.name == name:
                tool_def = tool
                break
        
        if tool_def is None:
            return {
                "type": "tool_result",
                "tool_use_id": id,  # This must match the id from the tool_use
                "content": "tool not found",
                "is_error": True
            }
        
        print(f"\033[92mtool\033[0m: {name}({json.dumps(input_data)})")
        
        # Execute the tool function
        response, error = tool_def.function(input_data)
        
        if error:
            return {
                "type": "tool_result",
                "tool_use_id": id,  # This must match the id from the tool_use
                "content": str(error),
                "is_error": True
            }
        
        return {
            "type": "tool_result",
            "tool_use_id": id,  # This must match the id from the tool_use
            "content": response,
        }

    def run_inference(self, conversation):
        # Convert our ToolDefinition objects to Anthropic SDK format
        anthropic_tools = []
        for tool in self.tools:
            anthropic_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            })
        
        message = self.client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1024,
            messages=conversation,
            tools=anthropic_tools
        )
        
        return message

    
if __name__ == "__main__":
    main()
