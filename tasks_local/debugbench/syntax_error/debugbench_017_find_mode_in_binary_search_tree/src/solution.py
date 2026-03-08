from typing import *
from collections import *
from functools import *
import math
import heapq
import bisect

class Solution:
    def findMode(self, root: Optional[TreeNode]) -> List[int]:
        def bfs(freq):
            queue = [root]
            while queue:
                curr= queue.pop()
                if curr.left:
                    queue.append(curr.left)
                if curr.right:
                    queue.append(curr.right)
                freq.setdefault(curr.val, 0)
                freq[curr.val] += 1

        freq = {}
        bfs(freq)
        freq = freq.items()
        ans = []
        max_cnt = 0

        for num, cnt in freq
            if cnt > max_cnt:
                max_cnt = cnt

        for num, cnt in freq:
            if cnt == max_cnt:
                ans.append(num)
        return ans
