def interleave_arrays(arrays):
    """
    Interleave multiple arrays into a single array, maintaining the order of elements,
    and deduplicate items while preserving the order of first appearance.
    """
    from itertools import zip_longest
    seen = set()
    result = []
    for group in zip_longest(*arrays, fillvalue=None):
        for item in group:
            if item is not None and item not in seen:
                seen.add(item)
                result.append(item)
    return result