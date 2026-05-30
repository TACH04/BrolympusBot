import logging

logger = logging.getLogger('core.tool_registry')

class ToolRegistry:
    """
    A registry for managing and dispatching LLM-accessible tools.
    """
    def __init__(self):
        self._tools = {}

    def register(self, name, description, parameters):
        """
        Decorator to register a function as a tool.
        
        Args:
            name (str): The name of the tool.
            description (str): A description of what the tool does.
            parameters (dict): JSON Schema describing the tool's parameters.
        """
        def decorator(func):
            self._tools[name] = {
                "func": func,
                "schema": {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters
                    }
                }
            }
            return func
        return decorator

    def execute(self, name, arguments, debug_callback=None):
        """
        Executes a registered tool by name with the provided arguments.
        """
        if name not in self._tools:
            error_msg = f"Error: Tool '{name}' not found."
            logger.error(error_msg)
            return error_msg
        
        func = self._tools[name]["func"]
        try:
            # We check if the tool function accepts a debug_callback
            import inspect
            sig = inspect.signature(func)
            
            if 'debug_callback' in sig.parameters:
                result = func(**arguments, debug_callback=debug_callback)
            else:
                # We assume the arguments passed by the LLM match the function signature
                result = func(**arguments)

            # Check if the returned string or dict indicates an error
            is_error = False
            if isinstance(result, str) and (result.startswith("Error") or "error" in result.lower()[:10]):
                is_error = True
            elif isinstance(result, dict) and result.get("status") == "error":
                is_error = True
                
            if is_error:
                err_msg = result.get("message") if isinstance(result, dict) else result
                logger.error(f"Tool '{name}' returned an error: {err_msg}")
            else:
                logger.info(f"Tool '{name}' completed successfully.")
                
            return result
                
        except TypeError as e:
            # Handle cases where LLM passes extra or missing arguments
            error_msg = f"Error: Argument mismatch (TypeError) for tool '{name}': {str(e)}"
            logger.exception(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error executing tool '{name}' ({type(e).__name__}): {str(e)}"
            
            # Smart Exception Logging: Suppress traceback for standard API/input errors
            expected_exceptions = ('HttpError', 'ValueError', 'TypeError', 'FileNotFoundError', 'RequestException')
            if type(e).__name__ in expected_exceptions:
                logger.error(error_msg)
            else:
                logger.exception(error_msg)
                
            return error_msg

    def get_ollama_tools(self):
        """
        Returns a list of tool definitions compatible with Ollama's API.
        """
        # Return tools in the order they were registered
        return [t["schema"] for t in self._tools.values()]
