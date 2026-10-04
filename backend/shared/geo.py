"""Distâncias em metros e GeoHash sem dependência de células externas."""
import math
import zlib

ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash(latitude, longitude, precision=5):
    bounds = [[-180.0, 180.0], [-90.0, 90.0]]
    value = bits = axis = 0
    result = ""
    while len(result) < precision:
        low, high = bounds[axis]
        middle = (low + high) / 2
        coordinate = longitude if axis == 0 else latitude
        upper = coordinate >= middle
        value = (value << 1) | int(upper)
        bounds[axis] = [middle, high] if upper else [low, middle]
        axis = 1 - axis
        bits += 1
        if bits == 5:
            result += ALPHABET[value]
            value = bits = 0
    return result


def partition(region_id, count):
    return zlib.crc32(region_id.encode("ascii")) % count


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b - a, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(h)))


def circle_polygon(latitude, longitude, radius_m, vertices=48):
    latitude, longitude = math.radians(latitude), math.radians(longitude)
    delta = radius_m / 6371008.8
    ring = []
    for step in range(vertices):
        bearing = 2 * math.pi * step / vertices
        lat = math.asin(math.sin(latitude) * math.cos(delta) + math.cos(latitude) * math.sin(delta) * math.cos(bearing))
        lon = longitude + math.atan2(math.sin(bearing) * math.sin(delta) * math.cos(latitude), math.cos(delta) - math.sin(latitude) * math.sin(lat))
        ring.append([math.degrees(lon), math.degrees(lat)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def covering_regions(latitude, longitude, radius_m, precision=5):
    # Precision 5: 13 longitude bits and 12 latitude bits. Cover full bounding
    # box, including adjacent cells; final selection always checks true radius.
    lon_bits = math.ceil(precision * 5 / 2)
    lat_bits = precision * 5 - lon_bits
    width, height = 360 / (2 ** lon_bits), 180 / (2 ** lat_bits)
    lat_delta = radius_m / 110574
    lon_delta = radius_m / max(1, 111320 * math.cos(math.radians(latitude)))
    if lon_delta > 20:
        raise ValueError("Área próxima aos polos não é suportada nesta demonstração")
    minlat, maxlat = max(-90, latitude - lat_delta), min(90, latitude + lat_delta)
    minlon, maxlon = longitude - lon_delta, longitude + lon_delta
    cells = set()
    for ilat in range(math.floor((minlat + 90) / height), math.floor((maxlat + 90) / height) + 1):
        for ilon in range(math.floor((minlon + 180) / width), math.floor((maxlon + 180) / width) + 1):
            lat = min(89.99999, -90 + (ilat + 0.5) * height)
            lon = (-180 + (ilon + 0.5) * width + 180) % 360 - 180
            cells.add(geohash(lat, lon, precision))
    return sorted(cells)
