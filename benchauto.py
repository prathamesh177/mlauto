import subprocess
import os
import json
import zipfile
import re
import time
import sys

# Configuration
BENCH_PATH = "/home/prathamesh/my-bench"  # Replace with your actual Frappe bench path
DEFAULT_MODULE = "custom_module"  # Default module name for DocTypes
SITE_NAME = "site1.local"  # Default site name (can be overridden if needed)
ADMIN_PASSWORD = "admin"  # Default admin password for new site

# Step 1: Parse the user prompt
def parse_prompt(prompt):
    """
    Parse a prompt like:
    "Create an app named test with DocTypes: Article (title: Data, status: Select[Issued,Available]), Member (name: Data, membership_date: Date)"
    Returns app_name and a dict of DocTypes with their fields.
    """
    try:
        # Extract app name
        app_name_match = re.search(r"named\s+([a-z_]+)", prompt)
        if not app_name_match:
            raise ValueError("App name not found in prompt")
        app_name = app_name_match.group(1)

        # Extract DocTypes part
        if "with DocTypes:" not in prompt:
            raise ValueError("No DocTypes specified in prompt")
        doctype_section = prompt.split("with DocTypes:")[1].strip()
        doctypes = {}

        # Match DocType entries (e.g., "Article (title: Data, ...)")
        doctype_pattern = r"([A-Z]\w+)\s*\((.*?)\)(?:,|$)"
        doctype_matches = re.finditer(doctype_pattern, doctype_section)

        if not doctype_matches:
            raise ValueError("No valid DocTypes found in prompt")

        for match in re.finditer(doctype_pattern, doctype_section):
            doctype_name, fields_raw = match.groups()
            fields = []

            # Parse fields (e.g., "title: Data" or "status: Select[Issued,Available]")
            field_pattern = r"(\w+):\s*([A-Za-z]+(?:\[[^\]]*\])?)"
            field_matches = re.finditer(field_pattern, fields_raw)

            for field_match in field_matches:
                fname, ftype = field_match.groups()
                field_dict = {
                    "fieldname": fname, 
                    "label": fname.capitalize(), 
                    "fieldtype": ftype,
                    "reqd": 1 if fname == "name" else 0  # Make name field required
                }

                if "[" in ftype:  # Handle Select with options
                    base_type, options = ftype.split("[", 1)
                    options = options.rstrip("]").replace(",", "\n")
                    field_dict["fieldtype"] = base_type
                    field_dict["options"] = options
                fields.append(field_dict)

            if not fields:
                raise ValueError(f"No valid fields found for DocType: {doctype_name}")
            doctypes[doctype_name] = fields

        if not doctypes:
            raise ValueError("Failed to parse any DocTypes")
        return app_name, doctypes
    except Exception as e:
        print(f"Error parsing prompt: {e}")
        raise

# Step 2: Create a new Frappe app
def create_frappe_app(app_name):
    """Use bench CLI to create a new Frappe app."""
    try:
        os.chdir(BENCH_PATH)
        # First, check if the app already exists and remove it if it does
        app_path = f"{BENCH_PATH}/apps/{app_name}"
        if os.path.exists(app_path):
            print(f"App directory {app_path} already exists. Removing it...")
            subprocess.run(["rm", "-rf", app_path], check=True)
        
        # Create the new app
        subprocess.run(["bench", "new-app", app_name, "--no-git"], check=True)
        print(f"Created app: {app_name}")
        
        # Verify that hooks.py exists and is accessible
        hooks_file = f"{BENCH_PATH}/apps/{app_name}/{app_name}/hooks.py"
        if not os.path.exists(hooks_file):
            raise FileNotFoundError(f"hooks.py file not found at {hooks_file}")
            
        # Add module to modules.txt
        module_file = f"{BENCH_PATH}/apps/{app_name}/{app_name}/modules.txt"
        if os.path.exists(module_file):
            with open(module_file, "r") as f:
                modules_content = f.read()
            
            if DEFAULT_MODULE not in modules_content:
                with open(module_file, "a") as f:
                    f.write(f"\n{DEFAULT_MODULE}")
        else:
            with open(module_file, "w") as f:
                f.write(f"{app_name}\n{DEFAULT_MODULE}")
        
        # Update hooks.py to ensure module is recognized
        with open(hooks_file, "r") as f:
            hooks_content = f.read()
            
        if "app_modules" not in hooks_content:
            with open(hooks_file, "a") as f:
                f.write(f'\napp_modules = ["{DEFAULT_MODULE}"]\n')
            
        # Create module directory and __init__.py
        module_path = f"{BENCH_PATH}/apps/{app_name}/{app_name}/{DEFAULT_MODULE}"
        os.makedirs(module_path, exist_ok=True)
        
        # Create __init__.py for module
        with open(f"{module_path}/__init__.py", "w") as f:
            f.write("")
            
        # Create doctype directory structure
        doctype_path = f"{module_path}/doctype"
        os.makedirs(doctype_path, exist_ok=True)
        
        # Create __init__.py for doctype path
        with open(f"{doctype_path}/__init__.py", "w") as f:
            f.write("")
            
        print(f"App structure created for {app_name}")
        
        # Add to installed_apps in sites/apps.txt if not already there
        apps_file = f"{BENCH_PATH}/sites/apps.txt"
        if os.path.exists(apps_file):
            with open(apps_file, "r") as f:
                installed_apps = f.read().splitlines()
            
            if app_name not in installed_apps:
                with open(apps_file, "a") as f:
                    f.write(f"\n{app_name}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create app: {e}")
        raise
    except Exception as e:
        print(f"Error in app creation: {str(e)}")
        raise

