# FILE: logix_component_manager.py
# A GUI application to import and export components for a Logix project.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import asyncio
import threading
import xml.etree.ElementTree as ET
import tempfile
import uuid
import re
import shutil

# Dependency Check for Logix SDK
try:
    from logix_designer_sdk import LogixProject, StdOutEventLogger, ImportCollisionOptions
except ImportError:
    messagebox.showerror("Missing Dependency", "Logix Designer SDK not installed.")
    exit()

# Configuration for the Importer to identify component types from L5X files
L5X_ROOT_TO_XPATH = {
    "Program": "Controller/Programs/Program",
    "AddOnInstructionDefinition": "Controller/AddOnInstructionDefinitions/AddOnInstructionDefinition",
    "DataType": "Controller/DataTypes/DataType"
}

# Configuration for the Exporter
EXPORT_CONFIG = {
    "Program": {
        "display_name": "Programs",
        "container_xpath": "Controller/Programs",
        "l5x_find_path": ".//{ns_prefix}Program"
    },
    "AddOnInstructionDefinition": {
        "display_name": "Add-On Instructions (AOIs)",
        "container_xpath": "Controller/AddOnInstructionDefinitions",
        "l5x_find_path": ".//{ns_prefix}AddOnInstructionDefinition"
    },
    "DataType": {
        "display_name": "User-Defined Types (UDTs)",
        "container_xpath": "Controller/DataTypes",
        "l5x_find_path": ".//{ns_prefix}DataType",
        "filter_attribute": {"key": "Class", "value": "User"}
    }
}

