import os
import subprocess
import shutil
import json
import hashlib
import sys
import tempfile

def get_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def build():
    # Use paths relative to the script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    req_file = os.path.join(root_dir, "../src/requirements.txt")
    build_dir = os.path.join(root_dir, "builds")
    zip_path = os.path.join(build_dir, "layer") # .zip will be added
    
    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)
    
    # Use a temporary directory for staging
    with tempfile.TemporaryDirectory() as stage_dir:
        site_packages = os.path.join(stage_dir, "python/lib/python3.12/site-packages")
        os.makedirs(site_packages, exist_ok=True)
        
        # Run pip
        try:
            subprocess.check_call([
                "pip", "install", "-r", req_file, 
                "-t", site_packages, 
                "--platform", "manylinux2014_x86_64", 
                "--implementation", "cp", 
                "--python-version", "3.12", 
                "--only-binary=:all:", 
                "--upgrade"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Zip it up to a temporary file first
            temp_zip = os.path.join(tempfile.gettempdir(), f"layer_{os.getpid()}")
            shutil.make_archive(temp_zip, 'zip', stage_dir)
            
            # Move the zip to the final location atomically
            final_zip = zip_path + ".zip"
            shutil.move(temp_zip + ".zip", final_zip)
            
            return os.path.abspath(final_zip)
        except Exception as e:
            sys.stderr.write(str(e))
            sys.exit(1)

if __name__ == "__main__":
    path = build()
    print(json.dumps({"path": path}))
