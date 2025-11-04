<<<<<<< HEAD
def fibonacci(n):
    """Calculate the nth Fibonacci number using iteration"""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def factorial(n):
    """Calculate factorial recursively"""
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)
||| base
def fibonacci(n):
    """Calculate the nth Fibonacci number using memoization"""
    memo = {}
    def fib_helper(k):
        if k in memo:
            return memo[k]
        if k <= 1:
            return k
        memo[k] = fib_helper(k - 1) + fib_helper(k - 2)
        return memo[k]
    return fib_helper(n)

def factorial(n):
    """Calculate factorial iteratively"""
    result = 1
    for i in range(1, n + 1):
        result = i
    return result
=======
def fibonacci(n):
    """Calculate the nth Fibonacci number using matrix exponentiation"""
    import numpy as np

    def matrix_mult(A, B):
        return [[A[0][0]B[0][0] + A[0][1]B[1][0], A[0][0]B[0][1] + A[0][1]B[1][1]],
                [A[1][0]B[0][0] + A[1][1]B[1][0], A[1][0]B[0][1] + A[1][1]B[1][1]]]

    def matrix_pow(M, exp):
        result = [[1, 0], [0, 1]]  # Identity matrix
        while exp > 0:
            if exp % 2 == 1:
                result = matrix_mult(result, M)
            M = matrix_mult(M, M)
            exp //= 2
        return result

    if n <= 1:
        return n

    F = [[1, 1], [1, 0]]
    result = matrix_pow(F, n - 1)
    return result[0][0]

def factorial(n):
    """Calculate factorial using reduce"""
    from functools import reduce
    return reduce(lambda x, y: x y, range(1, n + 1), 1) if n > 0 else 1
>>>>>>> branch