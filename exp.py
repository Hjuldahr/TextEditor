import collections
import numbers
from typing import Any, Callable


class Dictionary:
    def __init__(self, *args, **kwargs):
        self.key_val_pairs = {}
        if args or kwargs:
            self.putAll(*args, **kwargs)

            if kwargs:
                self.key_val_pairs.update(kwargs)
    
    def clear(self):
        self.key_val_pairs.clear()
        
    def clone(self):
        return Dictionary(self)
    
    def _set_key_val(self, key, value):
        if value is not None:
            self.key_val_pairs[key] = value
        else:
            self.key_val_pairs.pop(key, None)
    
    def compute(self, key: Any, bi_func: Callable):
        old_value = self.key_val_pairs.get(key, None)
        
        new_value = bi_func(key, old_value)
        self._set_key_val(key, new_value)
        
        return old_value
    
    def computeIfAbsent(self, key: Any, func: Callable):
        old_value = self.key_val_pairs.get(key, None)
        
        if old_value is None:
            new_value = func(key)
            self._set_key_val(key, new_value)
            
        return old_value
                
    def computeIfPresent(self, key: Any, bi_func: Callable) -> Any:
        old_value = self.key_val_pairs.get(key, None)
        
        if old_value is not None:
            new_value = bi_func(key, old_value)
            self._set_key_val(key, new_value)
            
        return old_value
    
    def containsKey(self, key: Any) -> bool:
        return key in self.key_val_pairs.keys()
    
    def containsValue(self, value: Any) -> bool:
        return value in self.key_val_pairs.values()
    
    def items(self):
        return self.key_val_pairs.items()
    
    def forEach(self, bi_func: Callable) -> None:
        for k, v in self.key_val_pairs.items():
            self.key_val_pairs[k] = bi_func(k, v)
            
    def get(self, key: Any, default: Any=None):
        return self.key_val_pairs.get(key, default)
    
    def isEmpty(self) -> bool:
        return len(self.key_val_pairs) == 0
    
    def isNotEmpty(self) -> bool:
        return len(self.key_val_pairs) != 0
    
    def keys(self):
        return self.key_val_pairs.keys()
    
    def merge(self, key: Any, value: Any, bi_func: Callable) -> Any:
        old_value = self.key_val_pairs.get(key)
        
        if key in self.key_val_pairs:
            self.key_val_pairs[key] = bi_func(self.key_val_pairs[key], value)
        else:
            self.key_val_pairs[key] = value
            
        return old_value
            
    def put(self, key: Any, value: Any) -> Any:
        old_value = self.key_val_pairs.get(key)
        
        self.key_val_pairs[key] = value
        
        return old_value
    
    def putAll(self, *args, **kwargs) -> None:
        if args:
            data = args[0]
            if isinstance(data, Dictionary):
                self.key_val_pairs.update(data.key_val_pairs)
            elif isinstance(data, collections.abc.Mapping):
                self.key_val_pairs.update(data)
            else:
                try:
                    self.key_val_pairs.update(data)
                except (TypeError, ValueError):
                    raise ValueError(f"Dictionary.putAll expected a mapping or iterable of pairs, got '{type(data).__name__}'")

        if kwargs:
            self.key_val_pairs.update(kwargs)
            
    def putIfAbsent(self, key: Any, value: Any) -> Any:
        old_value = self.key_val_pairs.get(key)
        
        if old_value is None:
            self.key_val_pairs[key] = value
            
        return old_value
        
    def putIfPresent(self, key: Any, value: Any) -> Any:
        old_value = self.key_val_pairs.get(key)
        
        if old_value is not None:
            self.key_val_pairs[key] = value
            
        return old_value
    
    def remove(self, key: Any) -> Any:
        return self.key_val_pairs.pop(key, None)
    
    def removeByValue(self, value: Any) -> bool:
        new_key_val_pairs = {k: v for k, v in self.key_val_pairs.items() if v != value}
        changed = len(self.key_val_pairs) != len(new_key_val_pairs)
        self.key_val_pairs = new_key_val_pairs
        return changed
    
    def removeByEntry(self, key: Any, value: Any) -> bool:
        current_value = self.key_val_pairs.get(key)
        
        if current_value == value:
            self.key_val_pairs.pop(key, None)
            return True
        return False
    
    def replace(self, key: Any, value: Any):
        old_value = self.key_val_pairs.get(key)
        
        self.key_val_pairs[key] = value
        
        return old_value
    
    def replaceByEntry(self, key: Any, old_value: Any, new_value: Any):
        current_value = self.key_val_pairs.get(key)
        
        if current_value == old_value:
            self.key_val_pairs[key] = new_value
            return True
        return False
    
    def replaceAll(self, bi_func: Callable) -> None:
        self.key_val_pairs = {k: bi_func(k, v) for k, v in self.key_val_pairs.items()}
        
    def size(self) -> int:
        return len(self.key_val_pairs)
    
    def values(self):
        return self.key_val_pairs.values()
    
    # ------------------------------------
    
    def __len__(self):
        return len(self.key_val_pairs)
    
    def __iter__(self):
        return iter(self.key_val_pairs)
    
    def __str__(self):
        return str(self.key_val_pairs)
    
    def __getitem__(self, key: Any):
        return self.get(key)
    
    def __setitem__(self, key: Any, value: Any):
        self.put(key, value)
        
    def __contains__(self, item) -> bool:
        return item in self.key_val_pairs
    
    def __eq__(self, other: Any):
        if isinstance(other, Dictionary):
            return self.key_val_pairs.items() == other.key_val_pairs.items()
        
        if isinstance(other, dict):
            return self.key_val_pairs.items() == other.items()
        
        raise TypeError(f"TypeError: unsupported operand type(s) for 'Dictionary' and '{type(other).__name__}'")
    
    def __iadd__(self, other):
        if isinstance(other, Dictionary):
            self.key_val_pairs.update(other.key_val_pairs)
            return self
        
        if isinstance(other, dict):
            self.key_val_pairs.update(other)
            return self
        
        raise TypeError(f"TypeError: unsupported operand type(s) for 'Dictionary' and '{type(other).__name__}'")
    
    def __isub__(self, other):
        if isinstance(other, Dictionary):
            self.key_val_pairs = {k: v for k, v in self.key_val_pairs.items() if k not in other.key_val_pairs.keys()}
            return self
        
        if isinstance(other, dict):
            self.key_val_pairs = {k: v for k, v in self.key_val_pairs.items() if k not in other.keys()}
            return self
        
        raise TypeError(f"TypeError: unsupported operand type(s) for 'Dictionary' and '{type(other).__name__}'")
    
    def __abs__(self):
        new_key_val_pairs = {}
        for k, v in self.key_val_pairs.items():
            if isinstance(v, numbers.Number):
                new_key_val_pairs[k] = abs(v)
            elif isinstance(v, str):
                new_key_val_pairs[k] = v.upper()
            else:
                new_key_val_pairs[k] = v
            
        return Dictionary(new_key_val_pairs)
    
    def __repr__(self):
        return f"Dictionary({self.key_val_pairs})"