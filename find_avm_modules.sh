#!/bin/bash
#####################################################################
# Script: find_avm_modules.sh
# Description: This script automates the process of finding and processing 
#              Azure Verified Modules (AVM) from a deployment CSV file.
#              It integrates with two Python scripts:
#              - avm_module_finder.py: Identifies AVM modules from deployment CSV
#              - avm_module_parameter_parser.py: Processes each available module
# Usage: ./find_avm_modules.sh <deployment_csv_path>
# Author: Unknown
# Date: July 3, 2025
#####################################################################

# Function to display script usage information
display_usage() {
    echo "Usage: $0 <deployment_csv_path>"
    echo "Example: $0 /home/azureuser/todoappwksp/todoapp/deployment.csv"
    echo
    echo "This script:"
    echo "1. Runs avm_module_finder.py with the provided deployment CSV"
    echo "2. Checks for the existence of AVMModuleMaster.csv"
    echo "3. Processes each available AVM module"
    echo "4. Logs all activities to the logs directory"
}

# Function for logging with different severity levels
# Parameters:
#   $1: Log level (INFO, WARN, ERROR)
#   $2: Message to be logged
# Output:
#   - Colored console output based on log level
#   - Log file entry with timestamp and log level
log() {
    local log_level=$1
    local message=$2
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Create logs directory if it doesn't exist
    mkdir -p "$(dirname "$0")/logs"
    
    # Print to console with color coding based on log level
    case $log_level in
        "INFO") echo -e "\033[0;32m[INFO]\033[0m $timestamp - $message" ;;  # Green
        "WARN") echo -e "\033[0;33m[WARN]\033[0m $timestamp - $message" ;;  # Yellow
        "ERROR") echo -e "\033[0;31m[ERROR]\033[0m $timestamp - $message" ;; # Red
        *) echo "$timestamp - $message" ;;  # Default with no color
    esac
    
    # Write to log file with date-based filename
    echo "[$log_level] $timestamp - $message" >> "$(dirname "$0")/logs/avm_processing_$(date '+%Y%m%d').log"
}

# Input validation section
# Check if the correct number of arguments is provided
if [ $# -ne 1 ]; then
    log "ERROR" "Missing or incorrect arguments"
    display_usage
    exit 1
fi

# Assign the input argument to a variable
deployment_csv_path=$1

# Verify the deployment CSV file exists
if [ ! -f "$deployment_csv_path" ]; then
    log "ERROR" "Deployment CSV file not found: $deployment_csv_path"
    exit 1
fi

# Setup phase: Determine paths and validate prerequisite files
# Get the absolute path of the script directory
script_dir=$(dirname "$(realpath "$0")")
log "INFO" "Script directory: $script_dir"

# Define paths to required Python scripts
module_finder_script="$script_dir/avm_module_finder.py"
param_parser_script="$script_dir/avm_module_parameter_parser.py"

# Validate that the required Python scripts exist
if [ ! -f "$module_finder_script" ]; then
    log "ERROR" "Module finder script not found: $module_finder_script"
    exit 1
fi

if [ ! -f "$param_parser_script" ]; then
    log "ERROR" "Parameter parser script not found: $param_parser_script"
    exit 1
fi

# Phase 1: Run the module finder script to identify AVM modules from the deployment CSV
log "INFO" "Running module finder with deployment CSV: $deployment_csv_path"
python3 "$module_finder_script" "$deployment_csv_path"

# Check if the module finder script executed successfully
if [ $? -ne 0 ]; then
    log "ERROR" "Module finder script failed"
    exit 1
fi

# Phase 2: Validate the output from the module finder script
# Define the path to the expected output CSV file
avm_master_csv="$script_dir/output/AVMModuleMaster.csv"

# Check if the output CSV file exists
if [ ! -f "$avm_master_csv" ]; then
    log "ERROR" "AVMModuleMaster.csv file not found at: $avm_master_csv"
    exit 1
fi

# Check if the output CSV file has meaningful content (more than just a header)
line_count=$(wc -l < "$avm_master_csv")
if [ "$line_count" -le 1 ]; then
    log "ERROR" "AVMModuleMaster.csv file is empty or only contains headers"
    exit 1
fi

log "INFO" "AVMModuleMaster.csv found and contains data"

# Phase 3: Process each available AVM module
log "INFO" "Processing available modules from AVMModuleMaster.csv"

# Initialize counters and data structures
processed_count=0
failed_count=0
declare -a available_modules=()

# Create a temporary file to track statistics across subshell context
# This is needed because variables set inside a pipe loop are lost due to subshell execution
tmp_stats_file=$(mktemp)
echo "0 0" > "$tmp_stats_file"  # Initialize: processed_count failed_count

# Read the CSV file line by line, skipping the header row
# Format of CSV: provider_namespace,resource_type,module_name,status,repo_url,registry_ref,...
tail -n +2 "$avm_master_csv" | while IFS=, read -r provider_namespace resource_type module_name status repo_url registry_ref rest; do
    # Clean up the status field by removing quotes and whitespace
    status=$(echo "$status" | tr -d '"' | tr -d ' ')
    
    # Process only modules with 'Available' status
    if [ "$status" = "Available" ]; then
        log "INFO" "Processing module: $module_name"
        
        # Format the module path in the required format for the parameter parser
        module_path="Azure/$module_name/azurerm"
        log "INFO" "Running parser with module path: $module_path"
        
        # Ensure the requests Python package is installed (required by parameter parser)
        pip3 install --quiet requests >/dev/null 2>&1
        
        # Run the parameter parser for this module
        python3 "$param_parser_script" "$module_path"
        
        # Check if parameter parser executed successfully
        if [ $? -eq 0 ]; then
            log "INFO" "Successfully processed module: $module_name"
            # Update success counter and add to available modules list
            read p f < "$tmp_stats_file"
            echo "$((p+1)) $f" > "$tmp_stats_file"
            available_modules+=("$module_name")
        else
            log "WARN" "Failed to process module: $module_name"
            # Update failure counter
            read p f < "$tmp_stats_file"
            echo "$p $((f+1))" > "$tmp_stats_file"
        fi
    else
        log "INFO" "Skipping module with status '$status': $module_name"
    fi
done

# Read final statistics from the temporary file
read processed_count failed_count < "$tmp_stats_file"
rm -f "$tmp_stats_file"  # Clean up temporary file

# Phase 4: List and report on generated output files
output_dir="$script_dir/output"
if [ -d "$output_dir" ]; then
    log "INFO" "Generated output files in $output_dir:"
    # Find all JSON files created after the AVMModuleMaster.csv was generated
    find "$output_dir" -type f -newer "$avm_master_csv" -name "*.json" | while read -r file; do
        log "INFO" "  - $(basename "$file")"
    done
else
    log "WARN" "Output directory not found: $output_dir"
fi

# Phase 5: Print summary statistics
log "INFO" "Processing complete"
log "INFO" "Total modules processed: $processed_count"
log "INFO" "Total modules failed: $failed_count"
log "INFO" "Available modules: ${available_modules[*]}"
log "INFO" "Log files are available in: $script_dir/logs"

exit 0
