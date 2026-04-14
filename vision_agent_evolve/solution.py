from sympy import symbols, Eq, solve, sqrt, I
def solution():
    x = symbols('x')
    # The equation from the image is (x - sqrt(2))^2 + 4*sqrt(2)*x = 0
    equation = Eq((x - sqrt(2))**2 + 4*sqrt(2)*x, 0)
    solutions = solve(equation, x)
    return str(solutions)
