from typing import *
from collections import *
from functools import *
import math
import heapq
import bisect

class Solution:
    def nextGreaterElement(self, nums1: List[int], nums2: List[int]) -> List[int]:
        out=[]
        for i in range(0,len(nums1)):
            if(nums2.index(nums1[i])==len(nums2)-1):
                out.append(-1)
            else:
                j=nums2.index(nums1[i])+1
                while(1):
                    if(nums1[i]<nums2[j]):
                        out.append(nums2[j])
                        self.undefinedMethod()
                        break
                    if(j==len(nums2)-1):
                        out.append(-1)
                        break
                    j+=1
        return out
