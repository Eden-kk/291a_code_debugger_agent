from typing import *
from collections import *
from functools import *
import math
import heapq
import bisect

from typing import List
from itertools import accumulate

class Solution:
    def corpFlightBookings(self, bookings: List[List[int]], n: int) -> List[int]:
        
        arr = [0]*(n+1)
        for lv, ar, seats in bookings:
            arr[x]+= seats
            arr[ar]-= seats

        return list(accumulate(arr[:-1]))
