import json
from typing import Generator, List, Dict, Any, Optional

from google import genai
from google.genai import types

from src.llm.base import BaseLLM
from src.config import Config


class MockFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class MockToolCall:
    def __init__(self, index: int, id: str, function: MockFunction):
        self.index = index
        self.id = id
        self.type = "function"
        self.function = function


class MockDelta:
    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[MockToolCall]] = None):
        self.content = content
        self.tool_calls = tool_calls


class MockChoice:
    def __init__(self, delta: MockDelta):
        self.delta = delta


class MockUsage:
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class MockChunk:
    def __init__(self, choices: List[MockChoice], usage: Optional[MockUsage] = None):
        self.choices = choices
        self.usage = usage


class BaseGeminiClient(BaseLLM):
    """
    Common base for all Gemini model clients using the native google-genai SDK.
    Supports native Thinking features and Thought Signatures for advanced models.
    """

    def __init__(self, model: str):
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Add it to your .env file: "
                "GEMINI_API_KEY=your_key_here"
            )
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
        # Remove 'gemini/' prefix if user passed it
        if self.model.startswith("gemini/"):
            self.model = self.model.replace("gemini/", "gemini-")

    def chat(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        reasoning: bool = False,
        tools: List[Dict[str, Any]] = None,
        tool_choice: str = "auto",
    ) -> Generator[Any, None, None]:
        
        system_instruction = None
        gemini_contents = []

        # 1. Parse Conversational history
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += "\n\n" + content

            elif role == "user":
                parts = []
                if content:
                    parts.append(types.Part.from_text(text=content))
                if parts:
                    gemini_contents.append(types.Content(role="user", parts=parts))

            elif role == "assistant":
                parts = []
                if content:
                    parts.append(types.Part.from_text(text=content))
                
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.get("function", {}).get("name", "")
                        func_args_str = tc.get("function", {}).get("arguments", "{}")
                        try:
                            # Parse JSON arguments for function call
                            args_dict = json.loads(func_args_str)
                        except Exception:
                            args_dict = {}
                            
                        parts.append(
                            types.Part.from_function_call(
                                name=func_name,
                                args=args_dict
                            )
                        )
                if parts:
                    gemini_contents.append(types.Content(role="model", parts=parts))

            elif role == "tool":
                func_name = msg.get("name", "unknown")
                # Wrap tool return in dictionary
                result_content = {"result": msg.get("content", "")}
                part = types.Part.from_function_response(name=func_name, response=result_content)
                gemini_contents.append(types.Content(role="user", parts=[part]))

        # 2. Parse Tools to Gemini SDK types
        gemini_tools = None
        if tools:
            func_decls = []
            for t in tools:
                if t.get("type") == "function":
                    f = t.get("function", {})
                    # Ensure parameters conform to expectation or pass a dict
                    func_decls.append(
                        types.FunctionDeclaration(
                            name=f.get("name", ""),
                            description=f.get("description", ""),
                            parameters=f.get("parameters", {})
                        )
                    )
            if func_decls:
                gemini_tools = [types.Tool(function_declarations=func_decls)]

        # 3. Configure generation
        config_kwargs = {}
        
        if system_instruction:
            # Inject reasoning prompt override for standard models if needed
            if reasoning and "thinking" not in self.model:
                system_instruction += "\n\nPlease think step by step and provide your reasoning before the final answer."

            config_kwargs["system_instruction"] = system_instruction
            
        if gemini_tools:
            config_kwargs["tools"] = gemini_tools
            # Attempt to set tool_config mapping
            if tool_choice == "auto":
                config_kwargs["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
            elif tool_choice == "none":
                config_kwargs["tool_config"] = {"function_calling_config": {"mode": "NONE"}}
        
        # Check explicit reasoning mode logic: apply native thinking configs if available
        if reasoning and "thinking" in self.model:
            # If standard dictionary coercion works:
            config_kwargs["thinking_config"] = {"thinking_budget_tokens": 1024}
            
        config = types.GenerateContentConfig(**config_kwargs)

        # 4. Stream response and yield Mocked OpenAI chunks
        response_stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=gemini_contents,
            config=config,
        )

        for chunk_item in response_stream:
            content_str = ""
            mock_tool_calls = []

            if getattr(chunk_item, 'candidates', None):
                first_candidate = chunk_item.candidates[0]
                if getattr(first_candidate, 'content', None) and getattr(first_candidate.content, 'parts', None):
                    for i, part in enumerate(first_candidate.content.parts):
                        # Extract Thought Signatures natively if present
                        if getattr(part, "thought", False):
                            content_str += f"\n<think>\n{part.text}\n</think>\n"
                        elif getattr(part, "text", None):
                            content_str += part.text
                        elif getattr(part, "function_call", None):
                            # Function call conversion
                            args_dict = dict(part.function_call.args) if part.function_call.args else {}
                            args_json = json.dumps(args_dict)
                            mock_fn = MockFunction(
                                name=part.function_call.name,
                                arguments=args_json
                            )
                            mock_tc = MockToolCall(
                                index=i,
                                id=f"call_{part.function_call.name}_{i}", 
                                function=mock_fn
                            )
                            mock_tool_calls.append(mock_tc)

            # Extract usage if present
            mock_usage = None
            if getattr(chunk_item, 'usage_metadata', None):
                mock_usage = MockUsage(
                    prompt_tokens=chunk_item.usage_metadata.prompt_token_count,
                    completion_tokens=chunk_item.usage_metadata.candidates_token_count,
                    total_tokens=chunk_item.usage_metadata.total_token_count
                )

            # Skip empty yields unless it has usage
            if not content_str and not mock_tool_calls and not mock_usage:
                continue

            delta = MockDelta(
                content=content_str if content_str else None,
                tool_calls=mock_tool_calls if mock_tool_calls else None
            )
            choice = MockChoice(delta=delta)
            
            yield MockChunk(choices=[choice], usage=mock_usage)
