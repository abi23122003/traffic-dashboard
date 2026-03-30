"""
Auto-update PPT when source code changes
Run this in background to keep PPT synchronized with code
"""

import time
import os
from pathlib import Path
from datetime import datetime
import hashlib

class PPTSync:
    """Monitor source code and auto-update PPT"""
    
    def __init__(self, project_path="."):
        self.project_path = Path(project_path)
        self.file_hashes = {}
        self.monitor_extensions = ['.py', '.txt', '.env']
        
    def get_file_hash(self, filepath):
        """Calculate file hash"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def scan_files(self):
        """Scan all relevant files"""
        files = []
        for ext in self.monitor_extensions:
            files.extend(self.project_path.rglob(f"*{ext}"))
        return files
    
    def check_changes(self):
        """Check for file changes"""
        changed = []
        for file in self.scan_files():
            if file.name in ['__pycache__', '.git']:
                continue
            
            current_hash = self.get_file_hash(file)
            if str(file) not in self.file_hashes:
                self.file_hashes[str(file)] = current_hash
            elif self.file_hashes[str(file)] != current_hash:
                changed.append(file)
                self.file_hashes[str(file)] = current_hash
        
        return changed
    
    def run_monitor(self):
        """Run monitoring loop"""
        print("🔍 Starting PPT Sync Monitor...")
        print("📁 Watching for changes in source code files")
        print("🔄 PPT will auto-update when changes are detected")
        print("Press Ctrl+C to stop\n")
        
        last_ppt_update = datetime.now()
        
        try:
            while True:
                changed_files = self.check_changes()
                
                if changed_files:
                    print(f"\n📝 Changes detected in {len(changed_files)} file(s):")
                    for file in changed_files:
                        print(f"   • {file.name}")
                    
                    # Update PPT
                    print("🔄 Updating PowerPoint presentation...")
                    try:
                        # Import and run the PPT generator
                        from generate_ppt import TrafficDashboardPPTGenerator
                        generator = TrafficDashboardPPTGenerator()
                        generator.generate_all_slides()
                        generator.save("Project_Review_2_Traffic_Dashboard.pptx")
                        print(f"✅ PPT updated at {datetime.now().strftime('%H:%M:%S')}")
                        last_ppt_update = datetime.now()
                    except Exception as e:
                        print(f"❌ Error updating PPT: {e}")
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped. PPT is up to date!")
            print(f"Last update: {last_ppt_update.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    monitor = PPTSync()
    monitor.run_monitor()