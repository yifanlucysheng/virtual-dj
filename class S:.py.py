class B:
    def __init__(self, M):
        self.M = M

    def __repr__(self):
        return f'B(M={self.M})'

    def f(self, other):
        N = other.M + self.M
        return B(N)

b1 = B([5])
b2 = B([2, 4])
b3 = b1.f(b2)
print(b3)
b4 = b2.f(b1)
print(b4)