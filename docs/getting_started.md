# Getting Started

This guide outlines how to set up the `tgftools` framework and start working on Investment Case (IC) projects.

## 1. Prerequisites

Before you begin, ensure you have the following installed:
- [Git](https://git-scm.com/downloads)
- [Python 3.11](https://www.python.org/downloads/) (for manual installation) or [Conda/Miniconda](https://docs.conda.io/en/latest/miniconda.html)

## 2. Initial Setup

### Clone the Repository
Clone the `tgftools` repository to your local machine:
```bash
git clone https://github.com/globalfund-pri/model_code_pipeline.git
```
(Alternatively, use the Git menu in PyCharm to clone the project).

### Environment Configuration

#### Non-TGF Devices (Using Conda)
Use `conda` to create and activate the environment:
```bash
conda env create -f environment.yml
conda activate tgftools
```

#### TGF Devices (Manual Installation)
For TGF laptop users, follow these steps if Anaconda is not available:
1. Ensure Python 3.10 (available via Software Center) or Python 3.11 is installed.
2. Manually install the packages listed in `environment.yml`.
3. Pay close attention to `mkdocs` and `mkdocstrings` requirements for documentation.

### PyCharm Setup (Recommended)
1. Open the cloned folder in PyCharm.
2. Set the Python Interpreter to the `tgftools` environment.
3. Mark the `src/` directory as **Sources Root** and the `tests/` directory as **Test Sources Root**.
    - Right-click on `src` -> Mark Directory as -> Sources Root.
    - Right-click on `tests` -> Mark Directory as -> Test Sources Root.
4. Configure PyCharm to use `pytest` as the default test runner:
    - Go to **Settings** (or **Preferences** on Mac) -> **Tools** -> **Python Integrated Tools**.
    - Under **Testing**, change **Default test runner** to **pytest**.
    - Click **OK**.
5. To run the tests, right-click on the `tests` directory and select **Run 'pytest in tests'**.

## 3. Local Configuration (`tgftools.conf`)

The framework requires a local configuration file to locate data.
1. Create a copy of `tgftools.example.conf` and name it `tgftools.conf` in the project root.
2. Edit `tgftools.conf` to set the `DATA_FOLDER_PATH` to your local data directory.

**Example Paths:**
- **Mac:** `/Users/username/TGF_data/`
- **Windows:** `C:\Users\username\OneDrive - The Global Fund\Documents\TGF_data\`

## 4. Accessing Project Data

The static input data files are hosted on SharePoint.
1. Download the contents of the [MCP TGF_data folder](https://tgf.sharepoint.com/:f:/r/sites/TSSIN1/PRIE/Project%20folders/Investment%20cases/Investment%20case%20for%208th%20replenishment/MCP/TGF_data?csf=1&web=1&e=niKgXq).
2. Place these files into the `DATA_FOLDER_PATH` directory you specified in `tgftools.conf`.

## 5. Project Structure

- `src/tgftools`: Core framework modules (Avoid modifying unless fixing framework bugs).
- `src/scripts`: Project-specific scripts (e.g., `ic7`, `ic8`).
- `resources`: Shared resources and configuration templates.
- `tests`: Unit and integration tests.
- `pytest.ini`: Pytest configuration.

## 6. Contributing

### Working on Projects
- Create a new branch named `username/feature_name` from `main`.
- Work exclusively on your branch.
- Push your changes and create a Pull Request for review.

### Coding Practices
- **Annotation:** Annotate code sufficiently to describe logic.
- **Naming:** Use lowercase and short, descriptive variable names.
- **Hard-coding:** Avoid hard-coding paths or parameters. Use `tgftools.conf` or configuration objects instead.
- **Testing:** If adding new functionality, include tests in the `tests/` directory.

## 7. Documentation

To view the documentation locally:
```bash
mkdocs build
mkdocs serve
```
Then navigate to `http://127.0.0.1:8000/` in your browser.

