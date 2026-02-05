import sys
sys.path.append('..')
import app
from dash.development.base_component import Component

def collect_ids(node):
    ids = []
    stack = [node]
    while stack:
        comp = stack.pop()
        if isinstance(comp, Component):
            cid = getattr(comp, 'id', None)
            if cid:
                ids.append(cid)
            children = getattr(comp, 'children', None)
            if isinstance(children, (list, tuple)):
                stack.extend(children)
            elif children is not None:
                stack.append(children)
    return ids

layout = app.vizro_app.dash.layout()
print(collect_ids(layout)[:40])
