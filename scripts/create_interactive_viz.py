"""
Create Interactive Knowledge Graph Visualization with Click-to-Zoom and Info Panel
"""

import json
import os

# Load the graph visualization data
doc_folder = "data/documents/policybazar_ipo"
viz_file = f"{doc_folder}/knowledge_graph/graph_viz.json"

print(f"Loading graph data from {viz_file}...")
with open(viz_file, 'r') as f:
    graph_data = json.load(f)

print(f"Loaded {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges")

# Show ALL nodes (no limit)
nodes = graph_data['nodes']
node_ids = set(n['id'] for n in nodes)
edges = [e for e in graph_data['edges'] if e['from'] in node_ids and e['to'] in node_ids]

print(f"Using {len(nodes)} nodes and {len(edges)} edges for visualization")

# Entity type color mapping
type_colors = {
    'COMPANY': '#3498db',
    'PERSON': '#e74c3c',
    'FINANCIAL_METRIC': '#2ecc71',
    'MARKET_SEGMENT': '#f39c12',
    'REGULATORY_BODY': '#9b59b6',
    'IPO_DETAIL': '#1abc9c',
    'PRODUCT_SERVICE': '#34495e',
    'RISK_FACTOR': '#c0392b',
    'ASSET': '#16a085',
    'SHAREHOLDER': '#d35400',
    'CUSTOMER': '#7f8c8d',
    'BANK': '#27ae60',
    'FINANCIAL_INSTITUTION': '#8e44ad',
    'SUPPLIER_VENDOR': '#2c3e50',
    'AGREEMENT': '#f1c40f',
    'ACCOUNT': '#95a5a6',
    'FACILITY': '#e67e22',
    'PROCESS': '#bdc3c7',
    'MEDIA_OUTLET': '#34495e',
    'REGULATION': '#c39bd3'
}

# Format nodes for vis.js
formatted_nodes = []
for node in nodes:
    entity_type = node.get('type', 'UNKNOWN')
    color = type_colors.get(entity_type, '#95a5a6')
    
    # Create detailed info
    info_html = f"<strong>{node.get('label', node['id'])}</strong><br>"
    info_html += f"<em>Type: {entity_type}</em><br><br>"
    
    if node.get('attributes'):
        info_html += "<strong>Attributes:</strong><br>"
        for key, value in node['attributes'].items():
            if isinstance(value, (str, int, float)):
                info_html += f"• {key}: {value}<br>"
    
    formatted_nodes.append({
        'id': node['id'],
        'label': node['label'][:30] + "..." if len(node['label']) > 30 else node['label'],
        'title': node['label'],
        'color': color,
        'type': entity_type,
        'fullInfo': info_html,
        'attributes': node.get('attributes', {})
    })

# Format edges for vis.js
formatted_edges = []
for edge in edges:
    formatted_edges.append({
        'from': edge['from'],
        'to': edge['to'],
        'label': edge.get('label', '')[:15],
        'title': edge.get('label', ''),
        'arrows': 'to',
        'color': {'color': '#7f8c8d', 'opacity': 0.5}
    })

