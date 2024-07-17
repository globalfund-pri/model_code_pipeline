# Documentation for `tgftools`

## Start Here

* Tutorial
* Getting Started
* Example scripts from Investment Case 7
* Scripts from Investment Case 8
* Reference book



## Project layout

    src/                # All the code
        tgftools/       # The code for the framework (not to be modified)
        scripts/        # The scripts that do the analysis (to be modified in project folder(s))
            ic7/        #   ... the scripts for investment case 7 analyses 

    docs/               # Documentation for the framework write-up (to be modified)
        diagrams        # All diagrams for the documentation are saved here
    tests/              # All the tests of the framework (not to be modified)
    outputs/            # Default location for outputs (local)
    sessions/           # Default location for stored sessions (local)
    resources/          # This conains all the parameters and fixed inputs for the code (to be modified)
        countries/      # Contains lists of ISO3 codes for model output and portfolio, per disease
        defintions/     # Contains lists of service coverage indicators per disease and scenario names
        fixed_gps/      # Contains fixed parameters to generate the Gp, per disease
        parameter.csv   # Contains the key central parameters