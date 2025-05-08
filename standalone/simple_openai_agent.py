# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
# ]
# ///

import sys
import openai
import readline  # For better input handling
import json

class ToolDefinition:
    def __init__(self, name, description, input_schema, function):
        self.name = name
        self.description = description
        self.input_schema = input_schema  # Will be converted to OpenAI's parameters format
        self.function = function

# Schema definition remains the same
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

def read_file(input_json):
    try:
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

read_file_definition = ToolDefinition(
    name="read_file",
    description="Read the contents of a given relative file path. Use this when you want to see what's inside a file. Do not use this with directory names.",
    input_schema=read_file_input_schema,
    function=read_file
)

class Agent:
    def __init__(self, client, get_user_message, tools):
        self.client = client
        self.get_user_message = get_user_message
        self.tools = tools
    
    def run(self):
        conversation = []
        
        print("Chat with OpenAI (use 'ctrl-c' to quit)")
        
        while True:
            print("\033[94mYou\033[0m: ", end="")
            user_input, ok = self.get_user_message()
            if not ok:
                break
            
            # Add user message to conversation
            conversation.append({"role": "user", "content": user_input})
            
            # Get assistant response
            response = self.run_inference(conversation)
            
            # Process the response
            message = response.choices[0].message
            conversation.append(message)
            
            # Display text content
            if message.content:
                print(f"\033[93mAssistant\033[0m: {message.content}")
            
            # Handle tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    function_call = tool_call.function
                    function_name = function_call.name
                    function_args = json.loads(function_call.arguments)
                    
                    print(f"\033[92mtool\033[0m: {function_name}({json.dumps(function_args)})")
                    
                    # Execute the tool
                    result, error = self.execute_tool(function_name, function_args)
                    
                    # Format tool response
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": result if not error else str(error)
                    }
                    
                    # Add tool response to conversation
                    conversation.append(tool_response)
                
                # Get follow-up response after tool use
                response = self.run_inference(conversation)
                assistant_message = response.choices[0].message
                conversation.append(assistant_message)
                
                if assistant_message.content:
                    print(f"\033[93mAssistant\033[0m: {assistant_message.content}")

    def execute_tool(self, name, input_data):
        # Find the tool by name
        tool_def = None
        for tool in self.tools:
            if tool.name == name:
                tool_def = tool
                break
        
        if tool_def is None:
            return "Tool not found", True
        
        # Execute the tool function
        response, error = tool_def.function(input_data)
        return response, error

    def run_inference(self, conversation):
        # Convert our ToolDefinition objects to OpenAI tools format
        openai_tools = []
        for tool in self.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            })
        
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",  # Use an appropriate OpenAI model
            messages=conversation,
            tools=openai_tools,
            tool_choice="auto"  # Let the model decide when to use tools
        )
        
        return response

def main():
    client = openai.OpenAI()  # Uses OPENAI_API_KEY from environment
    
    def get_user_message():
        try:
            message = input()
            return message, True
        except EOFError:
            return "", False
    
    tools = [read_file_definition]
    agent = Agent(client, get_user_message, tools)
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")
   
if __name__ == "__main__":
    main()