# Create HTML template
html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PB Fintech IPO - Knowledge Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: #0f0f23;
            color: #e0e0e0;
            overflow: hidden;
        }
        
        #header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        h1 {
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: white;
        }
        
        .stats {
            margin-top: 8px;
            font-size: 14px;
            color: rgba(255,255,255,0.9);
        }
        
        #container {
            display: flex;
            height: calc(100vh - 100px);
        }
        
        #network {
            flex: 1;
            background: #1a1a2e;
            border-right: 2px solid #2a2a4e;
        }
        
        #info-panel {
            width: 350px;
            background: #16213e;
            padding: 25px;
            overflow-y: auto;
            box-shadow: -4px 0 10px rgba(0,0,0,0.3);
        }
        
        #info-panel h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }
        
        #node-info {
            line-height: 1.6;
            color: #d0d0d0;
        }
        
        #node-info strong {
            color: #a8b3ff;
        }
        
        #node-info em {
            color: #9ca3af;
        }
        
        .legend {
            margin-top: 30px;
            padding: 15px;
            background: #1a1a2e;
            border-radius: 8px;
        }
        
        .legend h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #a8b3ff;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-size: 13px;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid rgba(255,255,255,0.2);
        }
        
        .instructions {
            margin-top: 20px;
            padding: 15px;
            background: rgba(102, 126, 234, 0.1);
            border-left: 3px solid #667eea;
            font-size: 13px;
            line-height: 1.8;
            border-radius: 4px;
        }
        
        .instructions strong {
            color: #667eea;
        }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #1a1a2e;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div id="header">
        <h1>🔍 PB Fintech IPO - Knowledge Graph</h1>
        <div class="stats">
            <span id="node-count"></span> Entities • 
            <span id="edge-count"></span> Relationships
        </div>
    </div>
    
    <div id="container">
        <div id="network"></div>
        <div id="info-panel">
            <h2>Node Information</h2>
            <div id="node-info">
                <p style="color: #9ca3af; font-style: italic;">
                    Click on any node to view details
                </p>
            </div>
            
            <div class="legend">
                <h3>Entity Types</h3>
                <div id="legend-items"></div>
            </div>
            
            <div class="instructions">
                <strong>💡 How to Use:</strong><br>
                • <strong>Click</strong> any node to zoom and see details<br>
                • <strong>Drag</strong> nodes to rearrange<br>
                • <strong>Scroll</strong> to zoom in/out<br>
                • <strong>Right-click drag</strong> to pan
            </div>
        </div>
    </div>
    
    <script>
        // Graph data
        const nodesData = """ + json.dumps(formatted_nodes) + """;
        const edgesData = """ + json.dumps(formatted_edges) + """;
        
        // Update stats
        document.getElementById('node-count').textContent = nodesData.length;
        document.getElementById('edge-count').textContent = edgesData.length;
        
        // Create legend
        const typeCounts = {};
        nodesData.forEach(node => {
            typeCounts[node.type] = (typeCounts[node.type] || 0) + 1;
        });
        
        const sortedTypes = Object.entries(typeCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10);
        
        const legendHTML = sortedTypes.map(([type, count]) => {
            const node = nodesData.find(n => n.type === type);
            return `
                <div class="legend-item">
                    <div class="legend-color" style="background: ${node.color}"></div>
                    <span>${type} (${count})</span>
                </div>
            `;
        }).join('');
        
        document.getElementById('legend-items').innerHTML = legendHTML;
        
        // Create network
        const container = document.getElementById('network');
        const nodes = new vis.DataSet(nodesData);
        const edges = new vis.DataSet(edgesData);
        
        const data = { nodes, edges };
        const options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: {
                    size: 14,
                    color: '#ffffff'
                },
                borderWidth: 2,
                borderWidthSelected: 4
            },
            edges: {
                width: 1,
                font: {
                    size: 11,
                    color: '#999',
                    background: '#1a1a2e'
                },
                smooth: {
                    type: 'continuous'
                }
            },
            physics: {
                forceAtlas2Based: {
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 150,
                    springConstant: 0.08,
                    avoidOverlap: 0.5
                },
                maxVelocity: 50,
                solver: 'forceAtlas2Based',
                stabilization: {
                    iterations: 150
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                zoomView: true,
                dragView: true
            }
        };
        
        const network = new vis.Network(container, data, options);
        
        let physicsTimeout;
        
        // Click handler - zoom to node, show info, and STOP PHYSICS
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = nodesData.find(n => n.id === nodeId);
                
                // STOP PHYSICS (stop rotation)
                network.setOptions({ physics: { enabled: false } });
                
                // Clear any existing timeout
                if (physicsTimeout) {
                    clearTimeout(physicsTimeout);
                }
                
                // Restart physics after 60 seconds
                physicsTimeout = setTimeout(() => {
                    network.setOptions({ physics: { enabled: true } });
                }, 60000); // 60 seconds
                
                // Zoom to node
                network.focus(nodeId, {
                    scale: 1.5,
                    animation: {
                        duration: 500,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                
                // Display info
                document.getElementById('node-info').innerHTML = node.fullInfo;
            }
        });
        
        // Double click - zoom in more (also stops physics)
        network.on('doubleClick', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                
                // STOP PHYSICS
                network.setOptions({ physics: { enabled: false } });
                
                // Clear and reset timeout
                if (physicsTimeout) {
                    clearTimeout(physicsTimeout);
                }
                physicsTimeout = setTimeout(() => {
                    network.setOptions({ physics: { enabled: true } });
                }, 60000);
                
                network.focus(nodeId, {
                    scale: 2.5,
                    animation: {
                        duration: 500,
                        easingFunction: 'easeInOutQuad'
                    }
                });
            }
        });
        
        console.log('Knowledge Graph loaded with', nodesData.length, 'nodes');
    </script>
</body>
</html>"""

# Save HTML file
output_file = f"{doc_folder}/knowledge_graph/interactive_kg.html"
print(f"\nSaving interactive visualization to {output_file}...")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_template)

print(f"✓ Interactive visualization created!")
print(f"\nOpen this file in your browser:")
print(f"  {output_file}")
