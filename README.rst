Utilities For Analyses by The Global Fund
==========================================
blugh

Initial Set Up - non GF devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/>`_ to set up an environment using:

``conda env create``

and then

``conda activate tgftools`` (and/or point PyCharm to ``tgftools`` as the Python Interpreter).

If you're lucky PyCharm will do this all for you when you first open the project!

Initial Set Up - GF devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~
For TGF laptop users, do not use Anaconda/Conda but install all packages listed in environment.yml manually including
those under pip. Take particular care to install the correct packages for mkdocs as several have similar names.

Note that Python 3.10 is the latest release available to TGF user via the Software Center and check that Python 3.10 is running in
tgftools virtual environment. Check bottom right corner shows Python 3.10 (tgftools) and if not, modify in
Project: tgftools > Python Interpreter

For markdown docs (mkdocs) to run, you *may* need to tell python where mkdocs.yml is located. In powershell try
``C:\Users\rgrahn\PycharmProjects\tgftools> ./venv/Scripts/mkdocs build`` and then
``C:\Users\rgrahn\PycharmProjects\tgftools> ./venv/Scripts/mkdocs serve``
You may now consult the markdown documents in your browser.
Type `Control C` in the powershell window and then `exit` to close the browser



Further Set Up - GF and non GF devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


You will need to declare the local path of the data folder containing static input files. Do this by making a copy of the `tgftools.example.conf` named `tgftools.conf` and writing in the path.

Typical path for TGF PC users is:
DATA_FOLDER_PATH = ``C:\Users\rgrahn\OneDrive - The Global Fund\Documents\rgrahn\TGF_data\``

Follow the instructions in ``docs/getting_started.md``

For developing:

1) You *may* need to manually set-up ``Pytest`` (see `Instructions <https://www.jetbrains.com/help/pycharm/pytest.html>`_).
2) You will need to mark the ``tests\`` directory as the "Test Sources Root" and ``src\`` as the "Sources Root"
3) It is recommended to  launch the ``Documentation for tgftools`` per below


Documentation
~~~~~~~~~~~~~
To view locally, type ``mkdocs build``, and then open ``site/index.html``.
(We will host this using ``mkdocs gh-deploy`` when we have a GitHub account with Pages enabled.)

