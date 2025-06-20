#!/usr/bin/env python3
"""
README.md Parser for Terraform Modules

This script parses a Terraform module's README.md file and extracts information 
about required inputs, optional inputs, and outputs, converting them to a JSON format.

Usage:
    python avm_module_parameter_parser.py [module_name]

Examples:
    python avm_module_parameter_parser.py                                  # Parse local README.md
    python avm_module_parameter_parser.py Azure/avm-res-keyvault-vault/azurerm  # Fetch and parse from registry

The script will read the README.md file (either local or from the Terraform Registry)
and generate a JSON file with the extracted information.
"""

import re
import json
import os
import sys
import time
import logging
import traceback
from typing import Dict, Any, List, Optional, Union, Tuple

# Check for required dependencies
def check_dependencies():
    missing_deps = []
    try:
        import requests
    except ImportError:
        missing_deps.append("requests")
    
    if missing_deps:
        print("Error: Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install the missing dependencies using:")
        print(f"  pip install {' '.join(missing_deps)}")
        print("\nOr for a virtual environment:")
        print("  python -m venv venv")
        print("  source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
        print(f"  pip install {' '.join(missing_deps)}")
        sys.exit(1)

# Import after dependency check
check_dependencies()
import requests

# Create necessary folders
def ensure_folders_exist():
    folders = ["working", "output"]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        logging.info(f"Ensured folder exists: {folder}")

# Configure logging
def setup_logging():
    log_folder = "logs"
    os.makedirs(log_folder, exist_ok=True)
    log_file = os.path.join(log_folder, "parser_log.txt")
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),  # Overwrite log file each run
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()
logger = logging.getLogger(__name__)

