from pathlib import Path
import os
import platform
import subprocess
import sys


def get_r_executable() -> str:
    """Get the path to the Rscript executable in a robust way.

    The function searches for the Rscript executable in the following order:
        1. CONDA_PREFIX/bin/Rscript if CONDA_PREFIX is set (active conda environment)
        2. Same directory as sys.executable (handles case where environment python
           is used but PATH is not updated)
        3. Common platform-specific locations (/usr/bin/Rscript, /usr/local/bin/Rscript, etc.)
        4. Using 'which Rscript' on Unix-like systems

    Returns:
        The absolute path to the Rscript executable.

    Raises:
        FileNotFoundError: If the Rscript executable cannot be found in any of
            the searched locations.
    """
    system = platform.system()

    # 1) Check CONDA_PREFIX (active conda env)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidate = Path(conda_prefix) / "bin" / "Rscript"
        if candidate.exists():
            return str(candidate)

    # 2) Check same env as sys.executable (useful when tests use env python but PATH isn't updated)
    try:
        exe_path = Path(sys.executable).resolve()
        env_bin = exe_path.parent
        candidate = env_bin / "Rscript"
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass

    # Platform-specific common locations
    possible_paths = []
    if system == "Windows":
        possible_paths = [
            r"C:\Program Files\R\R-4.x.x\bin\Rscript.exe",
            r"C:\Program Files\R\R-4.x.x\bin\x64\Rscript.exe",
        ]
        # Also try ProgramFiles scanning
        for root in [os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]:
            if root and os.path.exists(root):
                r_folder = Path(root) / "R"
                if r_folder.exists():
                    for r_version in r_folder.iterdir():
                        rscript = r_version / "bin" / "Rscript.exe"
                        if rscript.exists():
                            return str(rscript)
    elif system == "Darwin":
        possible_paths = [
            "/usr/local/bin/Rscript",
            "/usr/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
        ]
    else:
        possible_paths = [
            "/usr/bin/Rscript",
            "/usr/local/bin/Rscript",
        ]

    for p in possible_paths:
        if p and os.path.exists(p):
            return str(p)

    # Fallback: which
    if system != "Windows":
        try:
            result = subprocess.run(["which", "Rscript"], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    return path
        except Exception:
            pass

    raise FileNotFoundError(
        "Could not find Rscript executable. Please ensure R is installed and add it to your PATH"
    )


def run_r_script(r_file_path, *args):
    """Run an R script file from Python.

    The function locates the R executable, runs the specified script with the
    provided arguments, and returns the numeric output. The R script output
    is expected to be numeric values separated by newlines.

    Args:
        r_file_path: Path to the R script file.
        *args: Arguments to pass to the R script. All arguments are converted
            to strings before being passed to the script.

    Returns:
        List of numeric (float) results from the R script, parsed from stdout.

    Raises:
        FileNotFoundError: If the R script file does not exist.
        subprocess.CalledProcessError: If the R script execution fails.
        ValueError: If the R script output cannot be parsed as numeric values.
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

        # Parse the output - split by newlines and convert to float
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
