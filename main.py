import os
import shutil
import requests
import json
import winreg as reg
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# 全局变量来控制是否停止下载
stop_event = threading.Event()
current_thread = None
executor = ThreadPoolExecutor(max_workers=1)  # 只允许一次下载一个文件

def find_install_path(program_name):
    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        with reg.OpenKey(reg.HKEY_LOCAL_MACHINE, uninstall_key) as key:
            for i in range(reg.QueryInfoKey(key)[0]):
                subkey_name = reg.EnumKey(key, i)
                with reg.OpenKey(key, subkey_name) as subkey:
                    try:
                        display_name = reg.QueryValueEx(subkey, "DisplayName")[0]
                        if program_name.lower() in display_name.lower():
                            return reg.QueryValueEx(subkey, "InstallLocation")[0]
                    except FileNotFoundError:
                        continue
    except FileNotFoundError:
        return None

def get_file_list(server_url):
    response = requests.get(server_url)
    response.raise_for_status()
    return response.json()

def sync_files(server_url, local_path, result_listbox, download_status_label, progress_bar):
    stop_event.clear()

    files = get_file_list(server_url)
    files_to_add, files_to_delete, _ = check_files(files, local_path)
    total_files = len(files_to_add) + len(files_to_delete)
    current_file_count = 0

    if files_to_delete:
        for file_to_delete in files_to_delete:
            if stop_event.is_set():
                break
            local_file_path = os.path.join(local_path, file_to_delete)
            os.remove(local_file_path)
            result_listbox.insert(0, f"已删除: {file_to_delete}")
            result_listbox.itemconfig(0, {'fg': 'red'})
            result_listbox.update_idletasks()
            current_file_count += 1
            progress_bar['value'] = (current_file_count / total_files) * 100

    if files_to_add:
        for file_info in files:
            if stop_event.is_set():
                break
            relative_path = file_info['path']
            if relative_path not in files_to_add:
                continue
            file_url = file_info['link']
            local_file_path = os.path.join(local_path, relative_path)
            local_dir = os.path.dirname(local_file_path)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
            executor.submit(download_file, file_url, local_file_path, result_listbox, download_status_label, relative_path, total_files, current_file_count, progress_bar)

    executor.shutdown(wait=True)
    sync_button.config(state=tk.NORMAL, text="同步文件", command=on_sync)
    stop_event.clear()

def download_file(url, local_file_path, result_listbox, download_status_label, relative_path, total_files, current_file_count, progress_bar):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kibibyte
    progress = 0
    start_time = time.time()
    if total_size == 0:
        with open(local_file_path, 'wb') as f:
            f.write(response.content)
        result_listbox.insert(0, f"新增: {relative_path}")
        result_listbox.itemconfig(0, {'fg': 'green'})
        result_listbox.update_idletasks()
    else:
        with open(local_file_path, 'wb') as f:
            progress_msg_index = result_listbox.size()
            result_listbox.insert(progress_msg_index, f"下载: {relative_path} 0.00% 速度: 0.00 KB/s")
            result_listbox.itemconfig(progress_msg_index, {'fg': 'blue'})
            result_listbox.update_idletasks()
            for data in response.iter_content(block_size):
                if stop_event.is_set():
                    download_status_label.config(text="下载已停止")
                    return
                progress += len(data)
                f.write(data)
                elapsed_time = time.time() - start_time
                speed = progress / elapsed_time
                speed_str = f"{speed / 1024:.2f} KB/s" if speed < 1024 * 1024 else f"{speed / (1024 * 1024):.2f} MB/s"
                percent = progress / total_size * 100
                download_status_label.config(text=f"正在下载: {relative_path} {percent:.2f}% 速度: {speed_str}")
                result_listbox.delete(progress_msg_index)
                result_listbox.insert(progress_msg_index, f"下载: {relative_path} {percent:.2f}% 速度: {speed_str}")
                result_listbox.itemconfig(progress_msg_index, {'fg': 'blue'})
                result_listbox.update_idletasks()
            if not stop_event.is_set():
                result_listbox.delete(progress_msg_index)
                result_listbox.insert(0, f"新增: {relative_path}")
                result_listbox.itemconfig(0, {'fg': 'green'})
                download_status_label.config(text=f"下载完成: {relative_path}")
                result_listbox.update_idletasks()
                current_file_count += 1
                progress_bar['value'] = (current_file_count / total_files) * 100

def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config['program_name'], config['server_url'], config['mods_folder']

