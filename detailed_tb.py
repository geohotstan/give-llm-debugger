import sys
import traceback
import inspect
import pprint # For pretty printing complex data structures

# --- Configuration ---
MAX_STR_LEN = 100  # Maximum length for string representation of variables
CONTEXT_LINES = 3  # Number of source code lines to show before and after the error line
SHOW_GLOBALS = False # Set to True to show global variables (can be very verbose)
FILTER_GLOBALS = True # If SHOW_GLOBALS, filter out modules, builtins, etc.

def _format_value(value):
    """Safely formats a value, truncating long strings."""
    try:
        s = repr(value)
    except Exception as e:
        return f"<Error during repr: {e}>"
    if len(s) > MAX_STR_LEN:
        return s[:MAX_STR_LEN] + "..."
    return s

def _print_variables(var_dict, title="Variables"):
    """Helper to print a dictionary of variables."""
    if not var_dict:
        return
    print(f"    {title}:")
    for name, value in var_dict.items():
        print(f"      {name}: {_format_value(value)}")

def custom_detailed_excepthook(exc_type, exc_value, exc_tb):
    """
    Custom excepthook to print detailed debug information for each frame.
    """
    print("=" * 80)
    print("DETAILED TRACEBACK (most recent call last):")
    print("=" * 80)

    # Use traceback module to format the exception part
    # This gives us the standard "Traceback (most recent call last):"
    # and the exception type and message.
    # We'll print our detailed frames first, then the standard summary.

    # Iterate through the traceback frames
    current_tb = exc_tb
    frame_summaries = []

    while current_tb:
        frame = current_tb.tb_frame
        lineno = current_tb.tb_lineno # More accurate for the specific line in this frame
        code = frame.f_code
        filename = code.co_filename
        func_name = code.co_name

        frame_info = f"  File \"{filename}\", line {lineno}, in {func_name}\n"

        # 1. Source Code Snippet
        source_code_snippet = "    Source Code:\n"
        try:
            lines, start_line = inspect.getsourcelines(frame)
            # tb_lineno is 1-based, list indices are 0-based
            # start_line is the line number of the first line of the code object
            current_line_in_source_array = lineno - start_line

            start = max(0, current_line_in_source_array - CONTEXT_LINES)
            end = min(len(lines), current_line_in_source_array + CONTEXT_LINES + 1)

            for i, line_content in enumerate(lines[start:end]):
                actual_line_no = start_line + start + i
                prefix = "  --> " if actual_line_no == lineno else "      "
                source_code_snippet += f"      {prefix}{actual_line_no:4}: {line_content.rstrip()}\n"
        except (OSError, TypeError): # OSError if file not found, TypeError if e.g. eval/exec
            source_code_snippet += "      <Source code not available>\n"
        frame_info += source_code_snippet

        # 2. Local Variables
        locals_info = "    Local Variables:\n"
        if frame.f_locals:
            for name, value in frame.f_locals.items():
                if name.startswith("__") and name.endswith("__"): # Skip dunder_locals
                    continue
                locals_info += f"      {name}: {_format_value(value)}\n"
        else:
            locals_info += "      <No local variables>\n"
        frame_info += locals_info

        # 3. Arguments (if a function call)
        # inspect.getargvalues gets the names and values of arguments to a Python function.
        try:
            arg_info = inspect.getargvalues(frame)
            if arg_info.args or arg_info.varargs or arg_info.keywords:
                args_details = "    Arguments:\n"
                for arg_name in arg_info.args:
                    args_details += f"      {arg_name}: {_format_value(frame.f_locals.get(arg_name, '<N/A>'))}\n"
                if arg_info.varargs:
                    args_details += f"      *{arg_info.varargs}: {_format_value(frame.f_locals.get(arg_info.varargs, '<N/A>'))}\n"
                if arg_info.keywords:
                    # arg_info.keywords is the name of the **kwargs dict
                    kwargs_dict_name = arg_info.keywords
                    kwargs_dict = frame.f_locals.get(kwargs_dict_name, {})
                    if kwargs_dict:
                        args_details += f"      **{kwargs_dict_name}:\n"
                        for k, v_ in kwargs_dict.items():
                             args_details += f"        {k}: {_format_value(v_)}\n"
                    elif kwargs_dict_name in frame.f_locals: # if **kwargs was present but empty
                         args_details += f"      **{kwargs_dict_name}: {{}}\n"

                frame_info += args_details
        except Exception:
            pass # Ignore if arg parsing fails (e.g., not a standard function frame)


        # 4. Global Variables (Optional and Filtered)
        if SHOW_GLOBALS:
            globals_info = "    Global Variables (Filtered):\n"
            filtered_globals = {}
            for name, value in frame.f_globals.items():
                if FILTER_GLOBALS:
                    # Skip builtins, modules, functions, classes to reduce noise
                    if name.startswith("__") or inspect.ismodule(value) or \
                       inspect.isbuiltin(value) or inspect.isfunction(value) or \
                       inspect.isclass(value) :
                        continue
                filtered_globals[name] = value

            if filtered_globals:
                for name, value in filtered_globals.items():
                     globals_info += f"      {name}: {_format_value(value)}\n"
            else:
                globals_info += "      <No relevant global variables to display or all filtered>\n"
            frame_info += globals_info

        frame_summaries.append(frame_info)
        current_tb = current_tb.tb_next

    # Print frames in reverse order (most recent call last)
    for summary in reversed(frame_summaries):
        print(summary)
        print("-" * 60)

    # Print the standard exception message at the end
    print(f"{exc_type.__name__}: {exc_value}")
    print("=" * 80)

    # If you want the original traceback too, uncomment the next line
    # sys.__excepthook__(exc_type, exc_value, exc_tb)


