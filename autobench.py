import subprocess
import os
import json
import zipfile
import re
import toml
import importlib.util

def install_system_dependencies():
    """Install required system dependencies"""
    try:
        print("Installing system dependencies...")
        # Update package list and install required packages
        subprocess.run(["sudo", "apt-get", "update"], check=True)
        subprocess.run([
            "sudo", "apt-get", "install", "-y",
            "pkg-config", "libmysqlclient-dev", "python3-dev",
            "build-essential", "mariadb-client", "mariadb-server"
        ], check=True)
        print("System dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install system dependencies: {e}")
        raise

def create_bench(bench_name, bench_path):
    """Create a new Frappe bench if it doesn't exist"""
    try:
        if not os.path.exists(bench_path):
            print(f"Creating new bench '{bench_name}' at {bench_path}...")
            # Install system dependencies first
            install_system_dependencies()
            
            subprocess.run(["bench", "init", bench_name], cwd=os.path.dirname(bench_path), check=True)
            print(f"Bench '{bench_name}' created successfully")
            
            os.chdir(bench_path)
            # Install frappe
            subprocess.run(["bench", "get-app", "frappe"], check=True)
            print("Installed frappe in the new bench")
        else:
            print(f"Bench already exists at {bench_path}")
            os.chdir(bench_path)
    except subprocess.CalledProcessError as e:
        print(f"Failed to create bench: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error during bench creation: {e}")
        raise

def create_site(bench_path, site_name, admin_password):
    """Create a new site in the bench"""
    try:
        os.chdir(bench_path)
        if not os.path.exists(f"{bench_path}/sites/{site_name}"):
            print(f"Creating site '{site_name}'...")
            subprocess.run([
                "bench", "new-site", site_name,
                "--admin-password", admin_password,
                "--no-mariadb-socket"
            ], check=True)
            print(f"Site '{site_name}' created successfully")
            
            # Enable developer mode
            subprocess.run([
                "bench", "set-config", "--site", site_name,
                "developer_mode", "1"
            ], check=True)
            print(f"Developer mode enabled for site: {site_name}")
        else:
            print(f"Site '{site_name}' already exists")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create site: {e}")
        raise

def install_erpnext(bench_path, site_name):
    """Install ERPNext in the bench and site"""
    try:
        os.chdir(bench_path)
        print("Installing ERPNext...")
        subprocess.run(["bench", "get-app", "erpnext"], check=True)
        subprocess.run(["bench", "install-app", "erpnext", "--site", site_name], check=True)
        print("ERPNext installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install ERPNext: {e}")
        raise

# Step 1: Parse the user prompt
def parse_prompt(prompt):
    try:
        app_name_match = re.search(r"named\s+([a-z_]+)", prompt)
        if not app_name_match:
            raise ValueError("App name not found in prompt")
        app_name = app_name_match.group(1)

        if "with DocTypes:" not in prompt:
            raise ValueError("No DocTypes specified in prompt")
        doctype_section = prompt.split("with DocTypes:")[1].strip()
        doctypes = {}

        doctype_pattern = r"([A-Z]\w+)\s*\((.*?)\)(?:,|$)"
        doctype_matches = re.finditer(doctype_pattern, doctype_section)

        if not doctype_matches:
            raise ValueError("No valid DocTypes found in prompt")

        for match in doctype_matches:
            doctype_name, fields_raw = match.groups()
            fields = []

            field_pattern = r"(\w+):\s*([A-Za-z]+(?:\[[^\]]*\])?)"
            field_matches = re.finditer(field_pattern, fields_raw)

            for field_match in field_matches:
                fname, ftype = field_match.groups()
                field_dict = {"fieldname": fname, "label": fname.capitalize(), "fieldtype": ftype}

                if "[" in ftype:
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

# Step 2: Create a new Frappe app manually
def create_frappe_app(app_name, bench_path):
    try:
        os.chdir(bench_path)
        
        module_name = f"{app_name}_module"
        app_path = f"{bench_path}/apps/{app_name}"
        app_module_path = f"{app_path}/{app_name}"
        os.makedirs(app_module_path, exist_ok=True)

        with open(f"{app_path}/__init__.py", "w") as f:
            f.write("")
        with open(f"{app_module_path}/__init__.py", "w") as f:
            f.write("__version__ = '0.0.1'\n")

        pyproject_content = {
            "project": {
                "name": app_name,
                "version": "0.0.1",
                "description": f"A Frappe app named {app_name}",
                "authors": [{"name": "Prathamesh", "email": "prathamesh@example.com"}],
                "dependencies": ["frappe"],
            },
            "build-system": {
                "requires": ["flit_core >=3.2,<4"],
                "build-backend": "flit_core.buildapi"
            }
        }
        with open(f"{app_path}/pyproject.toml", "w") as f:
            toml.dump(pyproject_content, f)
        print(f"Created pyproject.toml for {app_name}")

        with open(f"{app_module_path}/modules.txt", "w") as f:
            f.write(module_name)

        hooks_content = f"""from . import __version__ as version

app_name = "{app_name}"
app_title = "{app_name.capitalize()}"
app_version = version
app_publisher = "Prathamesh"
app_description = "A custom Frappe app"
app_email = "prathamesh@example.com"
app_license = "MIT"
"""
        with open(f"{app_module_path}/hooks.py", "w") as f:
            f.write(hooks_content)

        print(f"Created app structure: {app_name}")

        subprocess.run(
            [f"{bench_path}/env/bin/python", "-m", "pip", "install", "-e", app_path],
            check=True
        )
        print(f"Installed app dependencies for {app_name}")

        return module_name
    except Exception as e:
        print(f"Failed to create app: {e}")
        raise

