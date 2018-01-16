import math
import hlt

def intersection(start, end, circle):
    try:
        m = (end.y - start.y) / (end.x - start.x)
    except ZeroDivisionError:
        m = 1000
    m_squared = m ** 2
    b = start.y - m * start.x
    D = (1 + m_squared) * circle.r ** 2 - (circle.y - m * circle.x - b) ** 2

    if D < 0:
        return []

    sqrt_D = math.sqrt(D)
    x1 = (circle.x + circle.y * m - b * m + sqrt_D) / (1 + m_squared)
    x2 = (circle.x + circle.y * m - b * m - sqrt_D) / (1 + m_squared)

    y1 = m * x1 + b
    y2 = m * x2 + b

    result = []
    if (y1 >= start.y and y1 <= end.y) or (y1 >= end.y and y1 <= start.y):
        result.append(hlt.entity.Position(x1, y1))

    if (y2 >= start.y and y2 <= end.y) or (y2 >= end.y and y2 <= start.y):
        result.append(hlt.entity.Position(x2, y2))

    return result

angle = 136
a = hlt.entity.Position(22.6, 124.1)
b = hlt.entity.Position(a.x + math.cos(math.radians(angle)) * 8.5, a.y + math.sin(math.radians(angle)) * 8.5)

c = hlt.entity.Position(61.5, 102.8)
c.r = 0.5 + 0.6
d = hlt.entity.Position(15.48, 132.35)
d.r = 5.2 + 0.6
print(intersection(a, b, c))
print(intersection(a, b, d))
# import time
# t = time.time()
# for i in range(100000):
#     intersection(a, b, c)
# print(time.time() - t)