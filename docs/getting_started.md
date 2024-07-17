# Getting Started

This file will outline how to get started with the tgftool framework. The tutorial page provides a dummy's guide to the 
overall framework, its core modules and how they interact. This page aims to provide the key information for someone to
get set up with tgftools, and start working on an existing project or set up a new project. It will provide information
regarding which files are core to the framework (and thus should not be unduly modified) and the scripts that are 
project-specific should be modified/developed for each project. 

1. How to get started
- Request access to the tgftools git repository
- In PyCharm, under the Git menu, select clone of tgftools
- The ReadMe file contains instructions on how to install anaconda and set the interpreter
- In the file tgftools.conf set the local path to your project folder for MAC users this will resemble e.g. /Users/mc1405/TGF_data/
- for GF PCs this will resemble e.g. C:\Users\XXX\OneDrive - The Global Fund\Documents\XXXI\TGF_data\

- Add the contents of the Sharepoint folder below to your local folder TGF_data created in step 4
  https://tgf.sharepoint.com/:f:/r/sites/TSSIN1/PRIE/Project%20folders/Investment%20cases/Investment%20case%20for%208th%20replenishment/MCP/TGF_data?csf=1&web=1&e=niKgXq

2. Setting up a new project
To set up a new project (e.g. for the Investment Case for the 8th Replenishment), a new sub-folder should be set up in 
the folder scr/scripts. Code from previous projects folder can be used as a base but should be updated to be made 
project-specific. 
TIM - WHAT ABOUT RESOURCES (AND SESSIONS), can we keep a  copy of these for each project? 
TIM - The test files may also need to be updated accordingly?

4. Joining an exising project
When joining an existing project, users are asked to create a new branch (username/branch_name) from main and work on 
their branches only. 

5. What should be modified and what should not be modified
The Index Page provides an overview to the framework structure and a quick guide to which parts of the framework should
and should not be modified.

6. Good coding practice
- Everyone should work on git, and push to their individual branches only. Merging to be done when core updates to the
code are made that should be used by all users
- Every piece of code should be annotated sufficiently to provide a good description of what the line(s) of code do
- Variable names: should be use small letter and be short but easy to understand 
- Hard-coding: to be avoided at all costs and if at all limited to these disease files 

