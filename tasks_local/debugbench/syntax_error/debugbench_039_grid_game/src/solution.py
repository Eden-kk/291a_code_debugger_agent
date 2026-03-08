from typing import *
from collections import *
from functools import *
import math
import heapq
import bisect

class Solution:
def gridGame(self, grid: List[List[int]]) -> int: 
    result = float("inf")
    left,right = 0,sum(grid[0])

    for a,b in zip(grid[0],grid[1]):
        right-=a

        result = min(result,max(left,right))
        left+=b

    return result

# time & space - O(n),O(1)
