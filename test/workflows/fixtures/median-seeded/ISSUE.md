# median() is wrong for even-length input

`median([1, 2, 3, 4])` returns `3.0`. The median of an even-length sample is the mean of the two
middle values, so the correct answer is `2.5`.

Odd-length input looks right, which is why this survived review.
