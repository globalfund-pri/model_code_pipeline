# This is a simple R program where the ROI analysis will be inserted.

args <- commandArgs(trailingOnly = TRUE)

# Print the arguments received
print("Arguments received:")
print(args)

# Check if we have the required number of arguments
if (length(args) < 3) {
    stop("Not enough arguments. Please provide input_file and output_file")
}

# Access arguments by position
input_file <- args[1]
output_file <- args[2]
parameters_file <- args[3]



# Read the inputfile
print("Reading input data...")
data <- read.csv(input_file)

# Print the first 5 rows
print("First 5 rows of the input data:")
print(head(data, 5))



# Save results to the expected location

# As an test, create some sample data first
sample_data <- data.frame(
  ID = 1:10,
  Name = c("Alice", "Bob", "Charlie", "David", "Eve",
           "Frank", "Grace", "Henry", "Ivy", "Jack"),
  Value = c(23, 45, 67, 89, 12, 34, 56, 78, 90, 11)
)

# Save sample data
write.csv(sample_data, output_file, row.names = FALSE)
print("Created sample input data file")