# Step 3: Create DocType files
def create_doctype(app_name, doctype_name, fields):
    """Generate .py and .json files for a DocType."""
    try:
        app_path = f"{BENCH_PATH}/apps/{app_name}/{app_name}"
        doctype_dir = f"{app_path}/{DEFAULT_MODULE}/doctype/{doctype_name.lower()}"

        # Create needed directories
        os.makedirs(doctype_dir, exist_ok=True)
        
        # Create __init__.py files for proper Python package structure
        with open(f"{doctype_dir}/__init__.py", "w") as f:
            f.write("")

        # Create .py file
        py_content = f"""from frappe.model.document import Document

class {doctype_name}(Document):
    pass
"""
        with open(f"{doctype_dir}/{doctype_name.lower()}.py", "w") as f:
            f.write(py_content)

        # Create .json file with enhanced configuration
        doctype_json = {
            "name": doctype_name,
            "module": DEFAULT_MODULE,
            "doctype": "DocType",
            "custom": 0,
            "fields": fields,
            "issingle": 0,
            "istable": 0,
            "editable_grid": 1,
            "quick_entry": 1,
            "track_changes": 1,
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1,
                    "submit": 0,
                    "cancel": 0,
                    "amend": 0,
                    "report": 1,
                    "import": 1,
                    "export": 1
                }
            ],
            "sort_field": "modified",
            "sort_order": "DESC",
            "autoname": "field:name" if any(f["fieldname"] == "name" for f in fields) else "prompt",
            "title_field": "name" if any(f["fieldname"] == "name" for f in fields) else fields[0]["fieldname"],
            "search_fields": ",".join(field["fieldname"] for field in fields[:3] if field["fieldtype"] in ["Data", "Link", "Select"])
        }
        
        with open(f"{doctype_dir}/{doctype_name.lower()}.json", "w") as f:
            json.dump(doctype_json, f, indent=2)

        print(f"Created DocType: {doctype_name}")
    except Exception as e:
        print(f"Error creating DocType {doctype_name}: {e}")
        raise

