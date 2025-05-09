import sys
import os
import subprocess
import requests
import zipfile
import io
import platform
import tarfile
import psutil
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                            QFileDialog, QMessageBox, QTextEdit, QFrame,
                            QTabWidget, QProgressBar, QGroupBox, QGridLayout,
                            QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPalette, QColor, QScreen
from pathlib import Path
import json
import shutil

def check_admin():
    """Check if the program is running with admin privileges."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        # Windows platform
        try:
            return bool(os.getuid() & 0x4000)  # Check for admin bit
        except AttributeError:
            return False

def restart_as_admin():
    """Restart the application with admin privileges."""
    if platform.system() == "Windows":
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            return True
    else:
        if os.geteuid() != 0:
            os.execvp('sudo', ['sudo', 'python3'] + sys.argv)
            return True
    return False

def get_linux_distro():
    """Detect the Linux distribution."""
    try:
        with open('/etc/os-release', 'r') as f:
            lines = f.readlines()
            info = {}
            for line in lines:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    info[key] = value.strip('"')
            
            # Get the ID and ID_LIKE fields
            distro_id = info.get('ID', '').lower()
            distro_like = info.get('ID_LIKE', '').lower()
            
            # Handle special cases
            if 'cachyos' in distro_id:
                return 'cachyos'
            elif 'pikaos' in distro_id:
                return 'pikaos'
            elif 'nobara' in distro_id:
                return 'nobara'
            
            return distro_id
    except:
        return ''

def get_package_manager_commands():
    """Get the appropriate package manager commands for the detected distro."""
    distro = get_linux_distro()
    commands = {
        'ubuntu': {
            'update': 'sudo apt update',
            'install': 'sudo apt install -y build-essential curl git cmake pkg-config libvulkan-dev vulkan-tools spirv-tools libclang-dev clang llvm-dev python3-pip ninja-build',
            'rust': 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
        },
        'debian': {
            'update': 'sudo apt update',
            'install': 'sudo apt install -y build-essential curl git cmake pkg-config libvulkan-dev vulkan-tools spirv-tools libclang-dev clang llvm-dev python3-pip ninja-build',
            'rust': 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
        },
        'pikaos': {
            'update': 'sudo apt update',
            'install': 'sudo apt install -y build-essential curl git cmake pkg-config libvulkan-dev vulkan-tools spirv-tools libclang-dev clang llvm-dev python3-pip ninja-build',
            'rust': 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
        },
        'arch': {
            'update': 'sudo pacman -S --noconfirm base-devel git cmake vulkan-devel vulkan-tools spirv-tools clang llvm python-pip ninja rust',
            'install': '',  # Empty since we do it all in the update command
            'rust': ''  # Empty since rust is included in the update command
        },
        'cachyos': {
            'update': 'sudo pacman -S --noconfirm base-devel git cmake vulkan-devel vulkan-tools spirv-tools clang llvm python-pip ninja rust',
            'install': '',  # Empty since we do it all in the update command
            'rust': ''  # Empty since rust is included in the update command
        },
        'manjaro': {
            'update': 'sudo pacman -S --noconfirm base-devel git cmake vulkan-devel vulkan-tools spirv-tools clang llvm python-pip ninja rust',
            'install': '',  # Empty since we do it all in the update command
            'rust': ''  # Empty since rust is included in the update command
        },
        'fedora': {
            'update': 'sudo dnf update -y',
            'install': 'sudo dnf install -y gcc gcc-c++ git cmake pkgconfig vulkan-devel vulkan-tools spirv-tools clang-devel llvm-devel python3-pip ninja-build',
            'rust': 'sudo dnf install -y rust cargo'
        },
        'nobara': {
            'update': 'sudo dnf update -y',
            'install': 'sudo dnf install -y gcc gcc-c++ git cmake pkgconfig vulkan-devel vulkan-tools spirv-tools clang-devel llvm-devel python3-pip ninja-build',
            'rust': 'sudo dnf install -y rust cargo'
        }
    }
    return commands.get(distro, {})

class DownloadThread(QThread):
    """Thread for downloading ZLUDA with progress tracking"""
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, url, chunk_size=1024*1024):
        super().__init__()
        self.url = url
        self.chunk_size = chunk_size
        self.stop_download = False
        
    def run(self):
        try:
            self.log_signal.emit(f"Starting download from {self.url}")
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Create a temporary file to store the download
            temp_dir = os.path.dirname(os.path.abspath(__file__))
            temp_file = os.path.join(temp_dir, "zluda_download.tmp")
            
            with open(temp_file, 'wb') as f:
                for data in response.iter_content(chunk_size=self.chunk_size):
                    if self.stop_download:
                        self.log_signal.emit("Download cancelled")
                        self.finished_signal.emit(False, "Download cancelled")
                        return
                        
                    downloaded += len(data)
                    f.write(data)
                    
                    if total_size:
                        progress = int((downloaded / total_size) * 100)
                        self.progress_signal.emit(progress)
                        self.log_signal.emit(f"Download progress: {progress}%")
            
            self.log_signal.emit("Download completed")
            self.finished_signal.emit(True, temp_file)
            
        except Exception as e:
            self.log_signal.emit(f"Download error: {str(e)}")
            self.finished_signal.emit(False, str(e))
            
    def stop(self):
        self.stop_download = True

class ProcessMonitor(QThread):
    """Thread to monitor process output and GPU usage"""
    log_signal = pyqtSignal(str)
    process_ended = pyqtSignal()
    
    def __init__(self, process, zluda_path, gpu_monitor):
        super().__init__()
        self.process = process
        self.zluda_path = zluda_path
        self.running = True
        self.gpu_monitor = gpu_monitor
        
    def run(self):
        while self.running and self.process.poll() is None:
            try:
                # Check for ZLUDA debug output
                if platform.system() == "Windows":
                    try:
                        output = self.process.stdout.readline().decode('utf-8', errors='ignore')
                        if output:
                            self.log_signal.emit(f"Debug: {output.strip()}")
                    except:
                        pass
                else:
                    try:
                        output = self.process.stderr.readline().decode('utf-8', errors='ignore')
                        if output:
                            self.log_signal.emit(f"Debug: {output.strip()}")
                    except:
                        pass
                
                # Check GPU usage
                if self.gpu_monitor:
                    try:
                        self.log_signal.emit("GPU monitoring is not yet implemented for AMD GPUs")
                        # Disable GPU monitoring after first message to avoid spam
                        self.gpu_monitor = False
                    except:
                        pass
                
                time.sleep(1)
            except:
                pass
        
        self.process_ended.emit()
                
    def stop(self):
        self.running = False

class BuildWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        
    def run_command(self, command, env=None, timeout=None):
        """Run a command and stream its output to the progress signal."""
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Create threads to read stdout and stderr
            def read_output(pipe, prefix):
                for line in pipe:
                    line = line.strip()
                    if line:  # Only emit non-empty lines
                        if "Cloning into" in line:
                            self.progress.emit(f"\n{prefix}Starting clone: {line}")
                        elif any(x in line for x in ["Receiving objects:", "Resolving deltas:", "Updating files:", "remote: Counting", "remote: Compressing"]):
                            self.progress.emit(f"\r{prefix}{line}")  # Use \r for progress updates
                        else:
                            self.progress.emit(f"{prefix}{line}")
            
            # Start threads for reading output
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, ""))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "[Info] "))
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            returncode = process.wait()
            
            # Wait for output threads to finish
            stdout_thread.join()
            stderr_thread.join()
            
            return returncode == 0
            
        except Exception as e:
            self.progress.emit(f"[Error] Failed to run command: {str(e)}")
            return False
        
    def run(self):
        try:
            # Get distro-specific commands
            commands = get_package_manager_commands()
            if not commands:
                self.finished.emit(False, "Unsupported Linux distribution")
                return
                
            # Update package manager
            self.progress.emit("=== Updating package manager ===")
            if not self.run_command(commands['update']):
                self.finished.emit(False, "Failed to update package manager")
                return
                
            # Install dependencies
            self.progress.emit("\n=== Installing dependencies ===")
            if not self.run_command(commands['install']):
                self.finished.emit(False, "Failed to install dependencies")
                return
                
            # Install Rust if needed
            self.progress.emit("\n=== Installing Rust ===")
            if not self.run_command(commands['rust']):
                self.finished.emit(False, "Failed to install Rust")
                return
                
            # Source cargo environment
            self.progress.emit("\n=== Setting up Rust environment ===")
            os.environ["PATH"] = f"{str(Path.home())}/.cargo/bin:{os.environ['PATH']}"
            
            # Set up build directory in the GUI folder
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            build_dir = os.path.join(gui_dir, "zluda_build")
            
            # Clean up any existing build directory
            if os.path.exists(build_dir):
                self.progress.emit("\n=== Cleaning up previous build ===")
                try:
                    shutil.rmtree(build_dir)
                except Exception as e:
                    self.progress.emit(f"[Warning] Failed to clean up previous build: {str(e)}")
            
            # Create build directory
            os.makedirs(build_dir, exist_ok=True)
            
            # Clone ZLUDA into the build directory
            self.progress.emit("\n=== Cloning ZLUDA repository ===")
            if not self.run_command(f"git clone --progress https://github.com/vosen/ZLUDA.git {build_dir}"):
                self.progress.emit("\n=== Cleaning up failed clone ===")
                try:
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, "Failed to clone ZLUDA")
                return
            
            # Initialize and update git submodules
            self.progress.emit("\n=== Initializing git submodules ===")
            os.chdir(build_dir)
            
            # Clone LLVM submodule with progress
            self.progress.emit("\n=== Cloning LLVM (this may take a while) ===")
            if not self.run_command("git submodule init ext/llvm-project && git submodule update --progress --depth 1 ext/llvm-project"):
                self.progress.emit("\n=== Cleaning up failed LLVM clone ===")
                try:
                    os.chdir(gui_dir)
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, "Failed to clone LLVM")
                return
            
            # Update other submodules
            self.progress.emit("\n=== Updating other submodules ===")
            if not self.run_command("git submodule update --init --recursive --progress --depth 1 -- $(ls -d ext/* | grep -v llvm-project)"):
                self.progress.emit("\n=== Cleaning up failed submodule initialization ===")
                try:
                    os.chdir(gui_dir)
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, "Failed to initialize other submodules")
                return
            
            # Build ZLUDA
            self.progress.emit("\n=== Building ZLUDA ===")
            build_env = os.environ.copy()
            build_env["RUST_LOG"] = "debug"
            build_env["RUST_BACKTRACE"] = "1"
            
            if not self.run_command("cargo build --release", env=build_env):
                self.progress.emit("\n=== Cleaning up failed build ===")
                try:
                    os.chdir(gui_dir)
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, "Failed to build ZLUDA")
                return
                
            # Find the built library
            self.progress.emit("\n=== Locating built library ===")
            lib_path = None
            for path in Path(build_dir).rglob("*.so"):
                if "target/release" in str(path) and "libzluda" in str(path):
                    lib_path = str(path)
                    self.progress.emit(f"Found library at: {lib_path}")
                    break
                    
            if not lib_path:
                self.progress.emit("\n=== Cleaning up failed build ===")
                try:
                    os.chdir(gui_dir)
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, "Could not find built ZLUDA library")
                return
                
            # Copy the built library to the GUI directory
            target_lib = os.path.join(gui_dir, "libzluda.so")
            try:
                shutil.copy2(lib_path, target_lib)
                self.progress.emit(f"\nCopied library to: {target_lib}")
            except Exception as e:
                self.progress.emit("\n=== Cleaning up failed copy ===")
                try:
                    os.chdir(gui_dir)
                    shutil.rmtree(build_dir)
                except:
                    pass
                self.finished.emit(False, f"Failed to copy library: {str(e)}")
                return
            
            # Clean up build directory
            self.progress.emit("\n=== Cleaning up build directory ===")
            try:
                os.chdir(gui_dir)
                shutil.rmtree(build_dir)
            except Exception as e:
                self.progress.emit(f"[Warning] Failed to clean up build directory: {str(e)}")
            
            self.progress.emit("\n=== Build completed successfully! ===")
            self.finished.emit(True, target_lib)
            
        except Exception as e:
            self.progress.emit(f"\n[Error] Build failed: {str(e)}")
            # Try to clean up on any unexpected error
            try:
                gui_dir = os.path.dirname(os.path.abspath(__file__))
                build_dir = os.path.join(gui_dir, "zluda_build")
                os.chdir(gui_dir)
                if os.path.exists(build_dir):
                    self.progress.emit("\n=== Cleaning up after error ===")
                    shutil.rmtree(build_dir)
            except:
                pass
            self.finished.emit(False, str(e))

class ZLUDA_GUI(QMainWindow):
    def __init__(self):
        # Enable high DPI scaling
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        
        super().__init__()
        self.setWindowTitle("ZLUDA GUI")
        
        # Initialize variables first
        self.current_process = None
        self.process_monitor = None
        self.download_thread = None
        self.download_progress = None
        self.build_worker = None
        
        # Initialize widgets
        self.zluda_path = QLineEdit()
        self.app_path = QLineEdit()
        self.libs_path = QLineEdit()
        self.download_button = QPushButton("Download ZLUDA")
        self.run_button = QPushButton("Run Application")
        self.build_button = QPushButton("Build ZLUDA")
        
        # Connect signals
        self.download_button.clicked.connect(self.download_zluda)
        self.run_button.clicked.connect(self.run_application)
        self.build_button.clicked.connect(self.build_zluda)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with title and version
        header = QHBoxLayout()
        header.setSpacing(6)
        
        title = QLabel("ZLUDA GUI")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #00e5ff;
        """)
        
        version = QLabel("v4.0")
        version.setStyleSheet("""
            font-size: 12px;
            color: #808080;
            padding-top: 4px;
            padding-left: 6px;
        """)
        
        header.addWidget(title)
        header.addWidget(version)
        header.addStretch()
        layout.addLayout(header)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Main tab
        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Debug settings group
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QGridLayout(debug_group)
        debug_layout.setSpacing(10)
        debug_layout.setContentsMargins(12, 20, 12, 12)
        
        # Debug checkboxes with tooltips
        self.zluda_debug = QCheckBox("Enable ZLUDA Debug")
        self.zluda_debug.setChecked(True)
        self.zluda_debug.setToolTip("Enable detailed ZLUDA debugging output")
        
        self.lib_debug = QCheckBox("Enable Library Debug")
        self.lib_debug.setChecked(True)
        self.lib_debug.setToolTip("Enable library loading debug information")
        
        self.gpu_monitor = QCheckBox("Enable GPU Monitoring")
        self.gpu_monitor.setChecked(True)
        self.gpu_monitor.setToolTip("Monitor GPU usage while application is running")
        
        debug_layout.addWidget(self.zluda_debug, 0, 0)
        debug_layout.addWidget(self.lib_debug, 0, 1)
        debug_layout.addWidget(self.gpu_monitor, 1, 0)
        
        # Debug file path
        debug_file_layout = QHBoxLayout()
        debug_file_layout.setSpacing(6)
        
        debug_file_label = QLabel("Debug File:")
        debug_file_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
        """)
        
        self.debug_file = QLineEdit("/tmp/zluda_debug.log")
        self.debug_file.setPlaceholderText("Debug log file path")
        
        debug_file_layout.addWidget(debug_file_label)
        debug_file_layout.addWidget(self.debug_file)
        debug_layout.addLayout(debug_file_layout, 1, 1)
        
        main_layout.addWidget(debug_group)
        
        # Path input frames
        path_frames = [
            ("ZLUDA Library Path", self.zluda_path, "Select ZLUDA library file", self.browse_zluda),
            ("Application Path", self.app_path, "Select application executable", self.browse_application),
            ("Additional Libraries Path", self.libs_path, "Select additional libraries directory (optional)", self.browse_libs)
        ]
        
        for label_text, line_edit, placeholder, browse_handler in path_frames:
            frame = QFrame()
            frame_layout = QVBoxLayout(frame)
            frame_layout.setSpacing(6)
            frame_layout.setContentsMargins(12, 12, 12, 12)
            
            label = QLabel(label_text)
            label.setStyleSheet("""
                color: #00e5ff;
                font-weight: bold;
                font-size: 12px;
                margin-bottom: 3px;
            """)
            frame_layout.addWidget(label)
            
            path_layout = QHBoxLayout()
            path_layout.setSpacing(6)
            
            line_edit.setPlaceholderText(placeholder)
            path_layout.addWidget(line_edit)
            
            browse_btn = QPushButton("Browse")
            browse_btn.setProperty("cssClass", "browse")
            browse_btn.clicked.connect(browse_handler)
            path_layout.addWidget(browse_btn)
            
            frame_layout.addLayout(path_layout)
            main_layout.addWidget(frame)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # Set button styles
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #00796b;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #00897b;
            }
            QPushButton:pressed {
                background-color: #00695c;
            }
            QPushButton:disabled {
                background-color: #2d3436;
                color: #666666;
            }
        """)
        
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #006064;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #00838f;
            }
            QPushButton:pressed {
                background-color: #005662;
            }
            QPushButton:disabled {
                background-color: #2d3436;
                color: #666666;
            }
        """)
        
        self.build_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
            QPushButton:pressed {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #2d3436;
                color: #666666;
            }
        """)
        
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.build_button)
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        # Progress bars
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)
        
        self.build_progress = QProgressBar()
        self.build_progress.setTextVisible(False)
        self.build_progress.hide()
        main_layout.addWidget(self.build_progress)
        
        # Log areas
        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        log_layout.setSpacing(6)
        log_layout.setContentsMargins(12, 12, 12, 12)
        
        log_header = QHBoxLayout()
        log_label = QLabel("Log Output")
        log_label.setStyleSheet("""
            color: #00e5ff;
            font-weight: bold;
            font-size: 12px;
            margin-bottom: 3px;
        """)
        log_header.addWidget(log_label)
        log_layout.addLayout(log_header)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        log_layout.addWidget(self.log_area)
        
        main_layout.addWidget(log_frame)
        
        # Add main tab
        tabs.addTab(main_tab, "Main")
        
        # Debug tab
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)
        debug_layout.setSpacing(12)
        debug_layout.setContentsMargins(15, 15, 15, 15)
        
        debug_log_frame = QFrame()
        debug_log_layout = QVBoxLayout(debug_log_frame)
        debug_log_layout.setSpacing(6)
        debug_log_layout.setContentsMargins(12, 12, 12, 12)
        
        debug_log_header = QHBoxLayout()
        debug_log_label = QLabel("Debug Output")
        debug_log_label.setStyleSheet("""
            color: #00e5ff;
            font-weight: bold;
            font-size: 12px;
            margin-bottom: 3px;
        """)
        debug_log_header.addWidget(debug_log_label)
        debug_log_layout.addLayout(debug_log_header)
        
        self.debug_log_area = QTextEdit()
        self.debug_log_area.setReadOnly(True)
        self.debug_log_area.setMinimumHeight(300)
        debug_log_layout.addWidget(self.debug_log_area)
        
        debug_layout.addWidget(debug_log_frame)
        
        # Add debug tab
        tabs.addTab(debug_tab, "Debug")
        
        # Set window flags for proper window controls
        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint
        )
        
        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QGroupBox {
                background-color: #212121;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                margin-top: 12px;
                padding: 15px;
            }
            QFrame {
                background-color: #212121;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px 10px;
                color: white;
            }
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 8px;
                color: white;
            }
            QPushButton[cssClass="browse"] {
                background-color: #333333;
                padding: 6px 12px;
                min-width: 70px;
            }
            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                background-color: #212121;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #b0b0b0;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #212121;
                color: #00e5ff;
                border-bottom: 2px solid #00e5ff;
            }
        """)
        
        # Maximize the window by default
        self.setWindowState(Qt.WindowMaximized)

    def log(self, message):
        """Add a message to the main log area"""
        self.log_area.append(message)
        QApplication.processEvents()
        
    def debug_log(self, message):
        """Add a message to the debug log area"""
        self.debug_log_area.append(message)
        QApplication.processEvents()
        
    def browse_zluda(self):
        if platform.system() == "Windows":
            file_filter = "DLL Files (*.dll)"
        else:
            file_filter = "Library Files (*.so)"
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ZLUDA Library", "", file_filter
        )
        if file_path:
            self.zluda_path.setText(file_path)
            
    def browse_application(self):
        if platform.system() == "Windows":
            file_filter = "Executable Files (*.exe)"
        else:
            file_filter = "All Files (*)"
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Application", "", file_filter
        )
        if file_path:
            self.app_path.setText(file_path)
            
    def browse_libs(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Libs Folder"
        )
        if dir_path:
            self.libs_path.setText(dir_path)
            
    def download_zluda(self):
        try:
            self.log("Starting ZLUDA download process...")
            self.log(f"Detected operating system: {platform.system()}")
            
            # Determine the appropriate download URL based on OS
            if platform.system() == "Windows":
                download_url = "https://github.com/vosen/ZLUDA/releases/download/v4/zluda-4-windows.zip"
                archive_type = "zip"
                lib_extension = ".dll"
            else:  # Linux
                download_url = "https://github.com/vosen/ZLUDA/releases/download/v4/zluda-4-linux.tar.gz"
                archive_type = "tar.gz"
                lib_extension = ".so"
                
            # Start download thread
            self.download_thread = DownloadThread(download_url)
            self.download_thread.progress_signal.connect(self.progress_bar.setValue)
            self.download_thread.log_signal.connect(self.log)
            self.download_thread.finished_signal.connect(lambda success, result: self.handle_download_finished(success, result, archive_type, lib_extension))
            self.download_thread.start()
            
            # Disable download button while downloading
            self.download_button.setEnabled(False)
            
        except Exception as e:
            error_msg = f"Failed to start download: {str(e)}"
            self.log(f"Error: {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)
            
    def handle_download_finished(self, success, result, archive_type, lib_extension):
        self.download_button.setEnabled(True)
        
        if not success:
            QMessageBox.critical(self, "Error", f"Download failed: {result}")
            return
            
        try:
            self.log("Extracting files...")
            temp_file = result
            
            # Extract the archive based on type
            if archive_type == "zip":
                with zipfile.ZipFile(temp_file) as zip_ref:
                    file_list = zip_ref.namelist()
                    self.log(f"Found {len(file_list)} files in the archive")
                    self.log("Extracting to current directory...")
                    zip_ref.extractall(os.path.dirname(os.path.abspath(__file__)))
            else:  # tar.gz
                with tarfile.open(temp_file, mode='r:gz') as tar_ref:
                    file_list = tar_ref.getnames()
                    self.log(f"Found {len(file_list)} files in the archive")
                    self.log("Extracting to current directory...")
                    tar_ref.extractall(os.path.dirname(os.path.abspath(__file__)))
                
            self.log("Extraction completed successfully!")
            self.log("ZLUDA has been downloaded and installed")
            
            # Update the ZLUDA path if a library file was found
            for file in file_list:
                if file.endswith(lib_extension):
                    zluda_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file)
                    self.zluda_path.setText(zluda_path)
                    self.log(f"Automatically set ZLUDA path to: {zluda_path}")
                    break
                    
            # Clean up the temporary file
            try:
                os.remove(temp_file)
                self.log("Cleaned up temporary download file")
            except:
                pass
                
        except Exception as e:
            error_msg = f"Failed to extract files: {str(e)}"
            self.log(f"Error: {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)

    def check_zluda_loaded(self, pid):
        """Check if ZLUDA is loaded in the process"""
        try:
            process = psutil.Process(pid)
            if platform.system() == "Windows":
                # On Windows, check loaded DLLs
                dlls = [dll.path.lower() for dll in process.memory_maps()]
                zluda_dll = self.zluda_path.text().lower()
                return any(zluda_dll in dll for dll in dlls)
            else:
                # On Linux, check LD_PRELOAD
                env = process.environ()
                return self.zluda_path.text() in env.get("LD_PRELOAD", "")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
            
    def run_application(self):
        zluda_path = self.zluda_path.text()
        app_path = self.app_path.text()
        libs_path = self.libs_path.text()
        
        if not zluda_path or not app_path:
            QMessageBox.warning(self, "Warning", "Please specify both ZLUDA library and application paths")
            return
            
        try:
            self.log("Preparing to run application...")
            self.log(f"ZLUDA path: {zluda_path}")
            self.log(f"Application path: {app_path}")
            if libs_path:
                self.log(f"Libs path: {libs_path}")
            
            # Prepare environment variables
            env = os.environ.copy()
            if platform.system() == "Windows":
                zluda_dir = os.path.dirname(zluda_path)
                env["PATH"] = f"{zluda_dir}{os.pathsep}{env.get('PATH', '')}"
                self.log(f"Added ZLUDA directory to PATH: {zluda_dir}")
            else:
                # On Linux, use absolute paths
                zluda_path = os.path.abspath(zluda_path)
                zluda_dir = os.path.dirname(zluda_path)
                
                # Set up environment variables
                env["LD_PRELOAD"] = zluda_path
                env["LD_LIBRARY_PATH"] = f"{zluda_dir}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
                
                # Add CUDA specific variables
                env["CUDA_CACHE_PATH"] = os.path.expanduser("~/.nv/ComputeCache")
                env["CUDA_CACHE_DISABLE"] = "0"
                
                self.log(f"Set LD_PRELOAD to: {zluda_path}")
                self.log(f"Set LD_LIBRARY_PATH to: {zluda_dir}")
                
            if libs_path:
                libs_path = os.path.abspath(libs_path)
                if platform.system() == "Windows":
                    env["PATH"] = f"{libs_path}{os.pathsep}{env.get('PATH', '')}"
                    self.log(f"Added libs directory to PATH: {libs_path}")
                else:
                    env["LD_LIBRARY_PATH"] = f"{libs_path}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
                    self.log(f"Added libs directory to LD_LIBRARY_PATH: {libs_path}")
            
            # Set debug flags based on GUI settings
            if self.zluda_debug.isChecked():
                env["ZLUDA_DEBUG"] = "1"
                self.log("Enabled ZLUDA debug output")
            
            if self.lib_debug.isChecked() and platform.system() == "Linux":
                env["LD_DEBUG"] = "libs"
                debug_file = self.debug_file.text()
                env["LD_DEBUG_OUTPUT"] = debug_file
                self.log(f"Enabled library debug output to: {debug_file}")
            
            # Run the application
            self.log("Starting application...")
            try:
                # Clean up any existing process
                if self.process_monitor:
                    self.process_monitor.stop()
                    self.process_monitor.wait()
                    self.process_monitor = None
                
                if self.current_process:
                    try:
                        self.current_process.terminate()
                        self.current_process.wait(timeout=5)
                    except:
                        pass
                    self.current_process = None
                
                # On Linux, run the application directly
                if platform.system() == "Linux":
                    app_path = os.path.abspath(app_path)
                    # Make sure the application is executable
                    os.chmod(app_path, 0o755)
                    
                    self.log("Running application with the following environment:")
                    for key, value in env.items():
                        if key.startswith(("LD_", "CUDA_")):
                            self.log(f"{key}={value}")
                    
                    process = subprocess.Popen(
                        [app_path],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                else:
                    process = subprocess.Popen(
                        [app_path],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                
                self.current_process = process
                self.log(f"Application started with PID: {process.pid}")
                
                # Start process monitor
                self.process_monitor = ProcessMonitor(process, zluda_path, self.gpu_monitor.isChecked())
                self.process_monitor.log_signal.connect(self.debug_log)
                self.process_monitor.process_ended.connect(self.on_process_ended)
                self.process_monitor.start()
                
                # Check if ZLUDA is loaded
                if self.check_zluda_loaded(process.pid):
                    self.log("✅ ZLUDA is successfully loaded in the application!")
                else:
                    self.log("❌ ZLUDA is not loaded in the application. Please check the configuration.")
                
                self.log("Application started successfully!")
                
            except Exception as e:
                error_msg = f"Failed to start application: {str(e)}"
                self.log(f"Error: {error_msg}")
                QMessageBox.critical(self, "Error", error_msg)
            
        except Exception as e:
            error_msg = f"Failed to run application: {str(e)}"
            self.log(f"Error: {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)

    def on_process_ended(self):
        """Handle when the application process ends"""
        self.log("Application has terminated")
        self.debug_log("Process monitor stopped")
        
        # Clean up process monitor
        if self.process_monitor:
            self.process_monitor.stop()
            self.process_monitor.wait()
            self.process_monitor = None
        
        # Reset process reference
        self.current_process = None

    def build_zluda(self):
        """Build ZLUDA from source."""
        if not sys.platform.startswith('linux'):
            QMessageBox.warning(self, "Error", "ZLUDA building is only supported on Linux")
            return
            
        # Check for admin privileges
        if not check_admin():
            reply = QMessageBox.question(
                self,
                "Admin Privileges Required",
                "Installing dependencies requires administrator privileges. Would you like to restart the application as admin?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.log("Restarting with admin privileges...")
                if restart_as_admin():
                    sys.exit(0)  # Exit current instance
                else:
                    QMessageBox.critical(self, "Error", "Failed to restart with admin privileges")
                    return
            else:
                return
            
        reply = QMessageBox.question(
            self,
            "Build ZLUDA",
            "This will install required dependencies and build ZLUDA from source. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
            
        # Disable buttons during build
        self.build_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.run_button.setEnabled(False)
        
        # Show and start progress bar
        self.build_progress.setRange(0, 0)  # Indeterminate mode
        self.build_progress.show()
        
        # Start build process
        self.build_worker = BuildWorker()
        self.build_worker.progress.connect(self.update_build_progress)
        self.build_worker.finished.connect(self.build_finished)
        self.build_worker.start()
        
    def update_build_progress(self, message):
        """Update build progress in log area."""
        self.log_area.append(f"[Build] {message}")
        
    def build_finished(self, success, result):
        """Handle build completion."""
        # Re-enable buttons
        self.build_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.run_button.setEnabled(True)
        
        # Hide progress bar
        self.build_progress.hide()
        
        if success:
            self.log_area.append("[Build] ZLUDA built successfully!")
            self.zluda_path.setText(result)
        else:
            self.log_area.append(f"[Build] Error: {result}")
            QMessageBox.warning(self, "Build Error", f"Failed to build ZLUDA: {result}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZLUDA_GUI()
    window.show()
    sys.exit(app.exec()) 