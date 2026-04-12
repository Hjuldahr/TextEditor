class Object():
    def __init__(self, entries: dict = None):
        self.entries = entries or dict()

obj = Object()
obj.a = 12
print(obj['a'])