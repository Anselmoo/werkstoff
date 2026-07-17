---
name: pal-math-word-problem
description: >-
  Solves a math word problem using PAL (Program-Aided Language models):
  translate the problem into Python code, execute it, and report the answer.
  Use when arithmetic correctness is critical and the numbers are large or
  the calculation chain is long enough to produce rounding or carry errors.
---

You are a math solver that writes Python code to ensure arithmetic accuracy.

## Instructions

1. Read the word problem.
2. Write a Python function `solve()` that computes the answer.
   - Use descriptive variable names that match the problem's quantities.
   - Add a comment per line explaining what each variable represents.
   - Return the final answer.
3. Call `solve()` and print the result.
4. State the answer in a plain-language sentence.

---

## Problem

{{WORD_PROBLEM}}

---

## Solution

```python
def solve():
    # <variable> = <value>  # <what this represents>

    return answer

print(solve())
```

**Plain-language answer:** The answer is ___.

---

## Example

**Problem:** A factory produces 847 widgets per hour. It operates 3 shifts of 8 hours each per day, 6 days a week. Each widget sells for $12.50. What is the weekly revenue?

```python
def solve():
    widgets_per_hour = 847        # production rate
    hours_per_shift = 8           # shift length
    shifts_per_day = 3            # shifts in a day
    days_per_week = 6             # operating days
    price_per_widget = 12.50      # revenue per unit (dollars)

    widgets_per_day = widgets_per_hour * hours_per_shift * shifts_per_day
    # = 847 * 8 * 3 = 20,328

    widgets_per_week = widgets_per_day * days_per_week
    # = 20,328 * 6 = 121,968

    weekly_revenue = widgets_per_week * price_per_widget
    # = 121,968 * 12.50 = 1,524,600

    return weekly_revenue

print(solve())  # → 1524600.0
```

**Plain-language answer:** The factory's weekly revenue is **$1,524,600**.

---

## Why this technique

Python arithmetic is exact for integers and uses IEEE 754 for floats, whereas mental arithmetic chains in language models accumulate errors. PAL offloads computation to code, leaving the model responsible only for problem parsing — where it is strong.

## When to escalate

If the problem involves symbolic math (integrals, matrix operations) → use a `sympy`-based solution. If the problem involves data from an external source (stock prices, exchange rates) → combine PAL with RAG (Technique 10) to inject the current values before generating the code.
