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
    
    # Create network - NO heading for cleaner look
    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#0d1117",  # GitHub dark theme
        font_color="#e6edf3",
        directed=True,
        heading=""  # Remove heading
    )
    
    # Enhanced physics for better interactivity
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "centralGravity": 0.008,
          "springLength": 180,
          "springConstant": 0.06,
          "damping": 0.5,
          "avoidOverlap": 0.5
        },
        "maxVelocity": 40,
        "solver": "forceAtlas2Based",
        "timestep": 0.4,
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 25
        }
      },
      "nodes": {
        "font": {
          "size": 14,
          "color": "#e6edf3",
          "face": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          "strokeWidth": 2,
          "strokeColor": "#0d1117"
        },
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "shadow": {
          "enabled": true,
          "color": "rgba(0,0,0,0.3)",
          "size": 10,
          "x": 3,
          "y": 3
        }
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.6,
            "type": "arrow"
          }
        },
        "smooth": {
          "type": "curvedCW",
          "roundness": 0.15
        },
        "font": {
          "size": 10,
          "color": "#8b949e",
          "align": "middle",
          "background": "#0d1117"
        },
        "color": {
          "inherit": false,
          "opacity": 0.8
        },
        "width": 1.5,
        "selectionWidth": 3,
        "hoverWidth": 2.5
      },
      "interaction": {
        "hover": true,
        "hoverConnectedEdges": true,
        "multiselect": true,
        "navigationButtons": true,
        "keyboard": {
          "enabled": true,
          "bindToWindow": true
        },
        "tooltipDelay": 100,
        "zoomView": true,
        "dragView": true
      }
    }
    """)
    
    # Premium entity type colors - vibrant modern palette
    type_colors = {
        'PERSON': '#f97583',           # Soft red/pink
        'COMPANY': '#79c0ff',          # Bright blue
        'ORGANIZATION': '#d2a8ff',     # Light purple
        'SUBSIDIARY': '#58a6ff',       # Electric blue
        'REGULATOR': '#ff7b72',        # Coral red
        'UNKNOWN': '#8b949e',          # Gray
        'FINANCIAL_METRIC': '#7ee787', # Bright green
        'PERCENTAGE': '#56d364',       # Green
        'MONEY': '#e3b341',            # Gold
        'CURRENCY': '#e3b341',         # Gold
        'NUMBER': '#39d353',           # Green
        'DATE': '#f0883e',             # Orange
        'LOCATION': '#3fb950',         # Green
        'COUNTRY': '#3fb950',          # Green
        'PRODUCT': '#a5d6ff',          # Light blue
        'SERVICE': '#a5d6ff',          # Light blue
        'REGULATION': '#bc8cff',       # Purple
        'LEGISLATION': '#bc8cff',      # Purple
        'ROLE': '#ffa657',             # Orange
        'EVENT': '#ff7b72',            # Coral
        'DOCUMENT': '#8b949e',         # Gray
        'STANDARD': '#8b949e',         # Gray
        'CONCEPT': '#c9d1d9',          # Light gray
    }
    
    # First pass: collect relationships for each entity
    entity_relationships = {}
    for claim in data['claims']:
        subj_id = claim.get('subject_entity_id')
        obj_id = claim.get('object_entity_id')
        pred = claim.get('predicate', '')
        obj_name = claim.get('object_name') or claim.get('object_value', '')
        subj_name = claim.get('subject_name', '')
        
        if subj_id:
            if subj_id not in entity_relationships:
                entity_relationships[subj_id] = {'outgoing': [], 'incoming': []}
            entity_relationships[subj_id]['outgoing'].append(f"{pred} → {obj_name}")
        
        if obj_id:
            if obj_id not in entity_relationships:
                entity_relationships[obj_id] = {'outgoing': [], 'incoming': []}
            entity_relationships[obj_id]['incoming'].append(f"{subj_name} → {pred}")
    
    # Add entity nodes with rich tooltips
    entity_map = {}  # id -> name
    for entity in data['entities']:
        entity_id = entity['id']
        name = entity['name']
        entity_type = entity.get('entity_type', 'UNKNOWN')
        attributes = entity.get('attributes', {}) or {}
        
        entity_map[entity_id] = name
        
        color = type_colors.get(entity_type, '#8b949e')
        
        # Build rich HTML tooltip
        tooltip = f"""
        <div style='font-family: Inter, sans-serif; padding: 8px; max-width: 300px;'>
            <div style='font-size: 16px; font-weight: bold; color: {color}; margin-bottom: 8px;'>
                {name}
            </div>
            <div style='font-size: 12px; color: #8b949e; margin-bottom: 8px;'>
                Type: <span style='color: {color};'>{entity_type}</span>
            </div>
        """
        
        if attributes:
            tooltip += "<div style='margin-top: 8px; border-top: 1px solid #30363d; padding-top: 8px;'>"
            tooltip += "<div style='font-size: 11px; color: #58a6ff; margin-bottom: 4px;'>📋 ATTRIBUTES</div>"
            for k, v in list(attributes.items())[:5]:
                tooltip += f"<div style='font-size: 11px; color: #c9d1d9;'>• {k}: {v}</div>"
            tooltip += "</div>"
        
        # Add relationships to tooltip
        rels = entity_relationships.get(entity_id, {'outgoing': [], 'incoming': []})
        if rels['outgoing']:
            tooltip += "<div style='margin-top: 8px; border-top: 1px solid #30363d; padding-top: 8px;'>"
            tooltip += "<div style='font-size: 11px; color: #7ee787; margin-bottom: 4px;'>🔗 RELATIONSHIPS (Outgoing)</div>"
            for rel in rels['outgoing'][:5]:
                tooltip += f"<div style='font-size: 10px; color: #c9d1d9;'>→ {rel}</div>"
            if len(rels['outgoing']) > 5:
                tooltip += f"<div style='font-size: 10px; color: #8b949e;'>... and {len(rels['outgoing'])-5} more</div>"
            tooltip += "</div>"
        
        if rels['incoming']:
            tooltip += "<div style='margin-top: 8px; border-top: 1px solid #30363d; padding-top: 8px;'>"
            tooltip += "<div style='font-size: 11px; color: #f97583; margin-bottom: 4px;'>🔗 RELATIONSHIPS (Incoming)</div>"
            for rel in rels['incoming'][:5]:
                tooltip += f"<div style='font-size: 10px; color: #c9d1d9;'>← {rel}</div>"
            if len(rels['incoming']) > 5:
                tooltip += f"<div style='font-size: 10px; color: #8b949e;'>... and {len(rels['incoming'])-5} more</div>"
            tooltip += "</div>"
        
        tooltip += "</div>"
        
        # Determine node size based on connections
        num_connections = len(rels['outgoing']) + len(rels['incoming'])
        node_size = min(35, 18 + num_connections * 2)
        
        net.add_node(
            entity_id,
            label=name[:25] + "..." if len(name) > 25 else name,
            title=tooltip,
            color=color,
            size=node_size,
            shape='dot',
            borderWidthSelected=4
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
