# dump_pdb_context.py
import inspect
import json
import sys

def _safe_serialize(obj, max_depth=3, current_depth=0, visited_ids=None):
    """
    Safely serialize an object to a string, handling common types
    and preventing infinite recursion for complex or circular objects.
    Limits recursion depth and string length for individual items.
    """
    if visited_ids is None:
        visited_ids = set()

    obj_id = id(obj)
    if obj_id in visited_ids:
        return f"<Circular Reference: {type(obj).__name__} id={obj_id}>"

    visited_ids.add(obj_id)

    try:
        if current_depth > max_depth:
            return f"<Max Depth Exceeded: {type(obj).__name__}>"

        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, (list, tuple, set)):
            if not obj: return [] if isinstance(obj, list) else tuple() if isinstance(obj, tuple) else set()
            # Limit number of items shown for very long sequences
            max_items = 10
            truncated = len(obj) > max_items
            items_to_serialize = list(obj)[:max_items] if truncated else obj

            serialized_list = [
                _safe_serialize(item, max_depth, current_depth + 1, visited_ids.copy())
                for item in items_to_serialize
            ]
            if truncated:
                serialized_list.append(f"... ({len(obj) - max_items} more items)")
            return serialized_list
        elif isinstance(obj, dict):
            if not obj: return {}
            # Limit number of items shown for very large dicts
            max_items = 10
            truncated = len(obj) > max_items

            serialized_dict = {}
            count = 0
            for k, v in obj.items():
                if count >= max_items:
                    break
                serialized_dict[_safe_serialize(k, max_depth, current_depth + 1, visited_ids.copy())] = \
                    _safe_serialize(v, max_depth, current_depth + 1, visited_ids.copy())
                count += 1
            if truncated:
                serialized_dict["..."] = f"({len(obj) - max_items} more items)"
            return serialized_dict
        else:
            # For other objects, try to get __dict__ or a limited repr
            # Be careful with __repr__ as it can be very long or raise errors
            try:
                if hasattr(obj, '__dict__') and current_depth < max_depth : # Don't go too deep into object dicts
                    obj_dict = {k:v for k,v in obj.__dict__.items() if not k.startswith('__')}
                    return {
                        "__type__": type(obj).__name__,
                        "__module__": type(obj).__module__,
                        "__id__": id(obj),
                        "attributes": _safe_serialize(obj_dict, max_depth, current_depth + 1, visited_ids.copy())
                    }
                else:
                    s_repr = repr(obj)
                    max_repr_len = 200
                    if len(s_repr) > max_repr_len:
                        s_repr = s_repr[:max_repr_len] + "..."
                    return f"<{type(obj).__name__} object: {s_repr}> (id: {id(obj)})"

            except Exception as e:
                return f"<Error serializing {type(obj).__name__}: {e}>"
    finally:
        if obj_id in visited_ids: # Should always be true if added
            visited_ids.remove(obj_id)


