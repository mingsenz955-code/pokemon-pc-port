"""Native GNU integer unordered_map node order for original event regions.

VillageMapControler ctor 0x2db144 requests 10 buckets (prime 11);
createAreaSprite 0x2de4ec inserts IDs, getAreaSpriteAtTileCoord 0x2d8eca
walks hash nodes. XML order is not the original overlap priority.
"""
import math


def native_area_order(objects):
    buckets, nodes = 11, []

    def insert(result, obj, count):
        bucket = int(obj['name']) % count
        index = next((i for i, row in enumerate(result) if int(row['name']) % count == bucket), 0)
        result.insert(index, obj)

    for obj in objects:
        if obj['group'] != 'eventLayer':
            continue
        nodes[:] = [row for row in nodes if row['name'] != obj['name']]
        if len(nodes)+1 > buckets:
            candidate = 2*buckets+1
            while any(candidate % divisor == 0 for divisor in range(2, math.isqrt(candidate)+1)):
                candidate += 2
            buckets = candidate
            old, nodes = nodes, []
            for row in old:
                insert(nodes, row, buckets)
        insert(nodes, obj, buckets)
    return nodes
