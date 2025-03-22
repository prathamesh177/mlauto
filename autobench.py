import subprocess
import os
import json
import zipfile
import re
import toml
import importlib.util

# Configuration
BENCH_PATH = "/home/prathamesh/todo-bench"
SITE_NAME = "site1.local"
ADMIN_PASSWORD = "admin"
HOST = "localhost"
PORT = "8002"

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
def create_frappe_app(app_name):
    try:
        os.chdir(BENCH_PATH)
        
        # Define a unique module name based on app_name
        module_name = f"{app_name}_module"

        # Create app directory structure
        app_path = f"{BENCH_PATH}/apps/{app_name}"
        app_module_path = f"{app_path}/{app_name}"
        os.makedirs(app_module_path, exist_ok=True)

        # Create basic files
        with open(f"{app_path}/__init__.py", "w") as f:
            f.write("")
        with open(f"{app_module_path}/__init__.py", "w") as f:
            f.write("__version__ = '0.0.1'\n")

        # Create pyproject.toml
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

        # Create modules.txt with unique module name
        with open(f"{app_module_path}/modules.txt", "w") as f:
            f.write(module_name)

        # Create hooks.py with all required hooks
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

        # Install app dependencies
        subprocess.run(
            [f"{BENCH_PATH}/env/bin/python", "-m", "pip", "install", "-e", app_path],
            check=True
        )
        print(f"Installed app dependencies for {app_name}")

        return module_name
    except Exception as e:
        print(f"Failed to create app: {e}")
        raise

