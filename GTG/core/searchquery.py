"""
An saved search query.
It consists of the search query itself, an user-specified name and an icon.

In early versions of GTG internally it was actually an tag, but this caused
some problems especially together with tasks.
"""

import uuid
import xml.sax.saxutils as saxutils
import re

from liblarch import TreeNode
from functools import reduce
