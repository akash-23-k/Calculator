"""
Simple Command-Line Calculator
Supports +, -, *, / operations with input validation and error handling
"""

def add(a, b):
    """Add two numbers"""
    return a + b

def subtract(a, b):
    """Subtract b from a"""
    return a - b

def multiply(a, b):
    """Multiply two numbers"""
    return a * b

def divide(a, b):
    """Divide a by b with zero-division handling"""
    if b == 0:
        raise ValueError("Error: Division by zero is not allowed")
    return a / b

def clear():
    """Clear/reset the calculator"""
    print("\nCalculator cleared!")
    return None

def parse_input(user_input):
    """
    Parse user input to extract numbers and operator
    Returns: (num1, operator, num2) or None if invalid
    """
    user_input = user_input.strip()
    
    # Find the operator
    operators = ['+', '-', '*', '/']
    operator = None
    operator_index = -1
    
    # Search for operator (skip first character to handle negative numbers)
    for i in range(1, len(user_input)):
        if user_input[i] in operators:
            operator = user_input[i]
            operator_index = i
            break
    
    if operator is None:
        return None
    
    # Extract numbers
    try:
        num1_str = user_input[:operator_index].strip()
        num2_str = user_input[operator_index + 1:].strip()
        
        if not num1_str or not num2_str:
            return None
        
        num1 = float(num1_str)
        num2 = float(num2_str)
        
        return (num1, operator, num2)
    except ValueError:
        return None

def calculate(num1, operator, num2):
    """
    Perform calculation based on operator
    Returns: result or None if error
    """
    try:
        if operator == '+':
            return add(num1, num2)
        elif operator == '-':
            return subtract(num1, num2)
        elif operator == '*':
            return multiply(num1, num2)
        elif operator == '/':
            return divide(num1, num2)
        else:
            return None
    except ValueError as e:
        print(f"\n{e}")
        return None

def display_menu():
    """Display the calculator menu"""
    print("\n" + "="*50)
    print("         SIMPLE CALCULATOR")
    print("="*50)
    print("\nSupported Operations:")
    print("  • Addition       : a + b")
    print("  • Subtraction    : a - b")
    print("  • Multiplication : a * b")
    print("  • Division       : a / b")
    print("\nCommands:")
    print("  • 'clear' - Clear calculator")
    print("  • 'exit'  - Exit calculator")
    print("="*50)

def main():
    """Main calculator loop"""
    display_menu()
    
    while True:
        print("\nEnter calculation (e.g., 5 + 3) or command:")
        user_input = input(">>> ").strip().lower()
        
        # Handle commands
        if user_input == 'exit':
            print("\nThank you for using the calculator. Goodbye!")
            break
        
        if user_input == 'clear':
            clear()
            continue
        
        if not user_input:
            print("Error: Please enter a valid calculation or command")
            continue
        
        # Parse and validate input
        parsed = parse_input(user_input)
        
        if parsed is None:
            print("Error: Invalid input format")
            print("Please use format: number operator number (e.g., 5 + 3)")
            continue
        
        num1, operator, num2 = parsed
        
        # Perform calculation
        result = calculate(num1, operator, num2)
        
        if result is not None:
            print(f"\nResult: {num1} {operator} {num2} = {result}")

if __name__ == "__main__":
    main()
