#!/usr/bin/env python3
"""
AVM Module Finder

This script analyzes a deployment CSV file containing Azure resources and identifies 
matching Azure Verified Modules (AVM) that are available for use.

The script:
1. Downloads the latest AVM modules list from GitHub
2. Parses the deployment CSV to extract Azure resource information
3. Matches resources with available AVM modules
4. Outputs a CSV file with the matched modules

Usage:
    python3 avm_module_finder.py <deployment_csv_path> [--no-cleanup] [--debug]

Author: Unknown
Date: July 3, 2025
"""

import argparse
import csv
import datetime
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

def setup_directories() -> Tuple[str, str, str]:
    """
    Create working, output, and logs directories if they don't exist.
    
    This function creates three directories in the same location as the script:
    - working: For temporary files like downloaded AVM module lists
    - output: For the final output CSV file
    - logs: For log files
    
    Returns:
        Tuple[str, str, str]: Paths to the working, output, and logs directories
    """
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create directories in the same directory as the script
    working_dir = os.path.join(script_dir, "working")
    output_dir = os.path.join(script_dir, "output")
    logs_dir = os.path.join(script_dir, "logs")
    
    # Create directories if they don't exist
    for directory in [working_dir, output_dir, logs_dir]:
        if not os.path.exists(directory):
            # We can't use logging here yet since it's not set up
            print(f"Creating directory: {directory}")
            os.makedirs(directory)
    
    return working_dir, output_dir, logs_dir

