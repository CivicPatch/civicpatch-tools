def interleave_arrays(arrays):
    """
    Interleave multiple arrays into a single array, maintaining the order of elements.
    If arrays are of different lengths, the shorter ones will be padded with None.
    
    Args:
        *arrays: Variable number of arrays to interleave.
        
    Returns:
        A single list containing elements from all input arrays interleaved.
    """
    from itertools import zip_longest
    return [item for sublist in zip_longest(*arrays, fillvalue=None) for item in sublist if item is not None]