# Step 3: Create DocType files
def create_doctype(app_name, doctype_name, module_name, fields):
    try:
        app_path = f"{BENCH_PATH}/apps/{app_name}/{app_name}"
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
def ensure_site_and_install_app(app_name):
    try:
        os.chdir(BENCH_PATH)
        sites_dir = f"{BENCH_PATH}/sites"
        site_path = f"{sites_dir}/{SITE_NAME}"

        # Step 1: Update apps.txt with new app first
        apps_txt_path = f"{BENCH_PATH}/sites/apps.txt"
        if os.path.exists(apps_txt_path):
            with open(apps_txt_path, "r") as f:
                apps = [app.strip() for app in f.read().splitlines() if app.strip()]
        else:
            apps = ["frappe"]
        if app_name not in apps:
            apps.append(app_name)
        with open(apps_txt_path, "w") as f:
            f.write("\n".join(apps) + "\n")
        print(f"Initial apps list: {apps}")

        # Step 2: Install the new app into the site first
        if os.path.exists(site_path):
            print(f"Site {SITE_NAME} exists. Installing new app '{app_name}'...")
            try:
                subprocess.run(["bench", "install-app", app_name, "--site", SITE_NAME], check=True)
                print(f"Installed app: {app_name} into site: {SITE_NAME}")
            except subprocess.CalledProcessError as e:
                print(f"Warning: Failed to install '{app_name}' (possibly already installed): {e}")
        else:
            print(f"Site {SITE_NAME} does not exist. Creating it now...")
            subprocess.run(
                ["bench", "new-site", SITE_NAME, "--admin-password", ADMIN_PASSWORD, "--no-mariadb-socket"],
                check=True
            )
            print(f"Created site: {SITE_NAME}")
            subprocess.run(
                ["bench", "set-config", "--site", SITE_NAME, "developer_mode", "1"],
                check=True
            )
            print(f"Enabled developer mode for site: {SITE_NAME}")
            subprocess.run(["bench", "install-app", app_name, "--site", SITE_NAME], check=True)
            print(f"Installed app: {app_name} into site: {SITE_NAME}")

        # Step 3: Validate apps and fix hooks, skipping invalid ones
        required_hooks = ["app_title", "app_description", "app_publisher", "app_email", "app_license"]
        valid_apps = ["frappe"]  # Start with frappe
        for app in apps:
            if not app or app == "frappe":
                continue
            app_dir = f"{BENCH_PATH}/apps/{app}"
            app_path = f"{app_dir}/{app}/hooks.py"
            
            if not os.path.exists(app_dir):
                print(f"Warning: App directory '{app_dir}' does not exist. Skipping '{app}'.")
                continue

            if os.path.exists(app_path):
                with open(app_path, "r") as f:
                    hooks_content = f.read()
                missing_hooks = [hook for hook in required_hooks if hook not in hooks_content]
                if missing_hooks:
                    print(f"Fixing hooks.py for app '{app}' (missing: {missing_hooks})...")
                    hooks_content += "\n" + "\n".join([
                        f'app_title = "{app.capitalize()}"' if "app_title" in missing_hooks else "",
                        f'app_description = "A custom Frappe app"' if "app_description" in missing_hooks else "",
                        'app_publisher = "Prathamesh"' if "app_publisher" in missing_hooks else "",
                        'app_email = "prathamesh@example.com"' if "app_email" in missing_hooks else "",
                        'app_license = "MIT"' if "app_license" in missing_hooks else ""
                    ]).strip() + "\n"
                    with open(app_path, "w") as f:
                        f.write(hooks_content.strip())
            
            try:
                if importlib.util.find_spec(app):
                    valid_apps.append(app)
                else:
                    print(f"Warning: App '{app}' not importable. Skipping '{app}'.")
            except ModuleNotFoundError:
                print(f"Warning: Module '{app}' not found. Skipping '{app}'.")

        # Step 4: Sync site’s installed apps with valid_apps
        print(f"Syncing installed apps for site {SITE_NAME}...")
        result = subprocess.run(
            ["bench", "list-apps", "--site", SITE_NAME],
            capture_output=True, text=True, check=True
        )
        installed_apps = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        print(f"Currently installed apps in site: {installed_apps}")

        for app in installed_apps:
            if app not in valid_apps and app != "frappe":
                try:
                    print(f"Removing app '{app}' from site {SITE_NAME}...")
                    subprocess.run(["bench", "remove-app", app, "--site", SITE_NAME], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Warning: Failed to remove '{app}' with bench: {e}. Attempting manual cleanup...")
                    # Fallback: Manual database cleanup
                    try:
                        subprocess.run(["bench", "--site", SITE_NAME, "console"], input=f"""
import frappe
frappe.db.delete("Installed Application", {{"name": "{app}"}})
frappe.db.commit()
""", text=True, shell=True, check=True)
                        print(f"Manually removed '{app}' from site database.")
                    except subprocess.CalledProcessError as e:
                        print(f"Error: Failed to manually remove '{app}': {e}")

        # Step 5: Rewrite apps.txt with valid apps
        with open(apps_txt_path, "w") as f:
            f.write("\n".join(valid_apps) + "\n")
        print(f"Updated apps.txt with valid apps: {valid_apps}")

        # Step 6: Clear caches
        subprocess.run(["bench", "clear-cache"], check=True)
        subprocess.run(["bench", "clear-cache", "--site", SITE_NAME], check=True)
        subprocess.run(["bench", "clear-website-cache", "--site", SITE_NAME], check=True)

        # Step 7: Start the server
        print("Starting Frappe server...")
        subprocess.Popen(["bench", "start"], cwd=BENCH_PATH)
        live_link = f"http://{HOST}:{PORT}"
        print(f"Server started. Access your app at: {live_link} (login with admin/{ADMIN_PASSWORD})")
    except subprocess.CalledProcessError as e:
        print(f"Failed during site setup or server start: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

# Step 5: Create a zip file of the app
def create_zip(app_name):
    try:
        app_path = f"{BENCH_PATH}/apps/{app_name}"
        zip_path = f"{BENCH_PATH}/{app_name}.zip"
        if os.path.exists(app_path):
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(app_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, f"{BENCH_PATH}/apps")
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
def generate_frappe_app(prompt):
    try:
        app_name, doctypes = parse_prompt(prompt)
        module_name = create_frappe_app(app_name)
        for doctype_name, fields in doctypes.items():
            create_doctype(app_name, doctype_name, module_name, fields)
        ensure_site_and_install_app(app_name)
        zip_path = create_zip(app_name)
        if zip_path:
            print(f"App generation successful! Download your app at: {zip_path}")
        else:
            print(f"App generation partially successful. Site should still work, but zip creation failed.")
    except Exception as e:
        print(f"Failed to generate or install app: {e}")

if __name__ == "__main__":
    BENCH_PATH = "/home/prathamesh/todo-bench"
    SITE_NAME = "site2.local"
    ADMIN_PASSWORD = "admin"
    HOST = "localhost"
    PORT = "8002"

    app_name = input("Enter the name of the app (e.g., library_management): ").strip()
    prompt = (
        f"Create an app named {app_name} with DocTypes: "
        "Article (title: Data, status: Select[Issued,Available]), "
        "Member (name: Data, membership_date: Date)"
    )
    
    print(f"Generated prompt: {prompt}")
    
    generate_frappe_app(prompt)
