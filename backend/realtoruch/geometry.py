"""Bounded, validated map polygons shared by SQL search and alert matching."""

import json
import math

from sqlalchemy import and_, case, or_

MAX_VERTICES = 64
EPSILON = 1e-9


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def on_segment(a, b, p):
    return abs(cross(a, b, p)) <= EPSILON and all(
        min(a[i], b[i]) - EPSILON <= p[i] <= max(a[i], b[i]) + EPSILON for i in (0, 1)
    )


def intersects(a, b, c, d):
    sides = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    return (sides[0] * sides[1] < 0 and sides[2] * sides[3] < 0) or any(
        on_segment(x, y, p) for x, y, p in ((a, b, c), (a, b, d), (c, d, a), (c, d, b))
    )


def parse_polygon(value):
    try:
        points = json.loads(value)
        if not isinstance(points, list) or not 3 <= len(points) <= MAX_VERTICES + 1:
            raise ValueError()
        if any(not isinstance(p, list) or len(p) != 2 for p in points):
            raise ValueError()
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for p in points
            for v in p
        ):
            raise ValueError()
        points = [tuple(p) for p in points]
        if points[0] == points[-1]:
            points.pop()
        if not 3 <= len(points) <= MAX_VERTICES or len(set(points)) != len(points):
            raise ValueError()
        if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in points):
            raise ValueError()
        if max(p[0] for p in points) - min(p[0] for p in points) > 180:
            raise ValueError()
        edges = list(zip(points, points[1:] + points[:1]))
        if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < EPSILON:
            raise ValueError()
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if intersects(a, b, c, d):
                    raise ValueError()
        return points
    except (TypeError, ValueError, OverflowError):
        raise ValueError("polygon must be a simple ring of 3–64 [longitude,latitude] points") from None


def polygon_sql(longitude, latitude, points):
    """Bounding-box pruning plus exact ray casting; works on SQLite and PostgreSQL."""
    crossings, boundary = [], []
    for a, b in zip(points, points[1:] + points[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        determinant = dx * (latitude - a[1]) - dy * (longitude - a[0])
        boundary.append(
            and_(
                determinant.between(-EPSILON, EPSILON),
                longitude.between(min(a[0], b[0]) - EPSILON, max(a[0], b[0]) + EPSILON),
                latitude.between(min(a[1], b[1]) - EPSILON, max(a[1], b[1]) + EPSILON),
            )
        )
        if dy:
            crossings.append(
                case(
                    (
                        and_(
                            latitude >= min(a[1], b[1]),
                            latitude < max(a[1], b[1]),
                            longitude < a[0] + (latitude - a[1]) * dx / dy,
                        ),
                        1,
                    ),
                    else_=0,
                )
            )
    return and_(
        longitude.between(min(p[0] for p in points), max(p[0] for p in points)),
        latitude.between(min(p[1] for p in points), max(p[1] for p in points)),
        or_(sum(crossings) % 2 == 1, *boundary),
    )
