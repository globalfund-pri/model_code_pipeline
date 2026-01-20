# This is a simple R program
# Purpose: Test interaction with python: Adds 10 to every item received.

# Get the arguements
args <- commandArgs(trailingOnly = TRUE)

# Convert arguments to numeric
args_numeric <- as.numeric(args)

# Add 10 to each value
result <- args_numeric + 10

# Print results one per line, with no extra text (This is parsed by the calling code)
for (val in result) {
    cat(val, "\n")
}