# Step 3: Create DocType files
def create_doctype(app_name, doctype_name, module_name, fields, bench_path):
    try:
        app_path = f"{bench_path}/apps/{app_name}/{app_name}"
        module_path = f"{app_path}/{module_name}"
        doctype_dir = f"{app_path}/doctype/{doctype_name.lower()}"

        os.makedirs(module_path, exist_ok=True)
        os.makedirs(doctype_dir, exist_ok=True)

        with open(f"{module_path}/__init__.py", "w") as f:
            f.write("")

        py_content = f"""from frappe.model.document import Document

class {doctype_name}(Document):
    pass
"""
        with open(f"{doctype_dir}/{doctype_name.lower()}.py", "w") as f:
            f.write(py_content)

        doctype_json = {
            "name": doctype_name,
            "module": module_name,
            "doctype": "DocType",
            "fields": fields,
            "issingle": 0,
            "istable": 0,
            "editable_grid": 1,
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
            ],
            "autoname": "field:.name" if any(f["fieldname"] == "name" for f in fields) else "prompt",
            "title_field": "name" if any(f["fieldname"] == "name" for f in fields) else fields[0]["fieldname"]
        }
        with open(f"{doctype_dir}/{doctype_name.lower()}.json", "w") as f:
            json.dump(doctype_json, f, indent=2)

        print(f"Created DocType: {doctype_name}")
    except Exception as e:
        print(f"Error creating DocType {doctype_name}: {e}")
        raise

# Step 4: Ensure site exists, install the app, and start the server
def ensure_site_and_install_app(app_name, bench_path, site_name, admin_password, host, port):
    try:
        os.chdir(bench_path)
        subprocess.run(["bench", "install-app", app_name, "--site", site_name], check=True)
        print(f"Installed app: {app_name} into site: {site_name}")

        # Start the server
        print("Starting Frappe server...")
        subprocess.Popen(["bench", "start"], cwd=bench_path)
        live_link = f"http://{host}:{port}"
        print(f"Server started. Access your app at: {live_link} (login with admin/{admin_password})")
    except subprocess.CalledProcessError as e:
        print(f"Failed during app installation or server start: {e}")
        raise

# Step 5: Create a zip file of the app
def create_zip(app_name, bench_path):
    try:
        app_path = f"{bench_path}/apps/{app_name}"
        zip_path = f"{bench_path}/{app_name}.zip"
        if os.path.exists(app_path):
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(app_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, f"{bench_path}/apps")
                        zipf.write(file_path, arcname)
            print(f"Created zip file: {zip_path}")
            return zip_path
        else:
            print(f"Warning: App directory '{app_path}' not found. Skipping zip creation.")
            return None
    except Exception as e:
        print(f"Error creating zip: {e}")
        return None

# Main function
def generate_frappe_app(prompt, bench_name, bench_path, site_name, admin_password, host, port):
    try:
        # Create bench, site, and install ERPNext
        create_bench(bench_name, bench_path)
        create_site(bench_path, site_name, admin_password)
        install_erpnext(bench_path, site_name)
        
        # Create and install custom app
        app_name, doctypes = parse_prompt(prompt)
        module_name = create_frappe_app(app_name, bench_path)
        for doctype_name, fields in doctypes.items():
            create_doctype(app_name, doctype_name, module_name, fields, bench_path)
        ensure_site_and_install_app(app_name, bench_path, site_name, admin_password, host, port)
        zip_path = create_zip(app_name, bench_path)
        
        if zip_path:
            print(f"App generation successful! Download your app at: {zip_path}")
        else:
            print(f"App generation partially successful. Site should still work, but zip creation failed.")
    except Exception as e:
        print(f"Failed to generate or install app: {e}")

if __name__ == "__main__":
    bench_name = input("Enter the name of the bench (e.g., test-bench): ").strip()
    bench_path = f"/home/prathamesh/{bench_name}"
    site_name = "site2.local"
    admin_password = "admin"
    host = "localhost"
    port = "8002"

    app_name = input("Enter the name of the app (e.g., library_management): ").strip()
    prompt = (
        f"Create an app named {app_name} with DocTypes: "
        "Article (title: Data, status: Select[Issued,Available]), "
        "Member (name: Data, membership_date: Date)"
    )
    
    print(f"Generated prompt: {prompt}")
    generate_frappe_app(prompt, bench_name, bench_path, site_name, admin_password, host, port)
