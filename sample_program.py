def greet(name):
    message = f"Hello, {name}!"
    print_message(message)
    return message

def print_message(msg):
    print(msg)

def main():
    greet("World")
    greet("Python")