def get_pdb_full_context(frame=None, include_globals=False, max_depth=2):
    """
    When called inside PDB, captures the current execution context.
    Collects information about the current frame and optionally globals.
    Args:
        frame: The frame to inspect. If None, inspects the caller's frame (pdb's context).
        include_globals: Whether to include global variables.
        max_depth: Max depth for serializing complex objects.
    """
    if frame is None:
        # Try to get the frame PDB is currently stopped at.
        # This is a bit of a hack. PDB stores its current frame in self.curframe.
        # We need to find the PDB instance.
        # This might not be robust if PDB's internal structure changes.
        try:
            # For Python 3.7+ pdb.Pdb is the class
            # For older, it might be bdb.Bdb
            pdb_instance = None
            # Walk up the stack to find a Pdb instance
            # This assumes `get_pdb_full_context` is called directly or one level down from pdb commands
            f = inspect.currentframe()
            while f:
                if 'self' in f.f_locals and isinstance(f.f_locals['self'], (sys.breakpointhook.__self__.__class__, __import__('pdb').Pdb)):
                    pdb_instance = f.f_locals['self']
                    break
                f = f.f_back

            if pdb_instance and hasattr(pdb_instance, 'curframe'):
                frame = pdb_instance.curframe
            else: # Fallback if PDB instance not found, use current frame's caller
                frame = inspect.currentframe().f_back
                if frame and frame.f_code.co_name == 'get_pdb_full_context': # if called directly
                    frame = frame.f_back # one more step up
                print("Warning: Could not reliably find PDB's current frame. Using caller's frame.", file=sys.stderr)

        except Exception as e:
            print(f"Warning: Error trying to find PDB frame: {e}. Using caller's frame.", file=sys.stderr)
            frame = inspect.currentframe().f_back # default to caller of this function
            if frame and frame.f_code.co_name == 'get_pdb_full_context':
                frame = frame.f_back


    if not frame:
        return {"error": "Could not determine the current frame."}

    context = {}

    # 1. Current location
    context['location'] = {
        'filename': frame.f_code.co_filename,
        'lineno': frame.f_lineno,
        'function': frame.f_code.co_name
    }

    # 2. Source code snippet (optional, can be large)
    try:
        lines, start_line = inspect.getsourcelines(frame)
        context['source_code_snippet'] = {
            'start_line': start_line,
            'lines': lines[max(0, frame.f_lineno - start_line - 5) : frame.f_lineno - start_line + 6] # 5 lines before, current, 5 after
        }
    except OSError:
        context['source_code_snippet'] = "Could not retrieve source code."


    # 3. Local variables
    context['locals'] = {}
    if frame.f_locals:
        for name, value in frame.f_locals.items():
            if name.startswith('__') and name.endswith('__'): # Skip most builtins/specials
                 if name not in ['__file__', '__name__', '__doc__', '__package__']: continue # keep some common ones
            context['locals'][name] = _safe_serialize(value, max_depth=max_depth)

    # 4. Arguments (if applicable)
    arg_info = inspect.getargvalues(frame)
    context['arguments'] = {}
    if arg_info.args:
        for arg_name in arg_info.args:
            context['arguments'][arg_name] = _safe_serialize(frame.f_locals.get(arg_name), max_depth=max_depth)
    if arg_info.varargs:
        context['arguments'][f'*{arg_info.varargs}'] = _safe_serialize(frame.f_locals.get(arg_info.varargs), max_depth=max_depth)
    if arg_info.keywords:
        context['arguments'][f'**{arg_info.keywords}'] = _safe_serialize(frame.f_locals.get(arg_info.keywords), max_depth=max_depth)


    # 5. Global variables (optional)
    if include_globals:
        context['globals'] = {}
        if frame.f_globals:
            # Filter out most builtins and modules from globals for brevity
            for name, value in frame.f_globals.items():
                if name.startswith('__') and name.endswith('__'): continue
                if inspect.ismodule(value): continue # Skip modules
                context['globals'][name] = _safe_serialize(value, max_depth=max_depth)

    # 6. Call Stack (simplified)
    context['call_stack'] = []
    temp_frame = frame
    frame_count = 0
    max_frames = 10 # Limit stack depth shown
    while temp_frame and frame_count < max_frames:
        context['call_stack'].append({
            'filename': temp_frame.f_code.co_filename,
            'lineno': temp_frame.f_lineno,
            'function': temp_frame.f_code.co_name
        })
        temp_frame = temp_frame.f_back
        frame_count += 1
    if temp_frame: # if more frames exist
        context['call_stack'].append(f"... ({inspect.getouterframes(temp_frame, 0)} more frames)")


    return context

def pdb_dump(include_globals=False, depth=2, to_json=True):
    """
    PDB command function to dump context.
    Prints context as JSON or a Python dict.
    Args:
        include_globals: Whether to include global variables.
        depth: Max serialization depth for complex objects.
        to_json: If True, prints as JSON string, else prints dict.
    """
    # We pass None so get_pdb_full_context tries to find pdb's current frame
    context = get_pdb_full_context(frame=None, include_globals=include_globals, max_depth=depth)

    if to_json:
        try:
            print(json.dumps(context, indent=2, ensure_ascii=False))
        except TypeError as e:
            print(f"Error converting context to JSON: {e}")
            print("Printing raw context dictionary instead:")
            print(context) # Fallback
    else:
        # For direct printing of dict, pprint might be nicer
        from pprint import pprint
        pprint(context)

# Example of how to make it available as a PDB command (see instructions below)
# import pdb
# pdb.Pdb.do_dump = lambda self, arg: pdb_dump_wrapper(self, arg)
#
# def pdb_dump_wrapper(pdb_instance, arg_string):
#     args = arg_string.split()
#     include_globals = 'globals' in args
#     depth = 2
#     to_json = 'json' in args # default to true if not specified, but can be overridden
#     if not args or 'dict' not in args: to_json=True # Make JSON default
#     else: to_json = 'json' in args

#     for a in args:
#         if a.startswith('depth='):
#             try: depth = int(a.split('=')[1])
#             except: pass
#     pdb_dump(include_globals=include_globals, depth=depth, to_json=to_json)