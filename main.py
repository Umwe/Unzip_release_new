import os
import zipfile
import shutil
import tarfile
import rarfile
from tkinter import Tk, Label, Button, Entry, filedialog, messagebox
from tkinter import ttk, BooleanVar
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import json
import threading
import time


SETTINGS_FILE = "settings.json"

POLLING_INTERVAL = 5  # seconds

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as file:
        json.dump(settings, file)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as file:
            return json.load(file)
    return {}

class ZipFileProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("Archive File Processor")

        self.settings = load_settings()
        self.running = True
        self.deleted_files_count = 0  # Cumulative count for deleted files
        self.extracted_files_count = 0  # Cumulative count for extracted files

        # Input directory
        Label(root, text="Input Directory:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.input_dir_entry = Entry(root, width=50)
        self.input_dir_entry.grid(row=0, column=1, padx=10, pady=5)
        Button(root, text="Browse", command=self.browse_input_directory).grid(row=0, column=2, padx=10, pady=5)

        # Output directory
        Label(root, text="Output Directory:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.output_dir_entry = Entry(root, width=50)
        self.output_dir_entry.grid(row=1, column=1, padx=10, pady=5)
        Button(root, text="Browse", command=self.browse_output_directory).grid(row=1, column=2, padx=10, pady=5)

        # Date picker
        Label(root, text="Date:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.date_picker = DateEntry(root, width=20, date_pattern='yyyy-mm-dd')
        self.date_picker.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # Current date toggle
        self.use_current_date = BooleanVar(value=self.settings.get("use_current_date", False))
        self.current_date_checkbox = ttk.Checkbutton(root, text="Use Current Date", variable=self.use_current_date, command=self.toggle_current_date)
        self.current_date_checkbox.grid(row=2, column=2, padx=10, pady=5)

        # Process button
        Button(root, text="Process", command=self.process_files).grid(row=3, column=0, columnspan=3, pady=10)

        # Status and count labels
        self.log_label = Label(root, text="Status: Ready", anchor="w")
        self.log_label.grid(row=4, column=0, columnspan=3, sticky="w", padx=10, pady=5)

        self.deleted_files_label = Label(root, text="Deleted Files Count: 0", anchor="w")
        self.deleted_files_label.grid(row=5, column=0, sticky="w", padx=10, pady=5)

        self.extracted_files_label = Label(root, text="Extracted Files Count: 0", anchor="w")
        self.extracted_files_label.grid(row=5, column=2, sticky="e", padx=10, pady=5)

        self.load_previous_settings()
        self.update_date_picker_state()
        self.start_monitoring()



    def browse_input_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir_entry.delete(0, "end")
            self.input_dir_entry.insert(0, directory)

    def browse_output_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, directory)

    def toggle_current_date(self):
        self.settings["use_current_date"] = self.use_current_date.get()
        self.update_date_picker_state()
        save_settings(self.settings)

    def update_date_picker_state(self):
        if self.use_current_date.get():
            self.date_picker.config(state="disabled")
        else:
            self.date_picker.config(state="normal")

    def delete_previous_day_extracted_files(self, input_dir, process_date):
        previous_day = process_date - timedelta(days=1)
        deleted_count = 0  # Initialize the counter for deleted files

        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            if os.path.isfile(file_path) and not file_path.endswith(('.zip', '.rar', '.tar', '.tar.gz', '.tgz')):
                file_date = datetime.fromtimestamp(os.path.getmtime(file_path)).date()
                if file_date == previous_day:
                    os.remove(file_path)
                    deleted_count += 1  # Increment the counter for each deleted file

        # Update the cumulative count and label
        self.deleted_files_count += deleted_count
        self.deleted_files_label.config(text=f"Deleted Files Count: {self.deleted_files_count}")

        # Update the log to display the number of deleted files
        if deleted_count > 0:
            self.log_label.config(text=f"Status: Deleted {deleted_count} file(s) from {previous_day}.")
        else:
            self.log_label.config(text=f"Status: No files to delete from {previous_day}.")


    def process_files(self):
        input_dir = self.input_dir_entry.get()
        output_dir = self.output_dir_entry.get()
        process_date = None

        if not input_dir or not output_dir:
            self.log_label.config(text="Status: Error - Missing input or output directory.")
            return

        def safe_extract(tar, path="."):
            """
            Safely extract tar files by ensuring no file attempts to escape the target directory.
            """
            for member in tar.getmembers():
                # Ensure the file is within the target directory
                if not os.path.abspath(os.path.join(path, member.name)).startswith(os.path.abspath(path)):
                    raise Exception(f"Attempted Path Traversal in Tar File: {member.name}")
                tar.extract(member, path)

        try:
            if self.use_current_date.get():
                process_date = datetime.now().date()
            else:
                process_date = datetime.strptime(self.date_picker.get(), "%Y-%m-%d").date()

            self.settings["date"] = process_date.strftime("%Y-%m-%d")
            save_settings(self.settings)

            self.delete_previous_day_extracted_files(input_dir, process_date)

            extracted_count = 0  # Counter for extracted files
            for file_name in os.listdir(input_dir):
                file_path = os.path.join(input_dir, file_name)
                if os.path.isfile(file_path):
                    file_date = datetime.fromtimestamp(os.path.getmtime(file_path)).date()
                    if file_date == process_date:
                        if file_name.endswith(".zip"):
                            with zipfile.ZipFile(file_path, 'r') as archive:
                                archive.extractall(input_dir)
                        elif file_name.endswith(".tar") or file_name.endswith(".tar.gz") or file_name.endswith(".tgz"):
                            with tarfile.open(file_path, 'r') as archive:
                                safe_extract(archive, input_dir)
                        elif file_name.endswith(".rar"):
                            with rarfile.RarFile(file_path, 'r') as archive:
                                archive.extractall(input_dir)
                        else:
                            continue

                        shutil.move(file_path, os.path.join(output_dir, file_name))
                        extracted_count += 1

            self.extracted_files_count += extracted_count
            self.extracted_files_label.config(text=f"Extracted Files Count: {self.extracted_files_count}")

            if extracted_count > 0:
                self.log_label.config(text=f"Status: Processed {extracted_count} archive file(s).")
            else:
                self.log_label.config(text="Status: No archive files found.")
        except Exception as e:
            self.log_label.config(text=f"Status: Error - {e}")



    def load_previous_settings(self):
        input_dir = self.settings.get('input_dir', '')
        output_dir = self.settings.get('output_dir', '')
        saved_date = self.settings.get("date", None)
        if input_dir:
            self.input_dir_entry.insert(0, input_dir)
        if output_dir:
            self.output_dir_entry.insert(0, output_dir)
        if saved_date and not self.use_current_date.get():
            self.date_picker.set_date(saved_date)
        self.use_current_date.set(self.settings.get("use_current_date", False))

    def monitor_directory(self):
        while self.running:
            input_dir = self.input_dir_entry.get()
            output_dir = self.output_dir_entry.get()
            if input_dir and output_dir:
                self.process_files()
            time.sleep(POLLING_INTERVAL)

    def start_monitoring(self):
        monitoring_thread = threading.Thread(target=self.monitor_directory, daemon=True)
        monitoring_thread.start()

    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = ZipFileProcessor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
