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
        from src.safety.guardrail import safety_guard
        self.safety = safety_guard
        from src.agent.context import ContextManager
        self.context_manager = ContextManager()

    def chat(self, user_input: str) -> str:
        """Process user input and handle tool calls with multi-turn orchestration."""
        # 0. Context Injection (Grounding the user's request)
        context_block = self.context_manager.get_full_context_block()
        grounded_input = f"{context_block}\nUser Task: {user_input}" if context_block else user_input
        
        self.messages.append({"role": "user", "content": grounded_input})

        while True:
            # 1. Get completion with tool schemas
            schemas = tool_manager.get_tool_schemas()
            completion, usage = self.client.get_chat_completion(self.messages, tools=schemas)
            
            # Report usage
            from src.cli.theme import print_token_usage
            print_token_usage(usage)

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
                
                # Visual log & Safety Check
                try:
                    args_dict = json.loads(function_args)
                    from src.cli.theme import print_tool_call, print_terminal_preview, ask_confirmation
                    
                    # --- Safety Guardrail Check ---
                    risk = self.safety.get_tool_risk(function_name, args_dict)
                    
                    if risk == "blocked":
                        result = f"Error: Action blocked by safety guardrail. Restricted path or command."
                    elif risk == "high":
                        # Require confirmation
                        if function_name == "run_command":
                            print_terminal_preview(args_dict.get("command", ""))
                            if not ask_confirmation("Proceed with high-risk command?"):
                                result = "User cancelled execution."
                            else:
                                result = tool_manager.execute_tool(function_name, function_args)
                        else:
                            print_tool_call(function_name, args_dict)
                            if not ask_confirmation(f"Confirm {function_name}?"):
                                result = "User cancelled execution."
                            else:
                                result = tool_manager.execute_tool(function_name, function_args)
                    else:
                        # Low risk - automatic execution
                        if function_name == "run_command":
                            print_terminal_preview(args_dict.get("command", ""))
                        else:
                            print_tool_call(function_name, args_dict)
                        result = tool_manager.execute_tool(function_name, function_args)
                except Exception as e:
                    # Fallback for parsing errors
                    result = f"Error: {str(e)}"

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
