"""Example: Dynamic fan-out (map style) processing.

Demonstrates:
- fan_out helper to create tasks from iterable
- downstream aggregation waiting for dynamic expansion
"""

from __future__ import annotations

from auto_workflow import fan_out, flow, task


@task
def produce_numbers(n: int = 5):
    return list(range(1, n + 1))


@task
def square(x: int) -> int:
    return x * x


@task
def total(values: list[int]) -> int:
    return sum(values)


@flow
def squares_sum(n: int = 5):
    nums = produce_numbers(n)
    mapped = fan_out(square, nums)
    return total(mapped)


if __name__ == "__main__":
    print("Sum of squares:", squares_sum.run(6))
