#!/usr/bin/env python3
"""
Knowledge Graph Visualization from Claims
Creates an interactive HTML visualization from extracted claims
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

try:
    from pyvis.network import Network
except ImportError:
    os.system("pip install pyvis")
    from pyvis.network import Network

from database.connection import engine
from sqlalchemy import text


def get_claims_data(document_id: str):
    """Fetch claims data from PostgreSQL"""
    with engine.connect() as conn:
        # Get document DB ID
        result = conn.execute(text("SELECT id FROM documents WHERE document_id = :doc_id"), {"doc_id": document_id})
        row = result.fetchone()
        if not row:
            return None, []
        doc_db_id = row[0]
        
        # Get claims
        result = conn.execute(text("""
            SELECT id, predicate, object_value
            FROM claims 
            WHERE document_id = :doc_id
            AND object_value IS NOT NULL
            AND object_value != ''
        """), {"doc_id": doc_db_id})
        
        claims = [dict(row._mapping) for row in result]
        return doc_db_id, claims


def create_claims_visualization(claims: list, output_file: str, title: str):
    """Create network visualization from claims"""
    
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#0a0a0a",
        font_color="white",
        directed=True,
        heading=title
    )
    
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -150,
          "centralGravity": 0.01,
          "springLength": 200,
          "springConstant": 0.08,
          "damping": 0.4
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 200}
      },
      "nodes": {
        "font": {"size": 14, "color": "white", "face": "arial"},
        "borderWidth": 2
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.7}},
        "smooth": {"type": "continuous"},
        "font": {"size": 10, "color": "#888888", "align": "middle"}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)
    
    # Color mapping for predicates
    predicate_colors = {
        'CEO_OF': '#e74c3c',
        'FOUNDER_OF': '#e74c3c',
        'OWNS': '#2ecc71',
        'SUBSIDIARY_OF': '#3498db',
        'WORKS_AT': '#f39c12',
        'EMPLOYEE_OF': '#f39c12',
        'HAS_REVENUE': '#27ae60',
        'REGULATES': '#9b59b6',
        'LOCATED_IN': '#1abc9c',
        'MEMBER_OF': '#d35400',
        'PARTNER': '#8e44ad',
        'MANAGES': '#16a085',
    }
    
    # Central node for the company
    central_node = "PB Fintech / Policybazaar"
    net.add_node(
        central_node,
        label=central_node,
        title=f"<b>{central_node}</b><br>Central Entity",
        color='#3498db',
        size=40,
        shape='dot'
    )
    
    # Add nodes and edges from claims
    nodes_added = set([central_node])
    
    for claim in claims:
        predicate = claim.get('predicate', 'RELATED_TO')
        obj_value = claim.get('object_value', '')
        
        if not obj_value or len(obj_value) < 2:
            continue
        
        # Truncate long values
        display_value = obj_value[:50] + "..." if len(obj_value) > 50 else obj_value
        
        # Determine node color based on predicate
        if predicate in ['CEO_OF', 'FOUNDER_OF', 'WORKS_AT', 'EMPLOYEE_OF']:
            node_color = '#e74c3c'  # Red for people
        elif predicate in ['OWNS', 'SUBSIDIARY_OF']:
            node_color = '#2ecc71'  # Green for ownership
        elif predicate in ['HAS_REVENUE', 'HAS']:
            node_color = '#f1c40f'  # Yellow for metrics
        elif predicate in ['REGULATES']:
            node_color = '#9b59b6'  # Purple for regulators
        else:
            node_color = '#95a5a6'  # Gray for others
        
        # Add node if not exists
        if obj_value not in nodes_added:
            net.add_node(
                obj_value,
                label=display_value,
                title=f"<b>{obj_value}</b><br>Predicate: {predicate}",
                color=node_color,
                size=20,
                shape='dot'
            )
            nodes_added.add(obj_value)
        
        # Add edge
        edge_color = predicate_colors.get(predicate, '#7f8c8d')
        net.add_edge(
            central_node,
            obj_value,
            title=f"<b>{predicate}</b>",
            label=predicate.replace('_', ' ')[:15],
            color=edge_color,
            width=2
        )
    
    net.write_html(output_file)
    return len(nodes_added), len(claims)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Visualize KG from Claims')
    parser.add_argument('--document', '-d', required=True, help='Document ID')
    parser.add_argument('--output', '-o', default=None, help='Output HTML file')
    parser.add_argument('--open', action='store_true', help='Open in browser')
    
    args = parser.parse_args()
    
    print(f"\n🔍 Fetching claims for: {args.document}")
    
    doc_id, claims = get_claims_data(args.document)
    
    if not claims:
        print(f"❌ No claims found for {args.document}")
        return
    
    print(f"   Found {len(claims)} claims")
    
    output_file = args.output or f"data/documents/{args.document}/kg_claims_viz.html"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"🎨 Creating visualization...")
    nodes, edges = create_claims_visualization(
        claims, 
        output_file,
        f"Knowledge Graph: {args.document}"
    )
    
    print(f"\n✅ Visualization created!")
    print(f"   Nodes: {nodes}")
    print(f"   Edges: {edges}")
    print(f"   File: {output_file}")
    
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(output_file)}")
        print(f"🌐 Opened in browser!")


if __name__ == "__main__":
    main()
