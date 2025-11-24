import subprocess
import os
import platform
from pathlib import Path


def get_r_executable():
    """
    Get the path to Rscript executable based on the operating system
    """
    system = platform.system()

    if system == "Windows":
        # Common R installation paths on Windows
        possible_paths = [
            r"C:\Program Files\R\R-4.x.x\bin\Rscript.exe",
            r"C:\Program Files\R\R-4.x.x\bin\x64\Rscript.exe",
        ]
        # Try to find R in Program Files
        for root in [os.environ.get("ProgramFiles", "C:\\Program Files"),
                     os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")]:
            if os.path.exists(root):
                r_folder = Path(root) / "R"
                if r_folder.exists():
                    for r_version in r_folder.iterdir():
                        rscript = r_version / "bin" / "Rscript.exe"
                        if rscript.exists():
                            return str(rscript)

    elif system == "Darwin":  # macOS
        possible_paths = [
            "/usr/local/bin/Rscript",
            "/usr/bin/Rscript",
            "/opt/homebrew/bin/Rscript",  # For Apple Silicon Macs using Homebrew
        ]
    else:  # Linux/Unix
        possible_paths = [
            "/usr/bin/Rscript",
            "/usr/local/bin/Rscript",
        ]

    # Try each possible path
    for path in possible_paths:
        if os.path.exists(path):
            return path

    # If we can't find R, try using 'which' command on Unix-like systems
    if system != "Windows":
        try:
            result = subprocess.run(['which', 'Rscript'],
                                    capture_output=True,
                                    text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

    raise FileNotFoundError("Could not find Rscript executable. Please ensure R is installed and add it to your PATH")


def run_r_script(r_file_path, *args):
    """
    Run an R script file from Python

    Args:
        r_file_path (str): Path to the R script file
        *args: Arguments to pass to the R script

    Returns:
        list: The numeric results from the R script
    """
    try:
        # Check if the R script file exists
        if not os.path.exists(r_file_path):
            raise FileNotFoundError(f"R script not found at: {r_file_path}")

        # Get the R executable path
        r_executable = get_r_executable()

        str_args = [str(arg) for arg in args]

        # Construct the command
        cmd = [r_executable, str(r_file_path)] + str_args

        # Run the R script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # If there's any error output, print it
        if result.stderr:
            print("Warning/Info from R:", result.stderr)

        # Parse the output - split by newlines and convert to floatw
        output = [float(x.strip()) for x in result.stdout.strip().split('\n') if x.strip()]
        return output

    except subprocess.CalledProcessError as e:
        print(f"R script failed with error:\n{e.stderr}")
        raise
    except ValueError as e:
        print(f"Failed to parse R output as numbers:\n{result.stdout}")
        raise
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise
