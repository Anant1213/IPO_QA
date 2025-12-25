#!/usr/bin/env python3
"""
Knowledge Graph Visualization from PostgreSQL Database
Creates an interactive HTML visualization of the extracted KG data
"""

import os
import sys
import argparse
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

try:
    from pyvis.network import Network
except ImportError:
    print("Installing pyvis...")
    os.system("pip install pyvis")
    from pyvis.network import Network

from database.connection import engine
from sqlalchemy import text


def get_kg_data(document_id: str):
    """Fetch all KG data from PostgreSQL for a document"""
    
    data = {
        'entities': [],
        'claims': [],
        'defined_terms': [],
        'events': [],
        'doc_id_int': None
    }
    
    with engine.connect() as conn:
        # First get the integer document ID
        result = conn.execute(text("""
            SELECT id FROM documents WHERE document_id = :doc_id
        """), {"doc_id": document_id})
        row = result.fetchone()
        if not row:
            print(f"Document not found: {document_id}")
            return data
        
        doc_id_int = row[0]
        data['doc_id_int'] = doc_id_int
        
        # Get entities (use canonical_name instead of name)
        result = conn.execute(text("""
            SELECT id, document_id, canonical_name as name, entity_type, attributes
            FROM kg_entities 
            WHERE document_id = :doc_id
        """), {"doc_id": doc_id_int})
        data['entities'] = [dict(row._mapping) for row in result]
        
        # Get claims (relationships)
        result = conn.execute(text("""
            SELECT c.id, c.subject_entity_id, c.predicate, c.object_entity_id,
                   c.object_value, c.datatype,
                   s.canonical_name as subject_name, s.entity_type as subject_type,
                   o.canonical_name as object_name, o.entity_type as object_type
            FROM claims c
            LEFT JOIN kg_entities s ON c.subject_entity_id = s.id
            LEFT JOIN kg_entities o ON c.object_entity_id = o.id
            WHERE c.document_id = :doc_id
        """), {"doc_id": doc_id_int})
        data['claims'] = [dict(row._mapping) for row in result]
        
        # Get defined terms
        result = conn.execute(text("""
            SELECT id, term, definition
            FROM defined_terms 
            WHERE document_id = :doc_id
        """), {"doc_id": doc_id_int})
        data['defined_terms'] = [dict(row._mapping) for row in result]
        
        # Get events
        result = conn.execute(text("""
            SELECT id, event_type, description, event_date
            FROM events 
            WHERE document_id = :doc_id
        """), {"doc_id": doc_id_int})
        data['events'] = [dict(row._mapping) for row in result]
    
    return data


def create_visualization(data: dict, output_file: str, title: str = "Knowledge Graph"):
    """Create interactive PyVis visualization"""
    
    # Create network
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#0a0a0a",
        font_color="white",
        directed=True,
        heading=title
    )
    
    # Configure physics
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -100,
          "centralGravity": 0.005,
          "springLength": 230,
          "springConstant": 0.08,
          "damping": 0.4
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 200}
      },
      "nodes": {
        "font": {"size": 16, "color": "white", "face": "arial"},
        "borderWidth": 2
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.7}},
        "smooth": {"type": "continuous"},
        "font": {"size": 11, "color": "#888888", "align": "middle"}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)
    
    # Entity type colors
    type_colors = {
        'PERSON': '#e74c3c',           # Red
        'COMPANY': '#3498db',          # Blue
        'ORGANIZATION': '#9b59b6',     # Purple
        'SUBSIDIARY': '#2980b9',       # Darker blue
        'FINANCIAL_METRIC': '#2ecc71', # Green
        'PERCENTAGE': '#27ae60',       # Dark green
        'MONEY': '#f1c40f',            # Yellow
        'CURRENCY': '#f1c40f',         # Yellow
        'NUMBER': '#16a085',           # Teal
        'DATE': '#e67e22',             # Orange
        'LOCATION': '#1abc9c',         # Teal
        'PRODUCT': '#34495e',          # Dark gray
        'SERVICE': '#5d6d7e',          # Gray blue
        'REGULATION': '#8e44ad',       # Dark purple
        'ROLE': '#d35400',             # Dark orange
        'EVENT': '#c0392b',            # Dark red
        'DOCUMENT': '#7f8c8d',         # Gray
        'REGULATORY_BODY': '#8e44ad',  # Purple
        'MARKET_SEGMENT': '#f39c12',   # Orange
    }
    
    # Add entity nodes
    entity_map = {}  # id -> name
    for entity in data['entities']:
        entity_id = entity['id']
        name = entity['name']
        entity_type = entity.get('entity_type', 'UNKNOWN')
        attributes = entity.get('attributes', {}) or {}
        
        entity_map[entity_id] = name
        
        color = type_colors.get(entity_type, '#95a5a6')
        
        # Build tooltip
        tooltip = f"<b>{name}</b><br>Type: {entity_type}"
        if attributes:
            tooltip += "<br><br><b>Attributes:</b>"
            for k, v in list(attributes.items())[:5]:  # Limit attributes
                tooltip += f"<br>• {k}: {v}"
        
        net.add_node(
            entity_id,
            label=name[:25] + "..." if len(name) > 25 else name,
            title=tooltip,
            color=color,
            size=25,
            shape='dot',
            borderWidthSelected=3
        )
    
    # Add edges from claims
    edge_colors = {
        'CEO_OF': '#e74c3c',
        'FOUNDER_OF': '#e74c3c',
        'DIRECTOR_OF': '#d35400',
        'WORKS_FOR': '#f39c12',
        'EMPLOYEE_OF': '#f39c12',
        'OWNS': '#2ecc71',
        'SHAREHOLDING': '#27ae60',
        'SUBSIDIARY_OF': '#3498db',
        'PARTNER_OF': '#9b59b6',
        'LOCATED_IN': '#1abc9c',
        'HAS_REVENUE': '#27ae60',
        'HAS_VALUE': '#f1c40f',
        'HAS_METRIC': '#2ecc71',
    }
    
    for claim in data['claims']:
        subject_id = claim.get('subject_entity_id')
        object_id = claim.get('object_entity_id')
        predicate = claim.get('predicate', 'RELATED_TO')
        object_value = claim.get('object_value')
        
        if subject_id and object_id and subject_id in entity_map and object_id in entity_map:
            edge_color = edge_colors.get(predicate, '#7f8c8d')
            
            tooltip = f"<b>{predicate}</b>"
            if object_value:
                tooltip += f"<br>Value: {object_value}"
            
            net.add_edge(
                subject_id,
                object_id,
                title=tooltip,
                label=predicate.replace('_', ' ')[:15],
                color=edge_color,
                width=2,
                arrows='to'
            )
        elif subject_id and object_value and subject_id in entity_map:
            # Create a value node for claims with object_value
            value_id = f"value_{claim['id']}"
            display_value = str(object_value)[:30]
            net.add_node(
                value_id,
                label=display_value,
                title=f"<b>{predicate}:</b> {object_value}",
                color='#f1c40f',
                size=15,
                shape='box'
            )
            net.add_edge(
                subject_id,
                value_id,
                label=predicate.replace('_', ' ')[:15],
                color='#f1c40f',
                width=1.5
            )
    
    # Save HTML
    net.write_html(output_file)
    return len(data['entities']), len(data['claims'])


def print_statistics(data: dict, document_id: str):
    """Print KG statistics"""
    print(f"\n{'='*60}")
    print(f"  Knowledge Graph Statistics: {document_id}")
    print(f"{'='*60}")
    
    print(f"\n📊 Counts:")
    print(f"   • Entities: {len(data['entities'])}")
    print(f"   • Claims (Relationships): {len(data['claims'])}")
    print(f"   • Defined Terms: {len(data['defined_terms'])}")
    print(f"   • Events: {len(data['events'])}")
    
    # Entity type breakdown
    type_counts = defaultdict(int)
    for e in data['entities']:
        type_counts[e.get('entity_type', 'UNKNOWN')] += 1
    
    print(f"\n👤 Entity Types:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"   • {t}: {count}")
    
    # Predicate breakdown
    pred_counts = defaultdict(int)
    for c in data['claims']:
        pred_counts[c.get('predicate', 'UNKNOWN')] += 1
    
    print(f"\n🔗 Relationship Types (Top 10):")
    for p, count in sorted(pred_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"   • {p}: {count}")
    
    # Sample entities
    print(f"\n📝 Sample Entities:")
    for e in data['entities'][:8]:
        print(f"   • {e['name']} ({e.get('entity_type', 'UNKNOWN')})")
    
    # Sample claims
    print(f"\n🔗 Sample Claims:")
    for c in data['claims'][:8]:
        subj = c.get('subject_name', 'Unknown')
        pred = c.get('predicate', 'RELATED_TO')
        obj = c.get('object_name') or c.get('object_value', 'Unknown')
        print(f"   • {subj} --[{pred}]--> {obj}")


def main():
    parser = argparse.ArgumentParser(description='Visualize Knowledge Graph from Database')
    parser.add_argument('--document', '-d', type=str, required=True,
                       help='Document ID (e.g., policybazar_ipo)')
    parser.add_argument('--output', '-o', type=str, default=None,
                       help='Output HTML file path')
    parser.add_argument('--stats-only', action='store_true',
                       help='Only print statistics, no visualization')
    parser.add_argument('--open', action='store_true',
                       help='Open visualization in browser after creating')
    
    args = parser.parse_args()
    
    print(f"\n🔍 Fetching KG data for: {args.document}")
    
    try:
        data = get_kg_data(args.document)
    except Exception as e:
        print(f"\n❌ Error fetching data: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL is set")
        print("  3. The document exists in the database")
        return
    
    if not data['entities']:
        print(f"\n⚠️  No entities found for document: {args.document}")
        print("Run the KG extraction first with: python scripts/build_kg_v2.py --document <doc_id>")
        return
    
    # Print statistics
    print_statistics(data, args.document)
    
    if args.stats_only:
        return
    
    # Create visualization
    output_file = args.output or f"data/documents/{args.document}/kg_visualization.html"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"\n🎨 Creating visualization...")
    num_nodes, num_edges = create_visualization(
        data, 
        output_file, 
        title=f"Knowledge Graph: {args.document}"
    )
    
    print(f"\n✅ Visualization created!")
    print(f"   • Nodes: {num_nodes}")
    print(f"   • Edges: {num_edges}")
    print(f"   • File: {output_file}")
    
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(output_file)}")
        print(f"\n🌐 Opened in browser!")
    else:
        print(f"\n💡 Open in browser: open {output_file}")


if __name__ == "__main__":
    main()
