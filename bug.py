import detailed_tb
detailed_tb.install_detailed_traceback()

class ComplexCalculator:
    def __init__(self, initial_value):
        self.value = initial_value

    def nested_operation(self, x):
        # This will cause an index error
        dummy_list = [1, 2, 3]
        return dummy_list[x] * self.value

    def complex_math(self, x):
        try:
            result = self.nested_operation(x)
            # This will never execute if x >= 3
            return result / 0
        except IndexError as e:
            # This will cause a type error
            return "error" + 5

def recursive_function(n):
    if n < 0:
        # This will cause a recursion error
        return recursive_function(n + 1) * recursive_function(n + 2)
    return n

def my_complicated_function(x):
    calc = ComplexCalculator(x)

    # This will trigger multiple exceptions in the call stack
    intermediate = calc.complex_math(5)

    # These lines won't execute but add complexity to traceback
    final_result = recursive_function(intermediate)
    return final_result / 0

# This will generate a complex traceback with multiple exceptions
my_complicated_function(10)
