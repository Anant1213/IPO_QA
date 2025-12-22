"""
Knowledge Graph Visualization using Pyvis
Creates an interactive HTML graph from NetworkX graph
"""

import json
import os
import sys
import argparse
from pyvis.network import Network
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from utils.graph_store import GraphStore


def visualize_knowledge_graph(document_id: str, output_file: str = None, max_nodes: int = None):
    """
    Create interactive visualization of knowledge graph
    
    Args:
        document_id: Document folder name
        output_file: Output HTML file path (default: kg_visualization.html)
        max_nodes: Limit nodes for performance (default: all)
    """
    
    doc_folder = f"data/documents/{document_id}"
    kg_file = f"{doc_folder}/knowledge_graph/knowledge_graph.json"
    
    if not os.path.exists(kg_file):
        print(f"❌ Error: Knowledge graph not found: {kg_file}")
        return
    
    print(f"Loading knowledge graph from {kg_file}...")
    graph_store = GraphStore.load(kg_file)  # Use classmethod
    
    # Get statistics
    stats = graph_store.get_statistics()
    print(f"\nGraph Statistics:")
    print(f"  Nodes: {stats['num_nodes']}")
    print(f"  Edges: {stats['num_edges']}")
    print(f"  Connected: {stats['is_connected']}")
    print(f"  Components: {stats['num_connected_components']}")
    
    # Create Pyvis network
    print("\nCreating interactive visualization...")
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1a1a1a",
        font_color="white",
        directed=True
    )
    
    # Configure physics for better layout
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 200,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      },
      "nodes": {
        "font": {"size": 14, "color": "white"}
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
        "smooth": {"type": "continuous"}
      }
    }
    """)
    
    # Entity type color mapping
    type_colors = {
        'COMPANY': '#3498db',        # Blue
        'PERSON': '#e74c3c',         # Red
        'FINANCIAL_METRIC': '#2ecc71',  # Green
        'MARKET_SEGMENT': '#f39c12', # Orange
        'REGULATORY_BODY': '#9b59b6', # Purple
        'IPO_DETAIL': '#1abc9c',     # Teal
        'PRODUCT_SERVICE': '#34495e', # Dark gray
        'RISK_FACTOR': '#c0392b',    # Dark red
        'ASSET': '#16a085',          # Dark teal
        'SHAREHOLDER': '#d35400',    # Dark orange
        'CUSTOMER': '#7f8c8d',       # Gray
        'BANK': '#27ae60',           # Dark green
        'FINANCIAL_INSTITUTION': '#8e44ad',  # Dark purple
        'SUPPLIER_VENDOR': '#2c3e50', # Very dark gray
        'AGREEMENT': '#f1c40f',      # Yellow
        'ACCOUNT': '#95a5a6',        # Light gray
        'FACILITY': '#e67e22',       # Carrot
        'PROCESS': '#bdc3c7',        # Silver
        'MEDIA_OUTLET': '#34495e',   # Dark slate
        'REGULATION': '#c39bd3'      # Light purple
    }
    
    # Add nodes
    G = graph_store.graph
    node_count = 0
    
    for node_id, node_data in G.nodes(data=True):
        if max_nodes and node_count >= max_nodes:
            break
        
        entity_type = node_data.get('type', 'UNKNOWN')
        color = type_colors.get(entity_type, '#95a5a6')
        
        # Create label with type
        label = node_data.get('name', node_id)
        title = f"<b>{label}</b><br>Type: {entity_type}"
        
        # Add attributes to hover
        if 'attributes' in node_data and node_data['attributes']:
            title += "<br><br><b>Attributes:</b>"
            for key, value in node_data['attributes'].items():
                if isinstance(value, (str, int, float)):
                    title += f"<br>• {key}: {value}"
        
        # Size based on degree (connections)
        degree = G.degree(node_id)
        size = min(10 + degree * 2, 40)
        
        net.add_node(
            node_id,
            label=label[:30] + "..." if len(label) > 30 else label,
            title=title,
            color=color,
            size=size,
            shape='dot'
        )
        node_count += 1
    
    # Add edges
    edge_count = 0
    for source, target, edge_data in G.edges(data=True):
        if max_nodes:
            if source not in [n for n in list(G.nodes())[:max_nodes]]:
                continue
            if target not in [n for n in list(G.nodes())[:max_nodes]]:
                continue
        
        relation_type = edge_data.get('relation_type', 'RELATED_TO')
        
        # Create edge label
        title = f"<b>{relation_type}</b>"
        if 'source_chunk_id' in edge_data:
            title += f"<br>Source: Chunk {edge_data['source_chunk_id']}"
        
        net.add_edge(
            source,
            target,
            title=title,
            label=relation_type[:20],
            color='#7f8c8d',
            width=1
        )
        edge_count += 1
    
    # Set output file
    if not output_file:
        output_file = f"{doc_folder}/knowledge_graph/kg_visualization.html"
    
    # Save
    print(f"\nSaving visualization to {output_file}...")
    net.write_html(output_file)
    
    print(f"\n✓ Visualization created successfully!")
    print(f"  Nodes displayed: {node_count}")
    print(f"  Edges displayed: {edge_count}")
    print(f"\nOpen {output_file} in your browser to view the interactive graph.")


def main():
    parser = argparse.ArgumentParser(description='Visualize Knowledge Graph')
    parser.add_argument('--document', type=str, required=True,
                       help='Document ID (folder name)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output HTML file path')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of nodes for performance')
    
    args = parser.parse_args()
    
    visualize_knowledge_graph(
        document_id=args.document,
        output_file=args.output,
        max_nodes=args.limit
    )


if __name__ == "__main__":
    main()
