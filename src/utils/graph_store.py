"""
Graph Storage - NetworkX-based knowledge graph with JSON persistence
"""

import networkx as nx
import json
import os
from typing import List, Dict, Tuple, Optional


class GraphStore:
    """Store and query knowledge graph using NetworkX"""
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edges
        
    def add_entity(self, entity_id: str, entity_data: Dict):
        """Add entity as graph node"""
        self.graph.add_node(
            entity_id,
            **entity_data
        )
    
    def add_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        rel_type: str,
        attributes: Dict = None
    ):
        """Add relationship as graph edge"""
        attrs = attributes or {}
        attrs['type'] = rel_type
        
        self.graph.add_edge(
            source_id,
            target_id,
            key=rel_type,
            **attrs
        )
    
    def build_from_extractions(self, extractions: List[Dict]):
        """
        Build graph from resolved extraction results
        
        Args:
            extractions: List of resolved extractions with entities and relationships
        """
        print("Building knowledge graph...")
        entity_count = 0
        rel_count = 0
        
        # Add all entities
        for extraction in extractions:
            for entity in extraction.get('entities', []):
                canonical_id = entity.get('canonical_id', entity['id'])
                
                # Only add if not already present
                if not self.graph.has_node(canonical_id):
                    self.add_entity(canonical_id, {
                        'name': entity['name'],
                        'type': entity['type'],
                        'attributes': entity.get('attributes', {})
                    })
                    entity_count += 1
        
        # Add all relationships
        for extraction in extractions:
            chunk_id = extraction.get('chunk_id')
            
            for rel in extraction.get('relationships', []):
                source_id = rel['source_id']
                target_id = rel['target_id']
                rel_type = rel['type']
                
                # Only add if both nodes exist
                if self.graph.has_node(source_id) and self.graph.has_node(target_id):
                    attrs = rel.get('attributes', {}).copy()
                    attrs['source_chunk_id'] = chunk_id
                    
                    self.add_relationship(source_id, target_id, rel_type, attrs)
                    rel_count += 1
        
        print(f"Graph built: {entity_count} entities, {rel_count} relationships")
    
    def query_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity data by ID"""
        if not self.graph.has_node(entity_id):
            return None
        
        node_data = dict(self.graph.nodes[entity_id])
        return {
            'id': entity_id,
            **node_data
        }
    
    def query_relationships(
        self, 
        entity_id: str, 
        rel_type: Optional[str] = None,
        direction: str = 'outgoing'
    ) -> List[Tuple]:
        """
        Get relationships for an entity
        
        Args:
            entity_id: Entity ID
            rel_type: Filter by relationship type (optional)
            direction: 'outgoing', 'incoming', or 'both'
            
        Returns:
            List of (source, target, rel_type, attributes) tuples
        """
        results = []
        
        if direction in ['outgoing', 'both']:
            # Outgoing edges
            for _, target, key, data in self.graph.out_edges(entity_id, keys=True, data=True):
                if rel_type is None or key == rel_type:
                    results.append((entity_id, target, key, data))
        
        if direction in ['incoming', 'both']:
            # Incoming edges
            for source, _, key, data in self.graph.in_edges(entity_id, keys=True, data=True):
                if rel_type is None or key == rel_type:
                    results.append((source, entity_id, key, data))
        
        return results
    
    def find_entities_by_type(self, entity_type: str) -> List[str]:
        """Find all entities of a specific type"""
        return [
            node_id 
            for node_id, data in self.graph.nodes(data=True)
            if data.get('type') == entity_type
        ]
    
    def find_path(self, source_id: str, target_id: str) -> Optional[List]:
        """Find shortest path between two entities"""
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_neighbors(self, entity_id: str, hops: int = 1) -> List[str]:
        """Get all neighboring entities within N hops"""
        if hops == 1:
            successors = list(self.graph.successors(entity_id))
            predecessors = list(self.graph.predecessors(entity_id))
            return list(set(successors + predecessors))
        else:
            # Multi-hop traversal
            neighbors = set()
            current_level = {entity_id}
            
            for _ in range(hops):
                next_level = set()
                for node in current_level:
                    next_level.update(self.graph.successors(node))
                    next_level.update(self.graph.predecessors(node))
                neighbors.update(next_level)
                current_level = next_level
            
            neighbors.discard(entity_id)  # Remove original node
            return list(neighbors)
    
    def save(self, filepath: str):
        """Save graph to JSON file"""
        # Convert to node-link format for JSON serialization
        data = nx.node_link_data(self.graph)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Graph saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'GraphStore':
        """Load graph from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        store = cls()
        store.graph = nx.node_link_graph(data, directed=True, multigraph=True)
        
        print(f"Graph loaded from {filepath}")
        return store
    
    def get_statistics(self) -> Dict:
        """Get graph statistics"""
        return {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'is_connected': nx.is_weakly_connected(self.graph),
            'num_connected_components': nx.number_weakly_connected_components(self.graph),
            'density': nx.density(self.graph)
        }
    
    def export_for_visualization(self) -> Dict:
        """Export graph in format suitable for frontend visualization (vis.js)"""
        nodes = []
        edges = []
        
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                'id': node_id,
                'label': data.get('name', node_id),
                'type': data.get('type', 'UNKNOWN'),
                'attributes': data.get('attributes', {})
            })
        
        edge_id = 0
        for source, target, key, data in self.graph.edges(keys=True, data=True):
            edges.append({
                'id': edge_id,
                'from': source,
                'to': target,
                'label': key,
                'attributes': {k: v for k, v in data.items() if k != 'type'}
            })
            edge_id += 1
        
        return {
            'nodes': nodes,
            'edges': edges
        }
