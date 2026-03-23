# Runtime hook to fix uvicorn typing issues in Python 3.13
import sys
from types import ModuleType

# Patch collections.abc to allow subscripting
if sys.version_info >= (3, 9):
    import collections.abc
    for name in ['Mapping', 'MutableMapping', 'Sequence', 'MutableSequence', 
                 'Set', 'MutableSet', 'Iterable', 'Iterator']:
        if hasattr(collections.abc, name):
            cls = getattr(collections.abc, name)
            if not hasattr(cls, '__class_getitem__'):
                cls.__class_getitem__ = classmethod(lambda cls, params: cls)