def setup_logging(logs_dir: str) -> None:
    """
    Configure and initialize the logging system.
    
    Sets up logging to both a file and the console with timestamps and log levels.
    The log file name includes a timestamp to avoid overwriting previous logs.
    
    Args:
        logs_dir (str): Directory where log files should be stored
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"avm_module_finder_{timestamp}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info(f"Logging initialized. Log file: {log_file}")

def download_avm_modules(working_dir: str) -> str:
    """
    Download the latest Azure Verified Modules CSV file from GitHub.
    
    This function fetches the current list of Terraform AVM modules from the
    official Azure Verified Modules GitHub repository.
    
    Args:
        working_dir (str): Directory where the downloaded file should be saved
        
    Returns:
        str: Path to the downloaded CSV file
        
    Raises:
        RuntimeError: If the download fails for any reason
    """
    AVM_MODULES_URL = "https://raw.githubusercontent.com/Azure/Azure-Verified-Modules/main/docs/static/module-indexes/TerraformResourceModules.csv"
    logging.info(f"Downloading AVM modules from {AVM_MODULES_URL}...")
    
    temp_file = os.path.join(working_dir, "TerraformResourceModules.csv")
    try:
        urllib.request.urlretrieve(AVM_MODULES_URL, temp_file)
        logging.info(f"Downloaded AVM modules to {temp_file}")
        return temp_file
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        raise RuntimeError(f"Failed to download AVM modules: {e}")

def load_deployment_csv(file_path: str) -> Dict[str, List[str]]:
    """
    Parse the deployment CSV file containing Azure resources.
    
    Reads a CSV file with Azure resources that need to be deployed and extracts
    the provider namespaces and resource types for matching with AVM modules.
    
    Expected CSV format:
        - Must have 'ProviderNamespace' and 'ResourceType' columns
        - Each row represents an Azure resource to be deployed
    
    Args:
        file_path (str): Path to the deployment CSV file
        
    Returns:
        Dict[str, List[str]]: Dictionary mapping provider namespaces to lists of resource types
        
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        ValueError: If the CSV format is invalid (missing required columns)
    """
    if not os.path.exists(file_path):
        logging.error(f"Error: Deployment file {file_path} does not exist.")
        raise FileNotFoundError(f"Deployment file not found: {file_path}")
    
    logging.info(f"Loading deployment data from {file_path}...")
    deployment_data = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Validate CSV format
            if 'ProviderNamespace' not in reader.fieldnames or 'ResourceType' not in reader.fieldnames:
                logging.error(f"Invalid deployment CSV format. Required columns missing: ProviderNamespace, ResourceType")
                raise ValueError("Invalid CSV format: Missing required columns.")
            
            for row in reader:
                namespace = row.get('ProviderNamespace')
                resource_type = row.get('ResourceType')
                
                if namespace and resource_type:
                    if namespace not in deployment_data:
                        deployment_data[namespace] = []
                    deployment_data[namespace].append(resource_type)
                    logging.debug(f"Found resource: {namespace}/{resource_type}")
                else:
                    logging.warning(f"Skipping row with missing data: {row}")
    except Exception as e:
        logging.error(f"Error reading deployment CSV: {e}")
        raise
    
    logging.info(f"Loaded {len(deployment_data)} provider namespaces from deployment data.")
    return deployment_data

def match_and_filter_modules(avm_modules_file: str, deployment_data: Dict[str, List[str]]) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Match Azure resources from the deployment CSV with available AVM modules.
    
    This function reads the AVM modules CSV and finds matches with the resources 
    specified in the deployment data. It filters the modules to include only those
    with a status of 'Available'.
    
    The matching process:
    1. Looks for direct matches between provider namespace and resource type
    2. Checks for known naming discrepancies using the RESOURCE_TYPE_MAPPINGS dictionary
    3. Only includes modules with status 'Available'
    
    Args:
        avm_modules_file (str): Path to the downloaded AVM modules CSV file
        deployment_data (Dict[str, List[str]]): Dictionary of provider namespaces and resource types
        
    Returns:
        Tuple[List[Dict[str, str]], List[str]]: 
            - List of matched modules (as dictionaries)
            - List of column names for the output CSV
            
    Raises:
        ValueError: If the AVM modules CSV format is invalid
    """
    logging.info("Matching modules...")
    matched_modules = []
    skipped_modules = []
    parse_errors = 0
    
    OUTPUT_COLUMNS = [
        "ProviderNamespace",
        "ResourceType",
        "ModuleName",
        "ModuleStatus",
        "RepoURL",
        "PublicRegistryReference"
    ]
    
    # Known naming discrepancies between deployment resources and AVM modules
    # Format: {(namespace, deployment_resource_type): avm_resource_type}
    RESOURCE_TYPE_MAPPINGS = {
        # Add mappings here if needed in the future
    }
    
    try:
        with open(avm_modules_file, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Validate CSV columns
            missing_columns = [col for col in OUTPUT_COLUMNS if col not in reader.fieldnames]
            if missing_columns:
                logging.error(f"AVM modules CSV is missing required columns: {missing_columns}")
                raise ValueError(f"Invalid AVM modules CSV format: Missing columns {missing_columns}")
            
            total_rows = 0
            for row in reader:
                total_rows += 1
                try:
                    namespace = row.get('ProviderNamespace')
                    resource_type = row.get('ResourceType')
                    module_status = row.get('ModuleStatus')
                    
                    if not all([namespace, resource_type, module_status]):
                        logging.warning(f"Skipping row with missing required data: {row}")
                        skipped_modules.append(f"{namespace or 'Unknown'}/{resource_type or 'Unknown'}")
                        continue
                    
                    # Check for direct match
                    direct_match = (namespace in deployment_data and 
                                    resource_type in deployment_data[namespace])
                    
                    # Check for known naming discrepancies
                    mapped_match = False
                    for deployment_types in deployment_data.get(namespace, []):
                        mapping_key = (namespace, deployment_types)
                        if mapping_key in RESOURCE_TYPE_MAPPINGS and RESOURCE_TYPE_MAPPINGS[mapping_key] == resource_type:
                            mapped_match = True
                            logging.info(f"Found mapping match: {namespace}/{deployment_types} -> {namespace}/{resource_type}")
                            break
                    
                    if direct_match or mapped_match:
                        if module_status == "Available":
                            logging.info(f"Found matching module: {namespace}/{resource_type}")
                            matched_row = {column: row.get(column, '') for column in OUTPUT_COLUMNS}
                            matched_modules.append(matched_row)
                        else:
                            logging.warning(f"Skipping module with status '{module_status}': {namespace}/{resource_type}")
                            skipped_modules.append(f"{namespace}/{resource_type}")
                except Exception as e:
                    logging.warning(f"Failed to parse module row: {e}")
                    parse_errors += 1
            
            logging.info(f"Processed {total_rows} modules, with {parse_errors} parse errors")
            if skipped_modules:
                logging.warning(f"Skipped {len(skipped_modules)} modules that weren't 'Available' or had missing data")
    except Exception as e:
        logging.error(f"Error processing AVM modules: {e}")
        raise
    
    return matched_modules, OUTPUT_COLUMNS

def write_output_csv(matched_modules: List[Dict[str, str]], output_dir: str, column_names: List[str]) -> str:
    """
    Write the matched modules to an output CSV file.
    
    Creates a CSV file named 'AVMModuleMaster.csv' in the output directory,
    containing all the matched AVM modules that are available for the 
    resources in the deployment CSV.
    
    Args:
        matched_modules (List[Dict[str, str]]): List of matched module dictionaries
        output_dir (str): Directory where the output file should be saved
        column_names (List[str]): List of column names for the CSV header
        
    Returns:
        str: Path to the output CSV file
        
    Raises:
        Exception: If there's an error writing the CSV file
    """
    output_file = os.path.join(output_dir, "AVMModuleMaster.csv")
    logging.info(f"Writing {len(matched_modules)} matched modules to {output_file}...")
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=column_names)
            writer.writeheader()
            writer.writerows(matched_modules)
        
        logging.info(f"Successfully wrote data to {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"Error writing output CSV: {e}")
        raise

def cleanup_temp_files(files_to_remove: List[str]) -> None:
    """
    Remove temporary files created during script execution.
    
    Args:
        files_to_remove (List[str]): List of file paths to be deleted
    """
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.debug(f"Removed temporary file: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {file_path}: {e}")

def main():
    """
    Main entry point for the AVM module finder script.
    
    This function:
    1. Parses command-line arguments
    2. Sets up directories and logging
    3. Downloads the latest AVM modules list
    4. Loads and processes the deployment CSV
    5. Matches resources with available AVM modules
    6. Writes the results to a CSV file
    7. Cleans up temporary files (unless --no-cleanup is specified)
    
    Command-line arguments:
        deployment_csv: Path to the deployment CSV file
        --no-cleanup: Flag to keep temporary files
        --debug: Enable debug-level logging
        
    Exit codes:
        0: Success
        1: Error
        130: User interrupted (Ctrl+C)
    """
    try:
        # Parse command-line arguments
        parser = argparse.ArgumentParser(
            description="Match Azure resources from a deployment CSV with available AVM modules.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument(
            "deployment_csv", 
            help="Path to the deployment CSV file"
        )
        parser.add_argument(
            "--no-cleanup", 
            action="store_true",
            help="Do not remove temporary files after execution"
        )
        parser.add_argument(
            "--debug", 
            action="store_true",
            help="Enable debug logging"
        )
        
        # Display help if no arguments provided
        if len(sys.argv) == 1:
            parser.print_help(sys.stderr)
            sys.exit(1)
            
        args = parser.parse_args()
        
        # Create directories first without logging (since logging isn't set up yet)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Script directory: {script_dir}")
        
        # Create required directory structure
        working_dir, output_dir, logs_dir = setup_directories()
        
        # Initialize logging system
        setup_logging(logs_dir)
        
        # Log important directories
        logging.info(f"Script directory: {script_dir}")
        logging.info(f"Working directory: {working_dir}")
        logging.info(f"Output directory: {output_dir}")
        logging.info(f"Logs directory: {logs_dir}")
        
        # Set debug level if requested
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.debug("Debug logging enabled")
        
        logging.info("Starting AVM module finder")
        
        # Convert relative paths to absolute if needed
        deployment_csv_path = args.deployment_csv
        if not os.path.isabs(deployment_csv_path):
            # If it's a relative path, consider it relative to the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            deployment_csv_path = os.path.abspath(os.path.join(script_dir, deployment_csv_path))
            logging.info(f"Converted relative path to absolute: {deployment_csv_path}")
        
        logging.info(f"Deployment CSV: {deployment_csv_path}")
        
        # Track temporary files to clean up
        temp_files = []
        
        # Step 1: Download the latest AVM modules list
        try:
            avm_modules_file = download_avm_modules(working_dir)
            temp_files.append(avm_modules_file)
        except Exception as e:
            logging.error(f"Failed to download AVM modules: {e}")
            sys.exit(1)
        
        # Step 2: Load and parse the deployment CSV file
        try:
            deployment_data = load_deployment_csv(deployment_csv_path)
        except FileNotFoundError as e:
            logging.error(f"Error: {e}")
            sys.exit(1)
        except ValueError as e:
            logging.error(f"Error in deployment CSV format: {e}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Unexpected error loading deployment CSV: {e}")
            sys.exit(1)
        
        # Log deployment data summary for verification
        logging.info("Deployment data summary:")
        for namespace, resource_types in deployment_data.items():
            logging.info(f"  {namespace}: {resource_types}")
        
        # Step 3: Match Azure resources with available AVM modules
        try:
            matched_modules, columns = match_and_filter_modules(avm_modules_file, deployment_data)
        except Exception as e:
            logging.error(f"Failed to match modules: {e}")
            sys.exit(1)
        
        # Step 4: Write the results to the output CSV file
        try:
            output_file = write_output_csv(matched_modules, output_dir, columns)
            logging.info(f"Generated output file: {output_file}")
        except Exception as e:
            logging.error(f"Failed to write output CSV: {e}")
            sys.exit(1)
        
        # Step 5: Clean up temporary files (unless --no-cleanup is specified)
        if not args.no_cleanup:
            cleanup_temp_files(temp_files)
            logging.info("Temporary files cleaned up")
        else:
            logging.info("Temporary files kept (--no-cleanup)")
        
        # Print final summary
        logging.info(f"Found {len(matched_modules)} matching AVM modules that are available.")
        logging.info("AVM module finder completed successfully")
        
    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unhandled error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