class LogixGuiApp(tk.Tk):
    # ... No changes to this class ...
    def __init__(self):
        super().__init__()
        self.title("Logix Component Manager")
        self.geometry("700x550")
        self.async_loop = asyncio.new_event_loop()
        self.worker_thread = threading.Thread(target=self.async_worker, daemon=True)
        self.worker_thread.start()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    def async_worker(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()
    def submit_task(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.async_loop)
    def on_closing(self):
        if self.async_loop.is_running():
            def shutdown():
                self.async_loop.stop()
                self.async_loop.run_until_complete(self.async_loop.shutdown_asyncgens())
            self.async_loop.call_soon_threadsafe(shutdown)
        self.destroy()
    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        self.status_text = tk.StringVar(value="Status: Ready")
        status_bar = ttk.Label(self, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=0, column=0, sticky="nsew")
        ImporterTab(self, notebook)
        ExporterTab(self, notebook)
    def _set_ui_state(self, frame, is_enabled):
        state = tk.NORMAL if is_enabled else tk.DISABLED
        for widget in frame.winfo_children():
            try:
                if 'state' in widget.configure(): widget.configure(state=state)
            except tk.TclError: pass
            self._set_ui_state(widget, is_enabled)

class ImporterTab:
    # ... No changes to this class ...
    def __init__(self, app, notebook):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Import Components")
        self._build_ui()
    def _build_ui(self):
        self.frame.grid_rowconfigure(2, weight=1); self.frame.grid_columnconfigure(0, weight=1)
        target_frame = ttk.LabelFrame(self.frame, text="1. Select Target Project File (.ACD)", padding=10)
        target_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10)); target_frame.grid_columnconfigure(0, weight=1)
        self.target_path = tk.StringVar()
        target_entry = ttk.Entry(target_frame, textvariable=self.target_path, state='readonly')
        target_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(target_frame, text="Browse...", command=self.browse_for_target).grid(row=0, column=1)
        source_frame = ttk.LabelFrame(self.frame, text="2. Select Source Component File(s) (.L5X)", padding=10)
        source_frame.grid(row=1, column=0, sticky="ew", pady=5); source_frame.grid_columnconfigure(0, weight=1)
        self.source_paths = tk.StringVar()
        source_entry = ttk.Entry(source_frame, textvariable=self.source_paths, state='readonly')
        source_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(source_frame, text="Browse...", command=self.browse_for_sources).grid(row=0, column=1)
        options_frame = ttk.LabelFrame(self.frame, text="3. Set Import Options", padding=10)
        options_frame.grid(row=2, column=0, sticky="nsew", pady=5)
        self.collision_option = tk.StringVar(value="OVERWRITE_ON_COLL")
        ttk.Label(options_frame, text="If a component already exists in the project:").pack(anchor='w')
        ttk.Radiobutton(options_frame, text="Overwrite it with the version from the file (Overwrite)", variable=self.collision_option, value="OVERWRITE_ON_COLL").pack(anchor='w', padx=20)
        ttk.Radiobutton(options_frame, text="Keep the existing one and discard the import (Discard)", variable=self.collision_option, value="DISCARD_ON_COLL").pack(anchor='w', padx=20)
        self.import_button = ttk.Button(self.frame, text="Import Component(s)", state=tk.DISABLED, command=self.start_import)
        self.import_button.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    def _check_button_state(self):
        if self.target_path.get() and self.source_paths.get(): self.import_button.config(state=tk.NORMAL)
        else: self.import_button.config(state=tk.DISABLED)
    def browse_for_target(self):
        path = filedialog.askopenfilename(filetypes=[("Logix Projects", "*.ACD"), ("All files", "*.*")])
        if path: self.target_path.set(path)
        self._check_button_state()
    def browse_for_sources(self):
        paths = filedialog.askopenfilenames(filetypes=[("L5X Component Files", "*.L5X"), ("All files", "*.*")])
        if paths:
            display_text = f"{len(paths)} file(s) selected" if len(paths) > 1 else os.path.basename(paths[0])
            self.source_paths.set(display_text)
            self._source_file_list = paths
        self._check_button_state()
    def start_import(self):
        target_acd = self.target_path.get(); source_l5x_list = getattr(self, '_source_file_list', []); collision_choice = self.collision_option.get()
        if not target_acd or not source_l5x_list: messagebox.showwarning("Input Missing", "Please select both a target project and source file(s)."); return
        self.app._set_ui_state(self.frame, False)
        self.app.status_text.set("Status: Starting import process...")
        self.app.submit_task(self.perform_import(target_acd, source_l5x_list, collision_choice))
    def _inspect_l5x_and_get_xpath(self, l5x_path):
        try:
            tree = ET.parse(l5x_path); root = tree.getroot(); component_to_process = None
            root_tag_clean = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            if root_tag_clean in L5X_ROOT_TO_XPATH: component_to_process = root
            else:
                namespace = root.tag.split('}')[0][1:] if '}' in root.tag else ''
                ns_prefix = f'{{{namespace}}}' if namespace else ''
                for component_tag_name in L5X_ROOT_TO_XPATH.keys():
                    found_node = root.find(f".//{ns_prefix}{component_tag_name}")
                    if found_node is not None: component_to_process = found_node; break
            if component_to_process is not None:
                component_tag_clean = component_to_process.tag.split('}')[-1]
                if component_tag_clean in L5X_ROOT_TO_XPATH: return os.path.dirname(L5X_ROOT_TO_XPATH[component_tag_clean])
            raise ValueError(f"Could not identify a supported component in file: {os.path.basename(l5x_path)}")
        except ET.ParseError: raise ValueError(f"Invalid XML in file: {os.path.basename(l5x_path)}")
    async def perform_import(self, target_acd, source_l5x_list, collision_choice):
        project = None; error = None
        try:
            self.app.after(0, self.app.status_text.set, f"Status: Opening project {os.path.basename(target_acd)}...")
            project = await LogixProject.open_logix_project(target_acd, StdOutEventLogger())
            if project is None: raise Exception("Failed to open project.")
            collision_map = {"OVERWRITE_ON_COLL": ImportCollisionOptions.OVERWRITE_ON_COLL, "DISCARD_ON_COLL": ImportCollisionOptions.DISCARD_ON_COLL}
            sdk_collision_option = collision_map.get(collision_choice)
            for l5x_file in source_l5x_list:
                xpath_to_import = self._inspect_l5x_and_get_xpath(l5x_file)
                self.app.after(0, self.app.status_text.set, f"Status: Importing '{os.path.basename(l5x_file)}'...")
                await project.partial_import_from_xml_file(xpath_to_import, l5x_file, sdk_collision_option)
            self.app.after(0, self.app.status_text.set, "Status: Saving changes to project...")
            await project.save()
        except Exception as e: error = e
        finally:
            if project:
                self.app.after(0, self.app.status_text.set, "Status: Closing project...")
                project.close()
        self.app.after(0, self.finish_import, error)
    def finish_import(self, error):
        if error: messagebox.showerror("Import Failed", str(error)); self.app.status_text.set(f"Status: ERROR - {error}")
        else: messagebox.showinfo("Success", "Component(s) imported and project saved successfully."); self.app.status_text.set("Status: Import complete. Ready for next task.")
        self.app._set_ui_state(self.frame, True); self._check_button_state()

