
import json
import matplotlib.pyplot as plt
import numpy as np
import os

INPUT_FILE = "evaluation_results.json"
OUTPUT_DIR = "static/plots"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def load_results():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run evaluation first.")
        return []
    with open(INPUT_FILE, 'r') as f:
        return json.load(f)

def plot_accuracy_comparison(results):
    ids = [r['id'] for r in results]
    kg_scores = [r['kg_score'] * 100 for r in results]
    vec_scores = [r['vector_score'] * 100 for r in results]

    x = np.arange(len(ids))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    rects1 = ax.bar(x - width/2, kg_scores, width, label='KG RAG', color='#4CAF50', alpha=0.8)
    rects2 = ax.bar(x + width/2, vec_scores, width, label='Vector RAG', color='#2196F3', alpha=0.8)

    ax.set_ylabel('Keyword Accuracy Score (%)')
    ax.set_title('Answer Accuracy by Question (Keyword Match)')
    ax.set_xticks(x)
    ax.set_xticklabels(ids)
    ax.legend()
    
    # Add labels
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{int(height)}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)

    autolabel(rects1)
    autolabel(rects2)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/accuracy_comparison.png")
    print(f"Saved {OUTPUT_DIR}/accuracy_comparison.png")
    plt.close()

def plot_latency_comparison(results):
    ids = [r['id'] for r in results]
    kg_lat = [r['kg_latency'] for r in results]
    vec_lat = [r['vector_latency'] for r in results]

    x = np.arange(len(ids))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    rects1 = ax.bar(x - width/2, kg_lat, width, label='KG RAG', color='#FF9800', alpha=0.8)
    rects2 = ax.bar(x + width/2, vec_lat, width, label='Vector RAG', color='#9C27B0', alpha=0.8)

    ax.set_ylabel('Latency (seconds)')
    ax.set_title('Response Time by Question')
    ax.set_xticks(x)
    ax.set_xticklabels(ids)
    ax.legend()

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/latency_comparison.png")
    print(f"Saved {OUTPUT_DIR}/latency_comparison.png")
    plt.close()

def plot_radar_chart(results):
    # Calculate aggregate metrics
    categories = ['Accuracy', 'Speed (Inv Latency)', 'Financial Qs', 'Reasoning Qs', 'Consistency']
    
    # Helper to safe mean
    def mean(lst): return sum(lst) / len(lst) if lst else 0

    # 1. Accuracy
    kg_acc = mean([r['kg_score'] for r in results])
    vec_acc = mean([r['vector_score'] for r in results])

    # 2. Speed (Normalize: 10s = 0, 0s = 1)
    avg_kg_lat = mean([r['kg_latency'] for r in results])
    avg_vec_lat = mean([r['vector_latency'] for r in results])
    kg_speed = max(0, 1 - (avg_kg_lat / 15)) 
    vec_speed = max(0, 1 - (avg_vec_lat / 15))

    # 3. Financial (Q5, Q9)
    fin_qs = [r for r in results if r['category'] in ['Financial', 'Complex Financial']]
    kg_fin = mean([r['kg_score'] for r in fin_qs])
    vec_fin = mean([r['vector_score'] for r in fin_qs])

    # 4. Reasoning/Synthesis (Q7, Q8, Q10)
    reason_qs = [r for r in results if r['category'] in ['Reasoning', 'Synthesis', 'Specificity']]
    kg_reas = mean([r['kg_score'] for r in reason_qs])
    vec_reas = mean([r['vector_score'] for r in reason_qs])
    
    # 5. Consistency (Variance of scores - Inverse)
    kg_var = np.var([r['kg_score'] for r in results])
    vec_var = np.var([r['vector_score'] for r in results])
    kg_cons = 1 - (kg_var * 2) # Arbitrary scaling
    vec_cons = 1 - (vec_var * 2)

    # Prepare data
    kg_stats = [kg_acc, kg_speed, kg_fin, kg_reas, kg_cons]
    vec_stats = [vec_acc, vec_speed, vec_fin, vec_reas, vec_cons]
    
    # Normalize to 0-1
    kg_stats = [max(0, min(1, x)) for x in kg_stats]
    vec_stats = [max(0, min(1, x)) for x in vec_stats]

    # Radar Chart
    angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False)
    
    # Close the loop
    kg_stats = np.concatenate((kg_stats, [kg_stats[0]]))
    vec_stats = np.concatenate((vec_stats, [vec_stats[0]]))
    angles = np.concatenate((angles, [angles[0]]))

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    ax.plot(angles, kg_stats, 'o-', linewidth=2, label='KG RAG', color='#4CAF50')
    ax.fill(angles, kg_stats, alpha=0.25, color='#4CAF50')
    
    ax.plot(angles, vec_stats, 'o-', linewidth=2, label='Vector RAG', color='#2196F3')
    ax.fill(angles, vec_stats, alpha=0.25, color='#2196F3')

    ax.set_thetagrids(angles[:-1] * 180/np.pi, categories)
    ax.set_title('RAG System Capability Profile', y=1.1)
    ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/radar_comparison.png")
    print(f"Saved {OUTPUT_DIR}/radar_comparison.png")
    plt.close()

if __name__ == "__main__":
    results = load_results()
    if results:
        print(f"Loaded {len(results)} results. Generating plots...")
        plot_accuracy_comparison(results)
        plot_latency_comparison(results)
        plot_radar_chart(results)
        print("Done.")
