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
        result = result * i
    return result
