from typing import *
from collections import *
from functools import *
import math
import heapq
import bisect

class Solution:
    def minBitFlips(self, start: int, goal: int) -> int:
    s=bin(start)[2:].zfill(50)
        g=bin(goal)[2:].zfill(50)
        count=0
        for i in range(50):
            if s[i]!=g[i]:
                count+=1
    return count
