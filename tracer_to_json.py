import sys
import json
import inspect # To get argument values

# List to store trace events
trace_log = []

def json_tracer(frame, event, arg):
    if event == 'call':
        func_name = frame.f_code.co_name
        line_no = frame.f_lineno

        # Get argument names and values
        arg_info = inspect.getargvalues(frame)
        args_dict = {arg_name: arg_info.locals[arg_name] for arg_name in arg_info.args}

        trace_event = {
            "event_type": event,
            "function_name": func_name,
            "line_number": line_no,
            "arguments": args_dict
        }
        trace_log.append(trace_event)

    return json_tracer

# Import the program to be traced
import sample_program

# Set the trace function
sys.settrace(json_tracer)

# Run the main function from the sample program
sample_program.main()

# Disable the trace function
sys.settrace(None)

# Convert the trace log to JSON and print it
json_output = json.dumps(trace_log, indent=4)
print("\nJSON Trace Output:")
print(json_output)

print("\nFinished tracing and formatting to JSON.")