class ReadmeParser:
    """Parser for Terraform module README.md files to extract inputs and outputs."""
    
    def __init__(self, readme_path: str):
        """
        Initialize the parser with the path to the README.md file.
        
        Args:
            readme_path: Path to the README.md file
        """
        self.readme_path = readme_path
        self.content = ""
        self.required_inputs = {}
        self.optional_inputs = {}
        self.outputs = {}
        self.submodules = {}
        self.module_name = os.path.basename(readme_path).replace("_README.md", "")
        
    def read_file(self) -> str:
        """
        Read the README.md file.
        
        Returns:
            The content of the README.md file
        """
        try:
            with open(self.readme_path, 'r') as file:
                self.content = file.read()
            logger.info(f"Successfully read {self.readme_path} file")
            
            # Validate if this is a Terraform module README
            if not self.is_terraform_module_readme():
                logger.warning(f"File {self.readme_path} does not appear to be a Terraform module README")
                print(f"Warning: {self.readme_path} may not be a valid Terraform module README.")
                
            return self.content
        except FileNotFoundError:
            logger.error(f"Error: File {self.readme_path} not found.")
            return ""
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            logger.error(traceback.format_exc())
            return ""
    
    def is_terraform_module_readme(self) -> bool:
        """
        Check if the README appears to be for a Terraform module.
        
        Returns:
            True if it appears to be a Terraform module README, False otherwise
        """
        # Check for common sections in Terraform module READMEs
        terraform_indicators = [
            "## Required Inputs",
            "## Optional Inputs",
            "## Outputs",
            "## Requirements",
            "## Providers",
            "## Resources",
            "## Modules"
        ]
        
        # Count how many indicators are present
        matches = sum(1 for indicator in terraform_indicators if indicator in self.content)
        
        # Also check for terraform code blocks
        if "```hcl" in self.content or "```terraform" in self.content:
            matches += 1
            
        # If at least 2 indicators are present, it's likely a Terraform module README
        return matches >= 2
    
    def extract_section(self, section_name: str) -> str:
        """
        Extract a section from the README.md file.
        
        Args:
            section_name: The name of the section to extract, e.g., "Required Inputs"
            
        Returns:
            The content of the section as a string
        """
        pattern = rf"## {section_name}(.*?)(?:^##\s|\Z)"
        match = re.search(pattern, self.content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""
    
    def extract_hcl_block(self, text: str) -> str:
        """
        Extract HCL code block from markdown text.
        
        Args:
            text: The text containing HCL code blocks
            
        Returns:
            The HCL code block content
        """
        pattern = r"```hcl\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def parse_input_entry(self, entry: str) -> Dict[str, Any]:
        """
        Parse a single input entry from the README.md file.
        
        Args:
            entry: The text of a single input entry
            
        Returns:
            A dictionary with the parsed input information
        """
        # Extract the input name
        name_match = re.search(r"### <a name=\"input_(.*?)\"></a> \[(.*?)\]", entry)
        if not name_match:
            logger.debug(f"No name match found in input entry: {entry[:100]}...")
            return {}
        
        # Remove backslashes from input name
        input_name = name_match.group(2).replace("\\", "")
        
        # Extract the description
        desc_match = re.search(r"Description: (.*?)(?:Type:|$)", entry, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # Extract the type
        type_value = ""
        type_match = re.search(r"Type: `(.*?)`", entry)
        if type_match:
            type_value = type_match.group(1)
        
        # Extract HCL type if present - use the actual HCL content for complex types
        hcl_block = self.extract_hcl_block(entry)
        if hcl_block:
            type_value = hcl_block.strip()
        
        # Extract default value if present
        default_match = re.search(r"Default: `(.*?)`", entry)
        default_value = default_match.group(1) if default_match else None
        
        logger.debug(f"Parsed input: {input_name}")
        result = {
            "name": input_name,
            "description": description,
            "type": type_value
        }
        
        if default_value is not None:
            result["default"] = default_value
            
        return result
    
    def parse_output_entry(self, entry: str) -> Dict[str, Any]:
        """
        Parse a single output entry from the README.md file.
        
        Args:
            entry: The text of a single output entry
            
        Returns:
            A dictionary with the parsed output information
        """
        # Extract the output name
        name_match = re.search(r"### <a name=\"output_(.*?)\"></a> \[(.*?)\]", entry)
        if not name_match:
            logger.debug(f"No name match found in output entry: {entry[:100]}...")
            return {}
        
        # Remove backslashes from output name
        output_name = name_match.group(2).replace("\\", "")
        
        # Extract the description
        desc_match = re.search(r"Description: (.*?)(?:$)", entry, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        
        logger.debug(f"Parsed output: {output_name}")
        return {
            "name": output_name,
            "description": description
        }
    
    def parse_inputs_section(self, section_text: str, is_required: bool) -> Dict[str, Dict[str, Any]]:
        """
        Parse the inputs section (required or optional) of the README.md file.
        
        Args:
            section_text: The text of the inputs section
            is_required: Whether the inputs are required (True) or optional (False)
            
        Returns:
            A dictionary mapping input names to their parsed information
        """
        # Split the section into individual input entries
        entries = re.split(r"### <a name=\"input_", section_text)
        
        result = {}
        for entry in entries[1:]:  # Skip the first entry (section header)
            entry = "### <a name=\"input_" + entry  # Add back the split pattern
            parsed_entry = self.parse_input_entry(entry)
            if parsed_entry and "name" in parsed_entry:
                input_name = parsed_entry["name"]
                parsed_entry["required"] = is_required
                result[input_name] = parsed_entry
                
        return result
    
    def parse_outputs_section(self, section_text: str) -> Dict[str, Dict[str, Any]]:
        """
        Parse the outputs section of the README.md file.
        
        Args:
            section_text: The text of the outputs section
            
        Returns:
            A dictionary mapping output names to their parsed information
        """
        # Split the section into individual output entries
        entries = re.split(r"### <a name=\"output_", section_text)
        
        result = {}
        for entry in entries[1:]:  # Skip the first entry (section header)
            entry = "### <a name=\"output_" + entry  # Add back the split pattern
            parsed_entry = self.parse_output_entry(entry)
            if parsed_entry and "name" in parsed_entry:
                output_name = parsed_entry["name"]
                result[output_name] = parsed_entry
                
        return result
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the README.md file and extract required inputs, optional inputs, and outputs.
        
        Returns:
            A dictionary with the parsed information
        """
        if not self.content:
            self.read_file()
        
        # Extract sections
        requirements_section = self.extract_section("Requirements")
        required_inputs_section = self.extract_section("Required Inputs")
        optional_inputs_section = self.extract_section("Optional Inputs")
        outputs_section = self.extract_section("Outputs")
        submodules_section = self.extract_section("Submodules")
        
        # Parse sections
        self.required_inputs = self.parse_inputs_section(required_inputs_section, True)
        self.optional_inputs = self.parse_inputs_section(optional_inputs_section, False)
        self.outputs = self.parse_outputs_section(outputs_section)
        
        # Parse requirements
        module_requirements = self.parse_requirements_section(requirements_section)
        
        # Process submodules if they exist
        if submodules_section:
            logger.info("Found submodules section, looking for submodule READMEs")
            self.process_submodules(submodules_section)
        
        # Combine all inputs
        all_inputs = {**self.required_inputs, **self.optional_inputs}
        
        # Get the module name from the file path
        module_name = self.module_name
        
        # Create the new JSON structure with the module name as the top level key
        result = {
            module_name: {
                "name": module_name,
                "description": "",
                "inputs": all_inputs,
                "outputs": self.outputs
            }
        }
        
        # Add module_requirements if available
        if module_requirements:
            result[module_name]["module_requirements"] = module_requirements
        
        # Add submodules data if available
        if self.submodules:
            # The submodules data should already be in the correct format
            result[module_name]["submodules"] = self.submodules
            
        return result
        
    def parse_requirements_section(self, section: str) -> Dict[str, Any]:
        """
        Parse the Requirements section of the README.md file.
        
        Args:
            section: The Requirements section content
            
        Returns:
            A dictionary representing the module_requirements block
        """
        if not section:
            logger.debug("No Requirements section found")
            return {}
            
        logger.info("Parsing Requirements section")
        logger.debug(f"Requirements section content: {section}")
        
        # Parse requirements table
        terraform_version = None
        providers = {}
        
        # Process the requirements section line by line
        lines = section.split('\n')
        for line in lines:
            # Check for list format: "- <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) (>= 1.9, < 2.0)"
            if '<a name="requirement_' in line and '(' in line and ')' in line:
                # Extract the requirement name
                name_match = re.search(r'<a name="requirement_([^"]+)"></a>', line)
                if not name_match:
                    continue
                
                req_name = name_match.group(1)
                
                # Extract version from the parentheses at the end of the line
                version_match = re.search(r'\(([^)]+)\)$', line.strip())
                if not version_match:
                    continue
                    
                req_version = version_match.group(1).strip()
                logger.debug(f"Found requirement: {req_name}, version: {req_version}")
                
                # Handle terraform requirement
                if req_name == "terraform":
                    terraform_version = req_version
                # Handle provider requirements
                else:
                    # Create provider entry
                    providers[req_name] = {
                        "source": f"hashicorp/{req_name}",  # Default source
                        "version": req_version
                    }
                    
                    # Handle special case for modtm provider
                    if req_name == "modtm":
                        providers[req_name]["source"] = "azure/modtm"
        
        # Construct the module_requirements structure
        module_requirements = {}
        
        if terraform_version or providers:
            terraform_block = {}
            
            if terraform_version:
                terraform_block["required_version"] = terraform_version
                
            if providers:
                terraform_block["required_providers"] = providers
                
            module_requirements["terraform"] = terraform_block
            
        return module_requirements
        
    def process_submodules(self, submodules_section: str) -> None:
        """
        Process submodules mentioned in the README.
        
        Args:
            submodules_section: The section of the README that mentions submodules
        """
        # Extract submodule names using a regular expression
        submodule_pattern = r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"|(?:^|\n)-\s+[`'\"]?([^:`'\"\n]+)[`'\"]?(?::|$)"
        submodule_matches = re.finditer(submodule_pattern, submodules_section, re.MULTILINE)
        
        base_dir = os.path.dirname(self.readme_path)
        
        for match in submodule_matches:
            # Find the first non-None group (the submodule name)
            submodule_name = next((g for g in match.groups() if g is not None), None)
            if not submodule_name:
                continue
                
            logger.info(f"Found potential submodule: {submodule_name}")
            
            # Check for README in modules/{submodule_name} directory
            potential_paths = [
                os.path.join(base_dir, "modules", submodule_name, "README.md"),
                os.path.join(base_dir, submodule_name, "README.md"),
                os.path.join(base_dir, "modules", submodule_name, "README.md")
            ]
            
            submodule_readme_path = None
            for path in potential_paths:
                if os.path.exists(path):
                    submodule_readme_path = path
                    logger.info(f"Found README for submodule '{submodule_name}' at: {path}")
                    break
            
            if not submodule_readme_path:
                logger.warning(f"Could not find README for submodule '{submodule_name}'")
                continue
            
            # Parse the submodule README
            try:
                # Create a new parser for the submodule
                submodule_parser = ReadmeParser(submodule_readme_path)
                submodule_parser.read_file()
                
                # Extract sections from the submodule README
                required_inputs = submodule_parser.extract_section("Required Inputs")
                optional_inputs = submodule_parser.extract_section("Optional Inputs")
                outputs = submodule_parser.extract_section("Outputs")
                
                # Parse the sections
                req_inputs_data = submodule_parser.parse_inputs_section(required_inputs, True)
                opt_inputs_data = submodule_parser.parse_inputs_section(optional_inputs, False)
                outputs_data = submodule_parser.parse_outputs_section(outputs)
                
                # Combine all inputs
                all_inputs = {**req_inputs_data, **opt_inputs_data}
                
                # Add to the submodules dictionary
                self.submodules[submodule_name] = {
                    "name": submodule_name,
                    "inputs": all_inputs,
                    "outputs": outputs_data,
                    "description": ""
                }
                
                logger.info(f"Successfully parsed submodule '{submodule_name}'")
                logger.info(f"  - Required inputs: {len(req_inputs_data)}")
                logger.info(f"  - Optional inputs: {len(opt_inputs_data)}")
                logger.info(f"  - Outputs: {len(outputs_data)}")
                
            except Exception as e:
                logger.error(f"Error parsing submodule '{submodule_name}': {e}")
                logger.error(traceback.format_exc())
    
    def set_submodules(self, submodules_data: Dict[str, Dict[str, Any]]):
        """
        Set submodule data to be included in the parse output.
        
        Args:
            submodules_data: Dictionary of submodule data
        """
        self.submodules = submodules_data
    
    def to_json(self, output_path: str = None) -> str:
        """
        Convert the parsed information to JSON and optionally save it to a file.
        
        Args:
            output_path: Optional path to save the JSON to
            
        Returns:
            The JSON string
        """
        try:
            parsed_data = self.parse()
            if not parsed_data:
                logger.error("No data was parsed, cannot convert to JSON")
                return ""
                
            try:
                # Add debug output to check if module_requirements is in the parsed data
                if 'module_requirements' in next(iter(parsed_data.values())):
                    logger.debug(f"module_requirements is present in the parsed data for {next(iter(parsed_data.keys()))}")
                else:
                    logger.warning(f"module_requirements is NOT present in the parsed data for {next(iter(parsed_data.keys()))}")
                
                json_str = json.dumps(parsed_data, indent=2)
            except Exception as e:
                logger.error(f"Error converting data to JSON: {e}")
                logger.error(traceback.format_exc())
                return ""
            
            if output_path:
                try:
                    # Ensure output directory exists if there's a directory part
                    dir_path = os.path.dirname(output_path)
                    if dir_path:  # Only try to create the directory if there's a directory part
                        os.makedirs(dir_path, exist_ok=True)
                    
                    with open(output_path, 'w') as file:
                        file.write(json_str)
                    logger.info(f"JSON data written to {output_path}")
                except Exception as e:
                    logger.error(f"Error writing to file {output_path}: {e}")
                    logger.error(traceback.format_exc())
                    return json_str  # Return the JSON string even if file write fails
            
            return json_str
        except Exception as e:
            logger.error(f"Unexpected error in to_json: {e}")
            logger.error(traceback.format_exc())
            return ""

class TerraformRegistryFetcher:
    """Class to fetch module information from Terraform Registry."""
    
    def __init__(self, module_name: str):
        """
        Initialize the fetcher with a module name.
        
        Args:
            module_name: The module name in the format "namespace/name/provider"
        """
        self.module_name = module_name
        self.namespace, self.name, self.provider = self._parse_module_name(module_name)
        self.registry_base_url = "https://registry.terraform.io"
        self.github_raw_base_url = "https://raw.githubusercontent.com"
        self.github_repo = None
        self.source_url = None
        self.repo_branch = None  # Will store the default branch (main or master)
    
    def _parse_module_name(self, module_name: str) -> Tuple[str, str, str]:
        """
        Parse the module name into namespace, name, and provider.
        
        Args:
            module_name: The module name in the format "namespace/name/provider"
            
        Returns:
            A tuple of (namespace, name, provider)
        """
        parts = module_name.split('/')
        if len(parts) != 3:
            raise ValueError(
                f"Invalid module name: {module_name}. Expected format: namespace/name/provider"
            )
        return parts[0], parts[1], parts[2]
    
    def _get_registry_module_url(self) -> str:
        """
        Get the URL for the module in the Terraform Registry.
        
        Returns:
            The URL for the module in the Terraform Registry
        """
        return f"{self.registry_base_url}/modules/{self.namespace}/{self.name}/{self.provider}/latest"
    
    def _get_registry_api_url(self) -> str:
        """
        Get the API URL for the module in the Terraform Registry.
        
        Returns:
            The API URL for the module in the Terraform Registry
        """
        return f"{self.registry_base_url}/v1/modules/{self.namespace}/{self.name}/{self.provider}"
    
    def fetch_module_source(self) -> Optional[str]:
        """
        Fetch the module source repository URL from the Terraform Registry.
        
        Returns:
            The module source repository URL, or None if not found
        """
        api_url = self._get_registry_api_url()
        logger.info(f"Fetching module information from: {api_url}")
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            module_data = response.json()
            
            # Extract the source URL from the API response
            source_url = module_data.get("source", "")
            if not source_url:
                logger.error("Module source URL not found in the API response")
                return None
                
            logger.info(f"Module source URL: {source_url}")
            return source_url
        except requests.RequestException as e:
            logger.error(f"Error fetching module source: {e}")
            return None
    
    def extract_github_repo(self, source_url: str) -> Optional[str]:
        """
        Extract the GitHub repository from the source URL.
        
        Args:
            source_url: The source URL from the Terraform Registry
            
        Returns:
            The GitHub repository in the format "owner/repo", or None if not a GitHub repo
        """
        # Common GitHub URL patterns
        github_patterns = [
            r"github\.com[:/]([^/]+/[^/]+)(?:\.git)?$",
            r"github\.com/([^/]+/[^/]+)",
        ]
        
        for pattern in github_patterns:
            match = re.search(pattern, source_url)
            if match:
                repo = match.group(1)
                # Remove .git suffix if present
                repo = repo.replace(".git", "")
                logger.info(f"Extracted GitHub repository: {repo}")
                self.github_repo = repo
                self.source_url = source_url
                return repo
        
        logger.error(f"Could not extract GitHub repository from: {source_url}")
        return None
    
    def fetch_readme_content(self, github_repo: str, path: str = "") -> Optional[Tuple[str, str]]:
        """
        Fetch the README.md content from the GitHub repository.
        
        Args:
            github_repo: The GitHub repository in the format "owner/repo"
            path: Optional path to the README within the repository
            
        Returns:
            A tuple of (README content, branch used), or None if not found
        """
        # If path is provided, use it; otherwise use the root README
        if path:
            readme_path = path if path.endswith("README.md") else os.path.join(path, "README.md")
            readme_paths = [
                f"{github_repo}/main/{readme_path}",
                f"{github_repo}/master/{readme_path}",
            ]
        else:
            # Try different possible README file paths
            readme_paths = [
                f"{github_repo}/main/README.md",
                f"{github_repo}/master/README.md",
            ]
        
        for path in readme_paths:
            url = f"{self.github_raw_base_url}/{path}"
            logger.info(f"Trying to fetch README from: {url}")
            
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    logger.info(f"Successfully fetched README from: {url}")
                    # Determine which branch worked
                    branch = "main" if "main" in url else "master"
                    self.repo_branch = branch
                    return response.text, branch
            except requests.RequestException as e:
                logger.error(f"Error fetching README from {url}: {e}")
        
        logger.error(f"Could not fetch README from GitHub repository: {github_repo}, path: {path}")
        return None
    
    def fetch_and_save_readme(self) -> Optional[str]:
        """
        Fetch the README.md from the Terraform Registry and save it locally.
        
        Returns:
            The path to the saved README.md file, or None if failed
        """
        try:
            source_url = self.fetch_module_source()
            if not source_url:
                logger.error("Failed to fetch module source URL")
                return None
            
            github_repo = self.extract_github_repo(source_url)
            if not github_repo:
                logger.error("Failed to extract GitHub repository from source URL")
                return None
            
            readme_result = self.fetch_readme_content(github_repo)
            if not readme_result:
                logger.error("Failed to fetch README content from GitHub repository")
                return None
                
            readme_content, _ = readme_result
            
            # Generate a filename based on the module name
            module_filename = self.name.replace("-", "_")
            readme_filename = f"working/{module_filename}_README.md"
            
            # Save the README content to a file
            try:
                os.makedirs("working", exist_ok=True)
                with open(readme_filename, 'w') as file:
                    file.write(readme_content)
                logger.info(f"Saved README to: {readme_filename}")
                return readme_filename
            except Exception as e:
                logger.error(f"Error saving README to file: {e}")
                logger.error(traceback.format_exc())
                return None
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_save_readme: {e}")
            logger.error(traceback.format_exc())
            return None
            
    def fetch_submodule_readme(self, submodule_path: str, submodule_name: str) -> Optional[str]:
        """
        Fetch a submodule's README.md file from GitHub.
        
        Args:
            submodule_path: The path to the submodule in the repository
            submodule_name: The name of the submodule
            
        Returns:
            The path to the saved README.md file, or None if failed
        """
        try:
            if not self.github_repo:
                logger.error("GitHub repository not initialized")
                return None
                
            # Ensure path doesn't have leading/trailing slashes
            submodule_path = submodule_path.strip('/')
            
            # Handle 'Source: ./path/to/module' format - extract actual path
            if submodule_path.startswith('./'):
                submodule_path = submodule_path[2:]
            
            logger.info(f"Fetching README for submodule {submodule_name} from path: {submodule_path}")
            
            # Fetch README content
            readme_result = self.fetch_readme_content(self.github_repo, submodule_path)
            if not readme_result:
                logger.error(f"Failed to fetch README content for submodule: {submodule_name}")
                return None
                
            readme_content, _ = readme_result
            
            # Generate a unique filename for the submodule README
            module_base = self.name.replace("-", "_")
            submodule_safe_name = submodule_name.replace("-", "_").replace("/", "_")
            readme_filename = f"working/{module_base}_{submodule_safe_name}_README.md"
            
            # Save the README content to a file
            try:
                os.makedirs("working", exist_ok=True)
                with open(readme_filename, 'w') as file:
                    file.write(readme_content)
                logger.info(f"Saved submodule README to: {readme_filename}")
                return readme_filename
            except Exception as e:
                logger.error(f"Error saving submodule README to file: {e}")
                logger.error(traceback.format_exc())
                return None
        except Exception as e:
            logger.error(f"Unexpected error in fetch_submodule_readme: {e}")
            logger.error(traceback.format_exc())
            return None

def parse_readme_directly(readme_path):
    """
    Parse a README.md file directly to extract inputs and outputs.
    This is a standalone function that doesn't rely on the class structure,
    making it more robust for submodule parsing.
    
    Args:
        readme_path: Path to the README.md file
        
    Returns:
        A dictionary with parsed inputs and outputs
    """
    try:
        # Check if file exists
        if not os.path.exists(readme_path):
            logger.error(f"README file does not exist: {readme_path}")
            return {"inputs": {}, "outputs": {}}
            
        # Read the README content
        try:
            with open(readme_path, 'r') as file:
                readme_content = file.read()
        except Exception as e:
            logger.error(f"Error reading README file {readme_path}: {e}")
            logger.error(traceback.format_exc())
            return {"inputs": {}, "outputs": {}}
        
        # Create a temporary parser instance
        parser = ReadmeParser(readme_path)
        parser.content = readme_content  # Set content directly
        
        # Extract sections
        required_inputs_section = parser.extract_section("Required Inputs")
        optional_inputs_section = parser.extract_section("Optional Inputs")
        outputs_section = parser.extract_section("Outputs")
        
        # Parse sections
        required_inputs = parser.parse_inputs_section(required_inputs_section, True)
        optional_inputs = parser.parse_inputs_section(optional_inputs_section, False)
        outputs = parser.parse_outputs_section(outputs_section)
        
        # Combine all inputs
        all_inputs = {**required_inputs, **optional_inputs}
        
        logger.info(f"Parsed README {readme_path}: found {len(all_inputs)} inputs and {len(outputs)} outputs")
        logger.info(f"Required inputs: {sum(1 for inp in all_inputs.values() if inp.get('required', False))}")
        logger.info(f"Optional inputs: {sum(1 for inp in all_inputs.values() if not inp.get('required', True))}")
        
        return {
            "inputs": all_inputs,
            "outputs": outputs
        }
    except Exception as e:
        logger.error(f"Error parsing README {readme_path}: {e}")
        logger.error(traceback.format_exc())
        return {"inputs": {}, "outputs": {}}

def main():
    """Main function to execute the parser."""
    try:
        # Ensure required folders exist
        ensure_folders_exist()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        registry_fetcher = None
        
        # Check if a module name was provided as a command-line argument
        if len(sys.argv) > 1:
            module_name = sys.argv[1]
            logger.info(f"Module name provided: {module_name}")
            
            # Fetch README from Terraform Registry
            registry_fetcher = TerraformRegistryFetcher(module_name)
            readme_path = registry_fetcher.fetch_and_save_readme()
            
            if not readme_path:
                logger.error("Failed to fetch README from Terraform Registry")
                return
                
            # Use the absolute path
            readme_path = os.path.join(script_dir, readme_path)
        else:
            # Use local README.md
            working_readme = os.path.join(script_dir, "working", "README.md")
            root_readme = os.path.join(script_dir, "README.md")
            
            if os.path.exists(working_readme):
                readme_path = working_readme
            elif os.path.exists(root_readme):
                readme_path = root_readme
            else:
                logger.error("No README.md file found in working directory or root directory")
                print("Error: No README.md file found. Please provide a module name or ensure README.md exists.")
                return
                
            logger.info(f"Using local README: {readme_path}")
        
        # Derive output path from README path with new naming convention
        if "_README.md" in readme_path:
            module_name = os.path.basename(readme_path).replace("_README.md", "")
            output_path = os.path.join(script_dir, f"output/{module_name}.json")
        else:
            # Extract module name from the README content to create a more meaningful filename
            temp_parser = ReadmeParser(readme_path)
            temp_parser.read_file()
            
            # Try to extract module name from the first line or title of the README
            lines = temp_parser.content.split('\n')
            module_name = None
            
            # Look for a title pattern in the first few lines
            for line in lines[:10]:
                if line.startswith('# '):
                    # Extract module name from title, typically in format "# terraform-azurerm-avm-res-xxx-yyy"
                    title = line.strip('# ').strip()
                    if 'terraform' in title and '-' in title:
                        # Extract the last part of the module name (e.g., "keyvault-vault" from "terraform-azurerm-avm-res-keyvault-vault")
                        parts = title.split('-')
                        if len(parts) >= 3:
                            module_name = '-'.join(parts[-2:]) if len(parts) > 3 else parts[-1]
                    break
            
            # If we couldn't extract a name, use a more generic but meaningful name
            if not module_name:
                # Use the README filename or "terraform_module" as fallback
                module_name = os.path.basename(readme_path).replace(".md", "").lower() or "terraform_module"
            
            # Clean up the module name for use as a filename
            module_name = module_name.replace("-", "_").replace(" ", "_")
            output_path = os.path.join(script_dir, f"output/{module_name}.json")
        
        # Ensure output directory exists
        os.makedirs(os.path.join(script_dir, "output"), exist_ok=True)
        
        logger.info(f"README path: {readme_path}")
        logger.info(f"Output path: {output_path}")
        
        # Initialize parser and parse README
        parser = ReadmeParser(readme_path)
        
        parser.read_file()
        
        # Process submodules if registry fetcher is available
        submodules_data = {}
        if registry_fetcher and registry_fetcher.github_repo:
            logger.info("Searching for submodules...")
            
            # Extract the modules section to find submodules
            modules_section = parser.extract_section("Modules")
            if modules_section:
                logger.info("Found 'Modules' section in README")
                
                # Pattern to match module entries in the format:
                # ### <a name="module_name"></a> [name](#module\_name)
                # 
                # Source: ./path/to/module
                module_pattern = r"### <a name=\"module_(.*?)\"></a> \[(.*?)\].*?Source: (.*?)(?:\n\n|\Z)"
                
                matches = re.finditer(module_pattern, modules_section, re.DOTALL)
                submodule_infos = []
                
                for match in matches:
                    module_id = match.group(1).strip()
                    name = match.group(2).strip()
                    source_path = match.group(3).strip()
                    
                    # Clean up the path (remove ./ prefix if present)
                    if source_path.startswith('./'):
                        source_path = source_path[2:]
                        
                    logger.info(f"Found submodule: {name} at path: {source_path}")
                    
                    submodule_infos.append({
                        "id": module_id,
                        "name": name,
                        "path": source_path,
                        "description": ""  # Description might not be available in this format
                    })
                
                # Process each submodule
                for info in submodule_infos:
                    submodule_name = info["name"]
                    submodule_path = info["path"]
                    logger.info(f"Processing submodule: {submodule_name} at path: {submodule_path}")
                    
                    # Fetch and save the submodule README
                    submodule_readme_path = registry_fetcher.fetch_submodule_readme(submodule_path, submodule_name)
                    if not submodule_readme_path:
                        logger.warning(f"Failed to fetch README for submodule: {submodule_name}")
                        continue
                    
                    # Parse the submodule README directly using the standalone function
                    submodule_readme_path = os.path.join(script_dir, submodule_readme_path)
                    parsed_data = parse_readme_directly(submodule_readme_path)
                    
                    # Store the parsed data
                    submodules_data[submodule_name] = {
                        "name": submodule_name,
                        "path": submodule_path,
                        "description": info.get("description", ""),
                        "inputs": parsed_data["inputs"],
                        "outputs": parsed_data["outputs"]
                    }
            
            # If we found submodules, add them to the parser
            if submodules_data:
                logger.info(f"Found and processed {len(submodules_data)} submodules")
                parser.set_submodules(submodules_data)
        
        # Generate the parsed data with submodules included
        parsed_data = parser.parse()
        logger.info("Successfully parsed README.md content")
        
        # Print some statistics
        if parsed_data:
            module_name = next(iter(parsed_data))
            module_data = parsed_data[module_name]
            
            inputs_count = len(module_data.get("inputs", {}))
            required_inputs_count = sum(1 for input_data in module_data.get("inputs", {}).values() if input_data.get("required", False))
            optional_inputs_count = inputs_count - required_inputs_count
            outputs_count = len(module_data.get("outputs", {}))
            submodules_count = len(module_data.get("submodules", {}))
            
            logger.info(f"Statistics:")
            logger.info(f"  - Total Inputs: {inputs_count}")
            logger.info(f"    - Required Inputs: {required_inputs_count}")
            logger.info(f"    - Optional Inputs: {optional_inputs_count}")
            logger.info(f"  - Total Outputs: {outputs_count}")
            logger.info(f"  - Submodules: {submodules_count}")
            
            if submodules_count > 0:
                logger.info(f"Submodules:")
                for name, data in module_data.get("submodules", {}).items():
                    submodule_inputs = len(data.get("inputs", {}))
                    submodule_outputs = len(data.get("outputs", {}))
                    logger.info(f"  - {name}: {submodule_inputs} inputs, {submodule_outputs} outputs")
        else:
            logger.warning("No data was parsed from the README")
        
        # Generate and save JSON
        json_data = parser.to_json(output_path)
        if json_data:
            logger.info(f"Successfully generated JSON and saved to {output_path}")
            
            # Validate JSON syntax by trying to parse it
            try:
                json.loads(json_data)
                logger.info("JSON validation successful")
            except json.JSONDecodeError as e:
                logger.error(f"JSON validation failed: {e}")
            
            logger.info("Parser completed successfully")
            print(f"JSON data written to {output_path}")
        else:
            logger.error("Failed to generate JSON data")
            print("Error: Failed to generate JSON data. Check the logs for details.")
    
    except Exception as e:
        logger.error(f"Error during parsing: {e}")
        logger.error(traceback.format_exc())
        print(f"Error: An unexpected error occurred: {e}")
        print("Check the logs for more details.")
            
if __name__ == "__main__":
    # Check for help command
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("Terraform Module Parameter Parser")
        print("--------------------------------")
        print("This script extracts inputs and outputs from Terraform module README.md files.")
        print("\nUsage:")
        print("  python avm_module_parameter_parser.py [module_name]")
        print("\nExamples:")
        print("  python avm_module_parameter_parser.py                             # Parse local README.md")
        print("  python avm_module_parameter_parser.py Azure/avm-res-keyvault-vault/azurerm  # Fetch from registry")
        print("\nRequirements:")
        print("  - Python 3.6+")
        print("  - requests library (pip install requests)")
        print("\nOutput:")
        print("  JSON file will be created in the 'output' folder")
        print("  README files will be downloaded to the 'working' folder")
        sys.exit(0)
    
    try:
        # Run main function
        main()
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        sys.exit(1)
