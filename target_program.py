# python -m pdb target_program.py
def simple_function(a, b):
    x = a + b
    y = x * 2
    z = y - a
    return z

result = simple_function(5, 10)
print(f"Final result: {result}")