class ExporterTab:
    # ... No changes to __init__ or _build_ui ...
    def __init__(self, app, notebook):
        self.app = app; self.frame = ttk.Frame(notebook); notebook.add(self.frame, text="Export Components"); self.component_listbox = None; self._build_ui()
    def _build_ui(self):
        self.frame.grid_rowconfigure(3, weight=1); self.frame.grid_columnconfigure(0, weight=1)
        file_frame = ttk.LabelFrame(self.frame, text="1. Select Project File", padding=10); file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10)); file_frame.grid_columnconfigure(0, weight=1)
        self.project_path = tk.StringVar(); entry = ttk.Entry(file_frame, textvariable=self.project_path, state='readonly'); entry.grid(row=0, column=0, sticky="ew", padx=(0, 5)); ttk.Button(file_frame, text="Browse...", command=self.browse_for_project).grid(row=0, column=1)
        type_frame = ttk.LabelFrame(self.frame, text="2. Select Component Type to Export", padding=10); type_frame.grid(row=1, column=0, sticky="ew", pady=5)
        self.export_type = tk.StringVar(value="Program")
        ttk.Radiobutton(type_frame, text="Programs", variable=self.export_type, value="Program", command=self._on_export_type_change).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(type_frame, text="AOIs", variable=self.export_type, value="AddOnInstructionDefinition", command=self._on_export_type_change).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(type_frame, text="User-Defined Types (UDTs)", variable=self.export_type, value="DataType", command=self._on_export_type_change).pack(side=tk.LEFT, padx=10)
        list_frame = ttk.LabelFrame(self.frame, text="3. Scan for and Select Components", padding=10); list_frame.grid(row=2, column=0, sticky="ew", pady=5); list_frame.grid_columnconfigure(0, weight=1)
        self.scan_button = ttk.Button(list_frame, text="Scan for Components", command=self.start_scan); self.scan_button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        export_frame = ttk.LabelFrame(self.frame, text="4. Choose Export Location and Export", padding=10); export_frame.grid(row=3, column=0, sticky="nsew", pady=5); export_frame.grid_columnconfigure(0, weight=1)
        self.export_path = tk.StringVar(); export_entry = ttk.Entry(export_frame, textvariable=self.export_path, state='readonly'); export_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5)); ttk.Button(export_frame, text="Browse...", command=self.browse_for_export_folder).grid(row=0, column=1)
        self.export_button = ttk.Button(export_frame, text="Export Selected Component(s)", state=tk.DISABLED, command=self.start_export); self.export_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
    def _on_export_type_change(self):
        if self.component_listbox: self.component_listbox.destroy(); self.component_listbox = None
        self.export_button.config(state=tk.DISABLED)
    def browse_for_project(self):
        path = filedialog.askopenfilename(filetypes=[("Logix Projects", "*.ACD *.L5K"), ("All files", "*.*")]);
        if path: self.project_path.set(path); self._on_export_type_change()
    def browse_for_export_folder(self):
        path = filedialog.askdirectory(title="Select Folder to Save L5X Files");
        if path: self.export_path.set(path)
    def start_scan(self):
        proj_path = self.project_path.get()
        if not proj_path: messagebox.showwarning("Input Missing", "Please select a project file first."); return
        component_type = self.export_type.get(); config = EXPORT_CONFIG[component_type]; display_name = config['display_name'].lower()
        self.app._set_ui_state(self.frame, False); self.app.status_text.set(f"Status: Scanning project for {display_name}... This may take a moment.")
        future = self.app.submit_task(self.perform_scan(proj_path, config))
        future.add_done_callback(lambda x: self.app.after(0, self.finish_scan, x.exception(), x.result() if x.result() is not None else [], display_name))
    async def perform_scan(self, proj_path, config):
        project = None; temp_l5x_path = os.path.join(tempfile.gettempdir(), f"temp_scan_{uuid.uuid4().hex}.l5x")
        try:
            self.app.after(0, self.app.status_text.set, "Status: Opening project for scanning...")
            project = await LogixProject.open_logix_project(proj_path, StdOutEventLogger())
            if project is None: raise Exception("Failed to open project.")
            self.app.after(0, self.app.status_text.set, f"Status: Exporting component collection to temporary file...")
            await project.partial_export_to_xml_file(config['container_xpath'], temp_l5x_path)
            if not os.path.exists(temp_l5x_path): return []
            tree = ET.parse(temp_l5x_path); root = tree.getroot()
            namespace = root.tag.split('}')[0][1:] if '}' in root.tag else ''; ns_prefix = f'{{{namespace}}}' if namespace else ''
            find_path = config['l5x_find_path'].format(ns_prefix=ns_prefix); all_nodes = root.findall(find_path)
            if "filter_attribute" in config:
                key, val = config["filter_attribute"]["key"], config["filter_attribute"]["value"]
                component_names = [n.get('Name') for n in all_nodes if n.get('Name') and n.get(key) == val]
            else: component_names = [n.get('Name') for n in all_nodes if n.get('Name')]
            return sorted(component_names)
        except ET.ParseError as e: raise ValueError(f"Failed to parse temporary XML file: {temp_l5x_path} - {str(e)}")
        finally:
            if project: self.app.after(0, self.app.status_text.set, "Status: Closing project..."); project.close()
            if os.path.exists(temp_l5x_path):
                try: os.remove(temp_l5x_path)
                except OSError as e: print(f"Error removing temp file: {e}")
    def finish_scan(self, error, components, display_name):
        if error: messagebox.showerror("Scan Failed", str(error)); self.app.status_text.set(f"Status: ERROR - {error}")
        else:
            self.app.status_text.set(f"Status: Scan complete. Found {len(components)} {display_name}.")
            self._create_component_listbox(components)
            if components: self.export_button.config(state=tk.NORMAL)
        self.app._set_ui_state(self.frame, True)
    def _create_component_listbox(self, components):
        if self.component_listbox: self.component_listbox.destroy()
        list_frame = self.scan_button.master; listbox_frame = ttk.Frame(list_frame); listbox_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)
        listbox_frame.grid_rowconfigure(0, weight=1); listbox_frame.grid_columnconfigure(0, weight=1)
        self.component_listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, height=8); self.component_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.component_listbox.yview); scrollbar.grid(row=0, column=1, sticky="ns")
        self.component_listbox.config(yscrollcommand=scrollbar.set)
        for component in components: self.component_listbox.insert(tk.END, component)

    def start_export(self):
        proj_path = self.project_path.get(); export_dir = self.export_path.get()
        if not self.component_listbox or not self.component_listbox.curselection(): messagebox.showwarning("Input Missing", "Please select one or more components to export."); return
        if not export_dir: messagebox.showwarning("Input Missing", "Please select an export folder."); return
        selected_indices = self.component_listbox.curselection(); selected_components = [self.component_listbox.get(i) for i in selected_indices]; component_type = self.export_type.get()
        
        # NEW: Add a clear warning for the user about Program exports.
        if component_type == "Program":
            proceed = messagebox.askokcancel("Program Export Limitation",
                "Due to SDK limitations, exporting a Program will only save its main definition.\n\n"
                "Routines and program-scoped Tags will NOT be included in the L5X file.\n\n"
                "This is useful for creating a program shell, but not for a full backup. Proceed anyway?")
            if not proceed:
                return

        copies_to_make = 0
        if len(selected_components) == 1:
            num = simpledialog.askinteger("Create Indexed Copies", "Enter number of indexed copies to create (e.g., 3 creates _1, _2, _3).\n\nEnter 0 or Cancel for a normal single export.", parent=self.app, minvalue=0)
            if num is not None and num > 0: copies_to_make = num
        self.app._set_ui_state(self.frame, False); self.app.status_text.set(f"Status: Exporting {len(selected_components)} component(s)...")
        self.app.submit_task(self.perform_export(proj_path, export_dir, selected_components, component_type, copies_to_make))

    async def perform_export(self, proj_path, export_dir, selected_components, component_type, copies_to_make=0):
        project = None; error = None
        try:
            self.app.after(0, self.app.status_text.set, "Status: Opening project for export...")
            project = await LogixProject.open_logix_project(proj_path, StdOutEventLogger())
            if project is None: raise Exception("Failed to open project.")
            for component_name in selected_components:
                self.app.after(0, self.app.status_text.set, f"Status: Exporting '{component_name}'...")
                # REVERTED: All exports now use the same simple, reliable method.
                xpath = f"Controller/{EXPORT_CONFIG[component_type]['container_xpath'].split('/')[1]}/{component_type}[@Name='{component_name}']"
                final_export_file = os.path.join(export_dir, f"{component_name}.L5X")
                await project.partial_export_to_xml_file(xpath, final_export_file)
                if copies_to_make > 0 and os.path.exists(final_export_file):
                    self._create_indexed_copies(final_export_file, component_name, copies_to_make)
        except Exception as e: error = e
        finally:
            if project:
                self.app.after(0, self.app.status_text.set, "Status: Closing project...")
                project.close()
            self.app.after(0, self.finish_export, error)

    def _create_indexed_copies(self, original_l5x_path, original_name, num_copies):
        try:
            with open(original_l5x_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            pattern = re.compile(r'\b' + re.escape(original_name) + r'\b')
            for i in range(1, num_copies + 1):
                new_name = f"{original_name}_{i}"
                self.app.after(0, self.app.status_text.set, f"Status: Creating copy '{new_name}'...")
                new_content = pattern.sub(new_name, original_content)
                new_file_path = os.path.join(os.path.dirname(original_l5x_path), f"{new_name}.L5X")
                with open(new_file_path, 'w', encoding='utf-8') as f: f.write(new_content)
        except Exception as e:
            messagebox.showwarning("Copy Failed", f"Could not create indexed copies for '{original_name}':\n{e}")

    def finish_export(self, error):
        if error: messagebox.showerror("Export Failed", str(error)); self.app.status_text.set(f"Status: ERROR - {error}")
        else: messagebox.showinfo("Success", "Selected components exported successfully."); self.app.status_text.set("Status: Export complete. Ready for next task.")
        self.app._set_ui_state(self.frame, True)

def main():
    app = LogixGuiApp()
    app.mainloop()

if __name__ == "__main__":
    main()