# Step 4: Ensure site exists and install the app
def ensure_site_and_install_app(app_name):
    """Check if site exists, create it if not, and install the app."""
    try:
        os.chdir(BENCH_PATH)
        sites_dir = f"{BENCH_PATH}/sites"
        site_path = f"{sites_dir}/{SITE_NAME}"

        # Check if site exists
        if not os.path.exists(site_path):
            print(f"Site {SITE_NAME} does not exist. Creating it now...")
            # Create new site with default admin password
            subprocess.run(
                ["bench", "new-site", SITE_NAME, "--admin-password", ADMIN_PASSWORD, "--no-mariadb-socket"],
                check=True
            )
            print(f"Created site: {SITE_NAME}")

            # Enable developer mode for the new site
            subprocess.run(
                ["bench", "--site", SITE_NAME, "set-config", "developer_mode", "1"],
                check=True
            )
            print(f"Enabled developer mode for site: {SITE_NAME}")
        
        # Verify that the app is properly recognized by Frappe
        apps_path = f"{BENCH_PATH}/sites/apps.txt"
        with open(apps_path, "r") as f:
            apps_list = f.read().splitlines()
        
        if app_name not in apps_list:
            print(f"Adding {app_name} to apps.txt...")
            with open(apps_path, "a") as f:
                f.write(f"\n{app_name}")
        
        # Make sure Python can find the app modules
        print(f"Checking Python path: {sys.path}")
        app_module_path = f"{BENCH_PATH}/apps/{app_name}"
        if app_module_path not in sys.path:
            sys.path.append(app_module_path)
            print(f"Added {app_module_path} to Python path")
        
        # Verify the app's hooks.py is importable
        try:
            import importlib
            hooks_module = f"{app_name}.hooks"
            importlib.import_module(hooks_module)
            print(f"Successfully imported {hooks_module}")
        except ImportError as e:
            print(f"Warning: Could not import hooks module: {e}")
            # Create a symlink to the app in the Python path if needed
            subprocess.run(["ln", "-sf", f"{BENCH_PATH}/apps/{app_name}/{app_name}", f"/usr/local/lib/python3.10/dist-packages/{app_name}"], check=False)
            print(f"Created symlink for {app_name} module")

        # Install the app into the site
        print(f"Installing app {app_name} into site {SITE_NAME}...")
        result = subprocess.run(["bench", "--site", SITE_NAME, "install-app", app_name], 
                                capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error installing app: {result.stderr}")
            
            # Try alternative installation method
            print("Trying alternative installation method...")
            subprocess.run(["bench", "setup", "requirements"], check=True)
            subprocess.run(["bench", "--site", "all", "clear-cache"], check=True)
            subprocess.run(["bench", "build"], check=True)
            
            # Try forcing the installation
            subprocess.run(["bench", "--site", SITE_NAME, "install-app", app_name, "--force"], check=True)
        
        print(f"Installed app: {app_name} into site: {SITE_NAME}")

        # Run migrations to ensure DocTypes are registered
        subprocess.run(["bench", "--site", SITE_NAME, "migrate"], check=True)
        print(f"Ran migrations for site: {SITE_NAME}")
        
        # Build assets to ensure everything is properly loaded
        subprocess.run(["bench", "build"], check=True)
        print(f"Built assets for better UI experience")
        
        # Start bench if it's not already running (in a separate thread to avoid blocking)
        try:
            result = subprocess.run(["pgrep", "-f", "bench start"], capture_output=True, text=True)
            if not result.stdout.strip():
                print("Starting bench server in the background...")
                subprocess.Popen(["bench", "start"], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
                # Wait a bit for server to start
                time.sleep(3)
        except Exception as e:
            print(f"Note: Could not start bench automatically: {e}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create site or install app: {e}")
        raise
    except Exception as e:
        print(f"Error during site setup: {str(e)}")
        raise

# Step 5: Create a zip file of the app
def create_zip(app_name):
    """Package the app folder into a zip file."""
    try:
        app_path = f"{BENCH_PATH}/apps/{app_name}"
        zip_path = f"{BENCH_PATH}/{app_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(app_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, f"{BENCH_PATH}/apps")
                    zipf.write(file_path, arcname)
        print(f"Created zip file: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Error creating zip: {e}")
        raise

# Main function to tie everything together
def generate_frappe_app(prompt):
    """Generate a Frappe app based on the prompt, install it, and return the zip file path."""
    try:
        # Parse the prompt
        app_name, doctypes = parse_prompt(prompt)

        # Create the app
        create_frappe_app(app_name)

        # Create each DocType
        for doctype_name, fields in doctypes.items():
            create_doctype(app_name, doctype_name, fields)

        # Ensure site exists and install the app
        ensure_site_and_install_app(app_name)

        # Create and return the zip file
        zip_path = create_zip(app_name)
        
        print(f"\nSUCCESS: App '{app_name}' created with {len(doctypes)} DocTypes!")
        print(f"You can access your Frappe Desk at http://{SITE_NAME}:8000")
        print(f"Login with username: Administrator, password: {ADMIN_PASSWORD}")
        print(f"Your DocTypes are available in the module: {DEFAULT_MODULE}")
        
        return zip_path
    except Exception as e:
        print(f"Failed to generate or install app: {e}")
        return None

# Example usage
if __name__ == "__main__":
    # Configuration
    BENCH_PATH = "/home/prathamesh/my-bench"  # Ensure this is correct
    SITE_NAME = "site1.local"  # Default site name
    ADMIN_PASSWORD = "admin"  # Default admin password

    # Test prompt
    prompt = (
        "Create an app named test with DocTypes: "
        "Article (title: Data, status: Select[Issued,Available]), "
        "Member (name: Data, membership_date: Date)"
    )
    
    zip_file = generate_frappe_app(prompt)
    if zip_file:
        print(f"App generation and installation successful! Download your app at: {zip_file}")
        print(f"Check your Frappe Desk at http://{SITE_NAME}:8000 (login with admin/{ADMIN_PASSWORD})")
    else:
        print("App generation or installation failed.")
