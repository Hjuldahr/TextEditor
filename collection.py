from __future__ import annotations
from typing import Any, Iterable

class OrderedSet:
    def __init__(self, iterable: Iterable):
        """A collection of unique elements.
        If a matching element is already in the collection, it gets replaced by the new element."""
        self.elements = []
        self.update(iterable)

    def add(self, elem: Any):
        """Adds an element to the end of the collection. 
        If a matching element is already in the collection, it gets replaced by the new element."""
        # bubble to top if already in elements
        if elem in self.elements: 
            self.elements.remove(elem)
        self.elements.append(elem)
        
    def update(self, iterable: Iterable):
        """Executes add() for each element of the iterable"""
        for elem in iterable:
            self.add(elem)
        
    def clear(self):
        """Removes all elements"""
        self.elements.clear()
        
    def reverse(self):
        """Reverses the order of the elements in place"""
        self.elements.reverse()
        
    def copy(self) -> OrderedSet:
        """Creates a deep copy"""
        return OrderedSet(self.elements) 
    
    def _normalize(self, other: set | tuple | list | OrderedSet) -> set:
        if isinstance(other, set):
            return other
        elif isinstance(other, (tuple, list, OrderedSet)):
            return set(other)
        raise TypeError("Other must be type of Tuple, List, Set or OrderedSet")
    
    def intersection(self, other: set | tuple | list | OrderedSet) -> set:
        """Return a new set with elements common to the set and all others."""
        return set(self).intersection(self._normalize(other))
    
    def difference(self, other: set | tuple | list | OrderedSet) -> set:
        """Return a new set with elements in the set that are not in the others."""
        return set(self).difference(self._normalize(other))
    
    def issubset(self, other: set | tuple | list | OrderedSet) -> bool:
        """Report whether this set contains another set."""
        return set(self).issubset(self._normalize(other))
    
    def issuperset(self, other: set | tuple | list | OrderedSet) -> bool:
        """Report whether this set contains another set."""
        return set(self).issuperset(self._normalize(other))
    
    def isdisjoint(self, other: set | tuple | list | OrderedSet) -> bool:
        """Return True if two sets have a null intersection."""
        return set(self).isdisjoint(self._normalize(other))
    
    def __str__(self) -> str:
        return f'{{{", ".join(self.elements)}}}'
    
    def __repr__(self) -> str:
        return f'OrderedSet({", ".join(self.elements)})'
        
    def __getitem__(self, i: int) -> Any:
        return self.elements[i]
    
    def __setitem__(self, i: int, value: Any):
        if value in self.elements:
            # Swap the existing value with the one at index i
            old_idx = self.elements.index(value)
            self.elements[i], self.elements[old_idx] = self.elements[old_idx], self.elements[i]
        else:
            # Standard replacement if it's a brand new value
            self.elements[i] = value
        
    def __iter__(self):
        return iter(self.elements)