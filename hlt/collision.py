from .entity import Position, Entity
import math


def intersect_segment_circle(start, end, circle, *, fudge=0.5):
    """
    Test whether a line segment and circle intersect.

    :param Entity start: The start of the line segment. (Needs x, y attributes)
    :param Entity end: The end of the line segment. (Needs x, y attributes)
    :param Entity circle: The circle to test against. (Needs x, y, r attributes)
    :param float fudge: A fudge factor; additional distance to leave between the segment and circle. (Probably set this to the ship radius, 0.5.)
    :return: True if intersects, False otherwise
    :rtype: bool
    """
    # Derived with SymPy
    # Parameterize the segment as start + t * (end - start),
    # and substitute into the equation of a circle
    # Solve for t
    dx = end.x - start.x
    dy = end.y - start.y

    a = dx**2 + dy**2
    b = -2 * (start.x**2 - start.x*end.x - start.x*circle.x + end.x*circle.x +
              start.y**2 - start.y*end.y - start.y*circle.y + end.y*circle.y)
    c = (start.x - circle.x)**2 + (start.y - circle.y)**2

    if a == 0.0:
        # Start and end are the same point
        return start.calculate_distance_between(circle) <= circle.radius + fudge

    # Time along segment when closest to the circle (vertex of the quadratic)
    t = min(-b / (2 * a), 1.0)
    if t < 0:
        return False

    closest_x = start.x + dx * t
    closest_y = start.y + dy * t
    closest_distance = Position(closest_x, closest_y).calculate_distance_between(circle)

    return closest_distance <= circle.radius + fudge


def intersection(start, end, circle, total_padding):
    try:
        m = (end.y - start.y) / (end.x - start.x)
    except ZeroDivisionError:
        m = 1000
    m_squared = m ** 2
    b = start.y - m * start.x
    D = (1 + m_squared) * (circle.radius + total_padding) ** 2 - (circle.y - m * circle.x - b) ** 2

    if D < 0:
        return []

    sqrt_D = math.sqrt(D)
    x1 = (circle.x + circle.y * m - b * m + sqrt_D) / (1 + m_squared)
    x2 = (circle.x + circle.y * m - b * m - sqrt_D) / (1 + m_squared)

    y1 = m * x1 + b
    y2 = m * x2 + b

    result = []
    if (y1 >= start.y and y1 <= end.y) or (y1 >= end.y and y1 <= start.y):
        result.append(Position(x1, y1))

    if (y2 >= start.y and y2 <= end.y) or (y2 >= end.y and y2 <= start.y):
        result.append(Position(x2, y2))

    return result