def check_files(files, local_path):
    server_files = set(file_info['path'] for file_info in files)
    local_files = set()
    for root, _, filenames in os.walk(local_path):
        for filename in filenames:
            relative_path = os.path.relpath(os.path.join(root, filename), local_path)
            local_files.add(relative_path)
    
    files_to_delete = local_files - server_files
    files_to_add = server_files - local_files
    files_have = server_files & local_files

    return list(files_to_add), list(files_to_delete), list(files_have)

def on_check():
    program_name, server_url, mods_folder = load_config(config_file)
    install_path = find_install_path(program_name)
    if install_path is None:
        messagebox.showerror("Error", f"Program {program_name} not found.")
        return
    
    mods_path = install_path + mods_folder
    if not os.path.exists(mods_path):
        os.makedirs(mods_path)

    files = get_file_list(server_url)
    files_to_add, files_to_delete, files_have = check_files(files, mods_path)

    result_listbox.delete(0, tk.END)
    for file in files_to_add:
        result_listbox.insert(0, f"新增: {file}")
        result_listbox.itemconfig(0, {'fg': 'green'})

    for file in files_to_delete:
        result_listbox.insert(0, f"删除: {file}")
        result_listbox.itemconfig(0, {'fg': 'red'})

    for file in files_have:
        result_listbox.insert(0, f"存在: {file}")
        result_listbox.itemconfig(0, {'fg': 'black'})

    # 根据检查结果启用或禁用同步按钮
    if files_to_add or files_to_delete:
        sync_button.config(state=tk.NORMAL)
    else:
        sync_button.config(state=tk.DISABLED)

def on_sync():
    global stop_event, current_thread, executor
    stop_event.clear()
    executor = ThreadPoolExecutor(max_workers=1)  # 重新初始化以确保新的任务可以提交
    program_name, server_url, mods_folder = load_config(config_file)
    install_path = find_install_path(program_name)
    if install_path is None:
        messagebox.showerror("Error", f"Program {program_name} not found.")
        return

    mods_path = install_path + mods_folder
    if not os.path.exists(mods_path):
        os.makedirs(mods_path)

    result_listbox.delete(0, tk.END)  # 清空列表
    download_status_label.config(text="")  # 清空下载状态
    progress_bar['value'] = 0  # 重置进度条

    # 更改按钮状态和功能为停止同步
    sync_button.config(state=tk.NORMAL, text="停止同步", command=on_stop)

    # 启动一个新线程执行同步操作
    current_thread = threading.Thread(target=sync_files, args=(server_url, mods_path, result_listbox, download_status_label, progress_bar))
    current_thread.start()

def on_stop():
    global stop_event, current_thread, executor
    stop_event.set()
    if current_thread is not None:
        current_thread.join()  # 等待当前线程完成
    executor.shutdown(wait=False)  # 尝试立即停止所有线程
    sync_button.config(state=tk.NORMAL, text="同步文件", command=on_sync)

def select_config_file():
    global config_file
    config_file = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if config_file:
        config_file_label.config(text=config_file)

app = tk.Tk()
app.title("File Sync Tool")

frame = ttk.Frame(app, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

config_file_label = ttk.Label(frame, text="No config file selected")
config_file_label.grid(row=0, column=0, columnspan=2, pady=5)

select_button = ttk.Button(frame, text="Select Config File", command=select_config_file)
select_button.grid(row=1, column=0, pady=5, sticky=tk.W)

check_button = ttk.Button(frame, text="检查文件", command=on_check)
check_button.grid(row=1, column=1, pady=5, sticky=tk.E)

sync_button = ttk.Button(frame, text="同步文件", command=on_sync)
sync_button.grid(row=2, column=0, columnspan=2, pady=5)
sync_button.config(state=tk.DISABLED)  # 初始状态为禁用

result_frame = ttk.Frame(frame)
result_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))

result_listbox = tk.Listbox(result_frame, height=20, width=80)
result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(result_frame, orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

result_listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=result_listbox.yview)

frame.columnconfigure(0, weight=1)
frame.columnconfigure(1, weight=1)
frame.rowconfigure(3, weight=1)

result_frame.columnconfigure(0, weight=1)
result_frame.rowconfigure(0, weight=1)

# 添加一个Label用于显示当前下载状态
download_status_label = ttk.Label(frame, text="")
download_status_label.grid(row=4, column=0, columnspan=2, pady=5)

# 添加一个全局进度条
progress_bar = ttk.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
progress_bar.grid(row=5, column=0, columnspan=2, pady=5)

app.columnconfigure(0, weight=1)
app.rowconfigure(0, weight=1)

app.mainloop()
