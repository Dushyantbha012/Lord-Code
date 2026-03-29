import json
from typing import List, Dict, Any, Optional
from src.llm.client import GroqClient
from src.tools.manager import tool_manager
from src.cli.theme import print_tool_call

class CodingAgent:
    """Agent that handles coding tasks using the Groq LLM and registered tools."""

    def __init__(self, system_prompt: Optional[str] = None):
        if not system_prompt:
            system_prompt = (
                "You are Lord Code, a high-fidelity AI coding assistant. "
                "You are working inside the Lord-Code repository. "
                "Guidelines:\n"
                "1. All file tools (read_file, write_file, list_dir) use paths relative to the project root.\n"
                "2. Use `list_dir(recursive=True)` for deep exploration of subdirectories.\n"
                "3. You can execute shell commands using `run_command(command)`. Use this for installation, tests, and script execution.\n"
                "4. All shell commands targeting deletion (like `rm`) will be flagged for user approval.\n"
                "5. Be concise and professional."
            )
        self.client = GroqClient()
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def chat(self, user_input: str) -> str:
        """Process user input and handle tool calls with multi-turn orchestration."""
        self.messages.append({"role": "user", "content": user_input})

        while True:
            # 1. Get completion with tool schemas
            schemas = tool_manager.get_tool_schemas()
            completion = self.client.get_chat_completion(self.messages, tools=schemas)
            
            message = completion.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                content = message.content or ""
                self.messages.append({"role": "assistant", "content": content})
                return content

            # Handle Tool Calls - serialize the message strictly as a dict
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": call.type,
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments
                        }
                    } for call in tool_calls
                ]
            self.messages.append(assistant_msg)

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                # Visual log
                try:
                    args_dict = json.loads(function_args)
                    from src.cli.theme import print_tool_call, print_terminal_preview, ask_confirmation
                    
                    if function_name == "run_command":
                        cmd = args_dict.get("command", "")
                        print_terminal_preview(cmd)
                    else:
                        print_tool_call(function_name, args_dict)
                except:
                    from src.cli.theme import print_tool_call
                    print_tool_call(function_name, {"raw": function_args})

                # Execute tool
                result = tool_manager.execute_tool(function_name, function_args)
                
                # Handle approval logic for shell deletions
                if function_name == "run_command" and result.startswith("APPROVAL_REQUIRED:"):
                    if ask_confirmation("Do you want to proceed with this command?"):
                        # Re-run with approved prefix
                        cmd = json.loads(function_args).get("command", "")
                        approved_args = json.dumps({"command": f"#APPROVED# {cmd}"})
                        result = tool_manager.execute_tool(function_name, approved_args)
                    else:
                        result = "User cancelled command execution."

                # Append tool result to history
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": result,
                })

            # Continue the loop to get the next model response after tools
            # The model will use the results from the 'tool' messages

    def clear_history(self) -> None:
        """Reset the chat history."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