def install_detailed_traceback():
    """Installs the custom detailed traceback handler."""
    sys.excepthook = custom_detailed_excepthook
    print("Detailed traceback handler installed.")

def uninstall_detailed_traceback():
    """Uninstalls the custom handler and restores the default."""
    sys.excepthook = sys.__excepthook__
    print("Detailed traceback handler uninstalled. Default restored.")


# --- Example Usage ---
def level_three(data_dict, factor, unused_arg="test"):
    print(f"Inside level_three with factor: {factor}")
    another_local = "I am in level three"
    # This will cause a KeyError
    return data_dict["non_existent_key"] * factor

def level_two(b, c):
    print(f"Inside level_two with b: {b}, c: {c}")
    my_data = {"value": 100, "name": "example"}
    complex_local = {"a": [1,2,3], "b": {"c": "deep"}}
    result = level_three(my_data, b + c)
    return result * 2

def level_one(a):
    print(f"Inside level_one with a: {a}")
    intermediate_val = a * 10
    # Let's make a long string
    long_string_local = "This is a very long string that should be truncated by the custom excepthook to avoid cluttering the output too much." * 3
    return level_two(intermediate_val, 5)

# Global variable for testing SHOW_GLOBALS
MY_GLOBAL_VAR = "This is a global test variable"
MY_GLOBAL_INT = 12345

if __name__ == "__main__":
    install_detailed_traceback()
    # To test SHOW_GLOBALS, change it at the top of the script
    # For example: SHOW_GLOBALS = True

    print("Running test program that will cause an error...\n")
    try:
        final_result = level_one(2)
        print(f"Final result: {final_result}") # This won't be reached
    except Exception as e:
        # The custom excepthook will handle unhandled exceptions.
        # If we catch it here, the excepthook won't be called unless we re-raise.
        # For testing, we let it propagate by not having a broad except clause
        # or by re-raising if we did want to do something first.
        # print(f"Caught an exception: {e}") # This would prevent excepthook
        pass # Let the excepthook handle it

    # Test with a different error
    print("\nRunning another test (ZeroDivisionError)...\n")
    try:
        x = 10
        y = 0
        z = x / y
    except ZeroDivisionError: # This will be caught by our excepthook
        pass

    # uninstall_detailed_traceback() # Optionally restore default