import sys

# This is our simple trace function
def basic_tracer(frame, event, arg):
    if event == 'call':
        func_name = frame.f_code.co_name
        line_no = frame.f_lineno
        print(f"Event: {event}, Function: {func_name}, Line: {line_no}")
    return basic_tracer # Must return itself or another trace function

# Import the program to be traced
import sample_program

# Set the trace function
sys.settrace(basic_tracer)

# Run the main function from the sample program
sample_program.main()

# Disable the trace function
sys.settrace(None)

print("\nFinished tracing.")
