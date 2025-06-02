import sys
import json
import inspect

# --- Program to be Traced ---
def greet(name):
    '''A simple function that greets and calls another function.'''
    message = f"Hello, {name}!"
    print_message(message) # Call to another function
    return message

def print_message(msg):
    '''A simple function that prints a message.'''
    print(f"Output: {msg}")

def sample_main():
    '''Main function for the program to be traced.'''
    print("Starting sample_main...")
    greet("World")
    greet("Python User")
    print("Finished sample_main.")

# --- Tracer Implementation ---
trace_log = [] # Global list to store trace events

def json_tracer(frame, event, arg):
    '''
    Trace function that captures 'call' events and stores them in trace_log.
    '''
    if event == 'call':
        func_name = frame.f_code.co_name
        line_no = frame.f_lineno

        # Get argument names and their current values
        arg_info = inspect.getargvalues(frame)
        args_dict = {}
        for arg_name in arg_info.args:
            try:
                args_dict[arg_name] = frame.f_locals[arg_name]
            except KeyError:
                # Handle cases where an arg might not be in f_locals immediately (less common for 'call')
                args_dict[arg_name] = "<value not available>"

        trace_event = {
            "event_type": event,
            "function_name": func_name,
            "line_number": line_no,
            "arguments": args_dict,
            "source_file": frame.f_code.co_filename # Added source file for more context
        }
        trace_log.append(trace_event)

    return json_tracer # Must return itself to continue tracing

# --- Main Execution Block ---
if __name__ == "__main__":
    print("Setting up tracer...")
    sys.settrace(json_tracer)

    # Run the main function of the program to be traced
    sample_main()

    print("Disabling tracer...")
    sys.settrace(None) # Important to disable the tracer

    # Convert the trace log to JSON and print it
    print("\n--- JSON Trace Output ---")
    json_output = json.dumps(trace_log, indent=4)
    print(json_output)

    print("\n--- End of Demo ---")
