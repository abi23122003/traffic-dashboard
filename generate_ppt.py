"""
System Block Diagram Generator for Traffic Route Analysis Dashboard
Generates a professional block diagram as PNG and PDF images
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon
import matplotlib.lines as mlines
import numpy as np

def create_system_block_diagram():
    """Create a professional system block diagram"""
    
    # Create figure with high DPI for quality
    fig, ax = plt.subplots(1, 1, figsize=(20, 14), dpi=300)
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 14)
    ax.axis('off')
    
    # Set background color
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Title
    ax.text(10, 13.5, 'Traffic Route Analysis Dashboard - System Architecture', 
            fontsize=20, fontweight='bold', ha='center', 
            fontname='Times New Roman', color='#1a237e')
    
    # Subtitle
    ax.text(10, 13, 'Real-Time Congestion Analysis with ML Predictions', 
            fontsize=12, ha='center', fontname='Times New Roman', 
            color='#666666', style='italic')
    
    # Define colors for different layers
    colors = {
        'user': '#E3F2FD',      # Light Blue
        'frontend': '#F3E5F5',   # Light Purple
        'backend': '#FFF3E0',     # Light Orange
        'processing': '#E8F5E9',  # Light Green
        'storage': '#FFE0B2',     # Light Amber
        'external': '#FCE4EC',    # Light Pink
        'ml': '#E0F7FA',          # Light Cyan
        'admin': '#F1F8E9'        # Light Lime
    }
    
    # Border color
    border_color = '#2c3e50'
    border_width = 2
    
    # =========================================================================
    # LAYER 1: USER INTERFACE LAYER (Top)
    # =========================================================================
    user_box = FancyBboxPatch((1, 11.2), 18, 1.3, 
                               boxstyle="round,pad=0.08",
                               facecolor=colors['user'], 
                               edgecolor=border_color, 
                               linewidth=border_width)
    ax.add_patch(user_box)
    
    # User Interface Title
    ax.text(10, 11.9, 'USER INTERFACE LAYER', fontsize=14, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#0d47a1')
    
    # UI Components
    ui_components = [
        ('Web Browser', 2.5, 11.4),
        ('Mobile View', 6, 11.4),
        ('Admin Panel', 9.5, 11.4),
        ('API Docs', 13, 11.4),
        ('Reports', 16.5, 11.4)
    ]
    
    for text, x, y in ui_components:
        ax.text(x, y, text, fontsize=9, ha='center', fontname='Times New Roman')
    
    # =========================================================================
    # LAYER 2: FRONTEND COMPONENTS
    # =========================================================================
    frontend_box = FancyBboxPatch((1, 9.5), 18, 1.4, 
                                   boxstyle="round,pad=0.08",
                                   facecolor=colors['frontend'], 
                                   edgecolor=border_color, 
                                   linewidth=border_width)
    ax.add_patch(frontend_box)
    
    ax.text(10, 10.5, 'FRONTEND COMPONENTS', fontsize=14, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#4a148c')
    
    # Frontend Components
    frontend_items = [
        ('Leaflet Maps', 2.5, 9.9),
        ('Route Visualization', 6, 9.9),
        ('Analytics Charts', 9.5, 9.9),
        ('User Dashboard', 13, 9.9),
        ('Forms & Input', 16.5, 9.9)
    ]
    
    for text, x, y in frontend_items:
        ax.text(x, y, text, fontsize=9, ha='center', fontname='Times New Roman')
    
    # Arrow between UI and Frontend
    ax.annotate('', xy=(10, 9.5), xytext=(10, 11.2),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#666', 
                               connectionstyle="arc3,rad=0"))
    
    # =========================================================================
    # LAYER 3: BACKEND API LAYER
    # =========================================================================
    backend_box = FancyBboxPatch((1, 7.5), 18, 1.6, 
                                  boxstyle="round,pad=0.08",
                                  facecolor=colors['backend'], 
                                  edgecolor=border_color, 
                                  linewidth=border_width)
    ax.add_patch(backend_box)
    
    ax.text(10, 8.7, 'BACKEND API LAYER (FastAPI)', fontsize=14, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#e65100')
    
    # Backend Endpoints
    endpoints = [
        ('/analyze-route', 1.5, 8.0),
        ('/autocomplete', 4, 8.0),
        ('/api/auth', 6.5, 8.0),
        ('/api/export', 9, 8.0),
        ('/api/analytics', 11.5, 8.0),
        ('/api/realtime', 14, 8.0),
        ('/admin', 17, 8.0)
    ]
    
    for text, x, y in endpoints:
        ax.text(x, y, text, fontsize=8, ha='center', fontname='Courier New', 
                color='#bf360c')
    
    # Arrow between Frontend and Backend
    ax.annotate('', xy=(10, 7.5), xytext=(10, 9.5),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#666'))
    
    # =========================================================================
    # LAYER 4: BUSINESS LOGIC & PROCESSING
    # =========================================================================
    processing_box = FancyBboxPatch((1, 5.3), 18, 1.8, 
                                     boxstyle="round,pad=0.08",
                                     facecolor=colors['processing'], 
                                     edgecolor=border_color, 
                                     linewidth=border_width)
    ax.add_patch(processing_box)
    
    ax.text(10, 6.6, 'BUSINESS LOGIC & PROCESSING LAYER', fontsize=14, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#1b5e20')
    
    # Processing Modules - Row 1
    modules_row1 = [
        ('Route Analyzer', 2, 5.9),
        ('Geocoding', 4.5, 5.9),
        ('Route Summarizer', 7, 5.9),
        ('Congestion Calc', 9.5, 5.9),
        ('Cost Optimizer', 12, 5.9),
        ('ML Predictor', 14.5, 5.9),
        ('Feature Engine', 17, 5.9)
    ]
    
    for text, x, y in modules_row1:
        ax.text(x, y, text, fontsize=8, ha='center', fontname='Times New Roman')
    
    # Processing Modules - Row 2
    modules_row2 = [
        ('Peak Hours', 2, 5.5),
        ('Day Analysis', 4.5, 5.5),
        ('Seasonal Trends', 7, 5.5),
        ('Reliability Score', 9.5, 5.5),
        ('Export Service', 12, 5.5),
        ('Notification', 14.5, 5.5),
        ('Cache Manager', 17, 5.5)
    ]
    
    for text, x, y in modules_row2:
        ax.text(x, y, text, fontsize=8, ha='center', fontname='Times New Roman')
    
    # Arrow between Backend and Processing
    ax.annotate('', xy=(10, 5.3), xytext=(10, 7.5),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#666'))
    
    # =========================================================================
    # LAYER 5: ML MODEL LAYER (Special)
    # =========================================================================
    ml_box = FancyBboxPatch((1, 3.8), 8.5, 1.2, 
                            boxstyle="round,pad=0.08",
                            facecolor=colors['ml'], 
                            edgecolor=border_color, 
                            linewidth=border_width)
    ax.add_patch(ml_box)
    
    ax.text(5.25, 4.4, 'ML MODEL LAYER', fontsize=11, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#006064')
    
    ml_items = [
        ('RandomForest', 3, 4.0),
        ('85% Accuracy', 5.25, 4.0),
        ('Congestion Prediction', 7.5, 4.0)
    ]
    
    for text, x, y in ml_items:
        ax.text(x, y, text, fontsize=8, ha='center', fontname='Times New Roman')
    
    # =========================================================================
    # LAYER 6: DATA STORAGE LAYER
    # =========================================================================
    storage_box = FancyBboxPatch((10.5, 3.8), 8.5, 1.2, 
                                  boxstyle="round,pad=0.08",
                                  facecolor=colors['storage'], 
                                  edgecolor=border_color, 
                                  linewidth=border_width)
    ax.add_patch(storage_box)
    
    ax.text(14.75, 4.4, 'DATA STORAGE LAYER', fontsize=11, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#bf360c')
    
    storage_items = [
        ('SQLite/PostgreSQL', 12.5, 4.0),
        ('Redis Cache', 14.75, 4.0),
        ('File System', 17, 4.0)
    ]
    
    for text, x, y in storage_items:
        ax.text(x, y, text, fontsize=8, ha='center', fontname='Times New Roman')
    
    # Arrows to ML and Storage
    ax.annotate('', xy=(5.25, 3.8), xytext=(5.25, 5.3),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#666'))
    
    ax.annotate('', xy=(14.75, 3.8), xytext=(14.75, 5.3),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='#666'))
    
    # =========================================================================
    # LAYER 7: EXTERNAL INTEGRATIONS
    # =========================================================================
    external_box = FancyBboxPatch((1, 2), 18, 1.4, 
                                   boxstyle="round,pad=0.08",
                                   facecolor=colors['external'], 
                                   edgecolor=border_color, 
                                   linewidth=border_width)
    ax.add_patch(external_box)
    
    ax.text(10, 3, 'EXTERNAL INTEGRATIONS', fontsize=13, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#ad1457')
    
    # External Services
    external_items = [
        ('TomTom API', 2, 2.4),
        ('Power BI', 5, 2.4),
        ('SMTP Email', 8, 2.4),
        ('OpenStreetMap', 11, 2.4),
        ('Google Maps', 14, 2.4),
        ('Weather API', 17, 2.4)
    ]
    
    for text, x, y in external_items:
        ax.text(x, y, text, fontsize=9, ha='center', fontname='Times New Roman')
    
    # Arrows from ML and Storage to External
    ax.annotate('', xy=(2, 2.4), xytext=(5.25, 3.8),
                arrowprops=dict(arrowstyle='->', lw=1, color='#999', linestyle='--'))
    
    ax.annotate('', xy=(5, 2.4), xytext=(14.75, 3.8),
                arrowprops=dict(arrowstyle='->', lw=1, color='#999', linestyle='--'))
    
    ax.annotate('', xy=(14, 2.4), xytext=(14.75, 3.8),
                arrowprops=dict(arrowstyle='->', lw=1, color='#999', linestyle='--'))
    
    # =========================================================================
    # LAYER 8: ADMIN DASHBOARD
    # =========================================================================
    admin_box = FancyBboxPatch((1, 0.5), 18, 1.2, 
                                boxstyle="round,pad=0.08",
                                facecolor=colors['admin'], 
                                edgecolor=border_color, 
                                linewidth=border_width)
    ax.add_patch(admin_box)
    
    ax.text(10, 1.1, 'ADMIN DASHBOARD & MONITORING', fontsize=12, fontweight='bold',
            ha='center', fontname='Times New Roman', color='#33691e')
    
    admin_items = [
        ('User Management', 3, 0.7),
        ('System Logs', 6, 0.7),
        ('Performance Metrics', 9.5, 0.7),
        ('Cache Control', 13, 0.7),
        ('Report Generator', 16.5, 0.7)
    ]
    
    for text, x, y in admin_items:
        ax.text(x, y, text, fontsize=9, ha='center', fontname='Times New Roman')
    
    # Arrow from Admin to Backend
    ax.annotate('', xy=(10, 0.5), xytext=(10, 1.7),
                arrowprops=dict(arrowstyle='<->', lw=1, color='#999', linestyle=':'))
    
    # =========================================================================
    # LEGEND
    # =========================================================================
    legend_x = 15
    legend_y = 5.5
    
    # Create legend items
    legend_items = [
        ('User Interface', colors['user']),
        ('Frontend', colors['frontend']),
        ('Backend API', colors['backend']),
        ('Processing', colors['processing']),
        ('ML Model', colors['ml']),
        ('Data Storage', colors['storage']),
        ('External', colors['external']),
        ('Admin', colors['admin'])
    ]
    
    for i, (text, color) in enumerate(legend_items):
        rect = Rectangle((legend_x, legend_y - i*0.3), 0.2, 0.2, 
                         facecolor=color, edgecolor=border_color, linewidth=1)
        ax.add_patch(rect)
        ax.text(legend_x + 0.3, legend_y - i*0.3 + 0.05, text, 
                fontsize=8, va='center', fontname='Times New Roman')
    
    # Data Flow Legend
    ax.text(legend_x, legend_y - 2.5, 'Data Flow:', fontsize=9, fontweight='bold',
            fontname='Times New Roman')
    
    line_solid = mlines.Line2D([legend_x, legend_x+0.5], [legend_y - 2.8, legend_y - 2.8],
                                color='#666', linewidth=1.5)
    ax.add_line(line_solid)
    ax.text(legend_x + 0.6, legend_y - 2.85, 'Primary Flow', fontsize=8, fontname='Times New Roman')
    
    line_dashed = mlines.Line2D([legend_x, legend_x+0.5], [legend_y - 3.1, legend_y - 3.1],
                                 color='#999', linewidth=1.5, linestyle='--')
    ax.add_line(line_dashed)
    ax.text(legend_x + 0.6, legend_y - 3.15, 'Secondary Flow', fontsize=8, fontname='Times New Roman')
    
    line_dotted = mlines.Line2D([legend_x, legend_x+0.5], [legend_y - 3.4, legend_y - 3.4],
                                 color='#999', linewidth=1, linestyle=':')
    ax.add_line(line_dotted)
    ax.text(legend_x + 0.6, legend_y - 3.45, 'Admin Control', fontsize=8, fontname='Times New Roman')
    
    # Add a decorative border around the diagram
    border = Rectangle((0.2, 0.2), 19.6, 13.4, 
                        fill=False, edgecolor='#cccccc', linewidth=1, linestyle='-')
    ax.add_patch(border)
    
    # Save the diagram
    plt.tight_layout()
    
    # Save as PNG (high resolution)
    plt.savefig('system_block_diagram.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print("✅ System block diagram saved as 'system_block_diagram.png'")
    
    # Save as PDF (vector format for presentations)
    plt.savefig('system_block_diagram.pdf', bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print("✅ System block diagram saved as 'system_block_diagram.pdf'")
    
    # Also save a smaller version for web
    plt.savefig('system_block_diagram_small.png', dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    print("✅ Small version saved as 'system_block_diagram_small.png'")
    
    plt.show()
    
    return "Diagram created successfully!"

# Run the diagram generator
if __name__ == "__main__":
    create_system_block_diagram()