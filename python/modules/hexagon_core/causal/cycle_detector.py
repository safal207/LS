from typing import Dict, List

class CycleDetector:
    """
    Detects cycles in a directed graph using DFS.
    """
    def has_path(self, graph: Dict[str, List[str]], start_node: str, target_node: str) -> bool:
        """
        Checks if there is a path from start_node to target_node.
        Used to prevent cycles: if adding A->B, check if path B->...->A exists.
        """
        if start_node == target_node:
            return True

        visited = set()
        stack = [start_node]

        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)

            if node == target_node:
                return True

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    stack.append(neighbor)

        return False
