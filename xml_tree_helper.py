import streamlit as st
from streamlit_tree_select import tree_select

class XMLTreeHelper:
    """
    Helper class for converting XML to tree structure and finding elements by unique path.
    """
    @staticmethod
    def xml_to_tree(elem, path=""):
        # Generate a unique path for each node using index among all children
        def get_path(e):
            parent = e.getparent()
            if parent is None:
                return f"/{e.tag}[0]"
            idx = list(parent).index(e)
            return f"{get_path(parent)}/{e.tag}[{idx}]"
        # If root, start path
        if not path:
            path = f"/{elem.tag}[0]"
        node = {
            "label": elem.tag,
            "value": path,
        }
        if len(elem) > 0:
            node["children"] = [XMLTreeHelper.xml_to_tree(child, f"{path}/{child.tag}[{i}]") for i, child in enumerate(elem)]
        return node

    @staticmethod
    def find_elem_by_path(elem, path):
        # path is like /root[0]/child[0]/subchild[0], so split and walk
        import re
        parts = re.findall(r'/([^/\[]+)\[(\d+)\]', path)
        current = elem
        if not parts:
            return None
        # The first part should match the root
        root_tag, root_idx = parts[0]
        if current.tag != root_tag or int(root_idx) != 0:
            return None
        for tag, idx in parts[1:]:
            idx = int(idx)
            # Get the idx-th child (regardless of tag)
            children = list(current)
            if len(children) > idx and children[idx].tag == tag:
                current = children[idx]
            else:
                return None
        return current
