#!/bin/bash

# Final AVM Module Initializer Script
echo "Starting Final AVM Module Initializer..."

# Check for correct usage
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <path_to_deployment_md> [working_dir]"
  echo "  path_to_deployment_md: Path to the DEPLOYMENT.md file"
  echo "  working_dir: Optional working directory for output files (default: .github)"
  exit 1
fi

# Get the deployment file path from argument
deployment_file="$1"

# Set working directory (default to .github if not provided)
working_dir="${2:-.github}"

# Create directories
mkdir -p "$working_dir/working"
mkdir -p "$working_dir/output"
mkdir -p "$working_dir/logs"

# Define mapping for translating Azure service names to their resource types and module references
declare -A service_reference_map
service_reference_map["Azure Kubernetes Service"]="Microsoft.ContainerService/managedClusters:Azure/avm-res-containerservice-managedcluster/azurerm"
service_reference_map["Azure Container Registry"]="Microsoft.ContainerRegistry/registries:Azure/avm-res-containerregistry-registry/azurerm"
service_reference_map["Azure Cosmos DB"]="Microsoft.DocumentDB/databaseAccount:Azure/avm-res-documentdb-databaseaccount/azurerm"
service_reference_map["Azure Key Vault"]="Microsoft.KeyVault/vaults:Azure/avm-res-keyvault-vault/azurerm"
service_reference_map["Azure Application Insights"]="Microsoft.Insights/components:Azure/avm-res-insights-component/azurerm"
service_reference_map["Azure Front Door"]="Microsoft.Network/frontDoors:Azure/avm-res-network-frontdoor/azurerm"
service_reference_map["Azure Monitor"]="Microsoft.Monitor/diagnosticSettings:Azure/avm-res-monitor-diagnosticsetting/azurerm"
service_reference_map["Azure API Management"]="Microsoft.ApiManagement/service:Azure/avm-res-apimanagement-service/azurerm"
service_reference_map["Azure Cache for Redis"]="Microsoft.Cache/Redis:Azure/avm-res-cache-redis/azurerm"
service_reference_map["Resource Group"]="Microsoft.Resources/resourceGroups:Azure/avm-res-resources-resourcegroup/azurerm"

# Dynamically extract required services from DEPLOYMENT.md
echo "Extracting required Azure services from: $deployment_file"
declare -A service_map

# Check if DEPLOYMENT.md exists
if [ ! -f "$deployment_file" ]; then
  echo "Error: Deployment file not found at $deployment_file"
  exit 1
fi

# Extract core/required services section from DEPLOYMENT.md
echo "Extracting core services from the deployment file..."
core_services=$(grep -A 100 "### Azure Services Required" "$deployment_file" | 
                grep -B 100 "#### Optional Components" | 
                grep -E '^\s*[0-9]+\.\s*\*\*.*\*\*' | 
                sed -E 's/^\s*[0-9]+\.\s*\*\*([^*]+)\*\*.*/\1/' |
                tr -d '\r')

# Extract optional services section from DEPLOYMENT.md
echo "Extracting optional services from the deployment file..."
optional_services=$(grep -A 50 "#### Optional Components" "$deployment_file" | 
                    grep -E '^\s*[0-9]+\.\s*\*\*.*\*\*' | 
                    sed -E 's/^\s*[0-9]+\.\s*\*\*([^*]+)\*\*.*/\1/' |
                    tr -d '\r')

# Add Resource Group as it's always needed
echo "Adding essential Resource Group service..."
service_map["Resource Group"]="${service_reference_map["Resource Group"]}"

# Debug output
echo "Core services found:"
echo "$core_services"
echo "Optional services found:"
echo "$optional_services"

# Process core services
echo "Processing core services from deployment file..."
while IFS= read -r service; do
  # Skip empty lines
  if [[ -z "$service" ]]; then
    continue
  fi
  
  # Clean up the service name (remove parentheses and trailing spaces)
  service=$(echo "$service" | sed -E 's/ \([^)]+\)//' | xargs)
  
  if [[ -n "${service_reference_map[$service]}" ]]; then
    echo "Found core service: $service"
    service_map["$service"]="${service_reference_map[$service]}"
  else
    echo "Warning: No reference mapping found for core service: '$service'"
  fi
done <<< "$core_services"

# Process optional services
echo "Processing optional services from deployment file..."
while IFS= read -r service; do
  # Skip empty lines
  if [[ -z "$service" ]]; then
    continue
  fi
  
  # Clean up the service name (remove parentheses and trailing spaces)
  service=$(echo "$service" | sed -E 's/ \([^)]+\)//' | xargs)
  
  if [[ -n "${service_reference_map[$service]}" ]]; then
    echo "Found optional service: $service"
    service_map["$service"]="${service_reference_map[$service]}"
  else
    echo "Warning: No reference mapping found for optional service: '$service'"
  fi
done <<< "$optional_services"

echo "Identified ${#service_map[@]} services from DEPLOYMENT.md"

# Create required modules array
required_modules=()
for service in "${!service_map[@]}"; do
  module_ref=$(echo "${service_map[$service]}" | cut -d':' -f2)
  required_modules+=("$module_ref")
done

echo "Required modules: ${required_modules[*]}"

# Download CSV
csv_url="https://raw.githubusercontent.com/Azure/Azure-Verified-Modules/main/docs/static/module-indexes/TerraformResourceModules.csv"
csv_file="$working_dir/working/TerraformResourceModules.csv"
curl -L -s -o "$csv_file" "$csv_url"
echo "Downloaded CSV file to $csv_file"

# Create master CSV
master_csv="$working_dir/output/AVMModuleMaster.csv"
echo "ProviderNamespace,ResourceType,ModuleName,RepoURL,PublicRegistryReference,ModuleStatus" > "$master_csv"

# Process each module
all_modules_available=true
for module_ref in "${required_modules[@]}"; do
  echo "Processing module: $module_ref"
  
  # Extract provider namespace and resource type
  module_found=false
  for service_info in "${service_map[@]}"; do
    if [[ "$service_info" == *"$module_ref"* ]]; then
      provider_info=$(echo "$service_info" | cut -d':' -f1)
      provider_namespace=$(echo "$provider_info" | cut -d'/' -f1)
      resource_type=$(echo "$provider_info" | cut -d'/' -f2)
      module_found=true
      break
    fi
  done
  
  if [ "$module_found" = false ]; then
    echo "Warning: Could not find provider info for $module_ref"
    provider_namespace="Unknown"
    resource_type="Unknown"
  fi
  
  # Get module short name
  module_short_name=$(echo "$module_ref" | cut -d'/' -f2)
  
  # Find readable name in CSV
  module_csv_info=$(grep -i "$module_short_name" "$csv_file" | head -1)
  if [ -n "$module_csv_info" ]; then
    IFS=',' read -r csv_provider_namespace csv_resource_type readable_name csv_repo_url csv_module_status csv_registry_reference csv_remaining <<< "$module_csv_info"
  else
    readable_name="$module_short_name"
  fi
  
  # Set initial status
  module_status="Available"
  
  # Run parser
  echo "Running parser for $module_ref..."
  expected_json_file="$working_dir/output/avm_res_$(echo "$module_short_name" | cut -d'-' -f3- | tr '-' '_').json"
  
  if python3 "$working_dir/avm_module_parameter_parser.py" "$module_ref" --working-dir="$working_dir" 2>&1; then
    # Check if file was created
    if [ -f "$expected_json_file" ]; then
      echo "Successfully parsed module $module_ref"
    else
      echo "Error: Parser completed but no JSON file was created for $module_ref"
      module_status="NotAvailable"
      all_modules_available=false
    fi
  else
    echo "Error: Parser failed for $module_ref"
    module_status="NotAvailable"
    all_modules_available=false
  fi
  
  # Add to master CSV
  echo "$provider_namespace,$resource_type,$readable_name,,registry.terraform.io/$module_ref,$module_status" >> "$master_csv"
done

# Check results
if [ "$all_modules_available" != true ]; then
  echo "WARNING: Not all required modules could be parsed with the parser script"
  echo "The following modules are NOT available and will require manual intervention:"
  grep "NotAvailable" "$master_csv" || echo "No NotAvailable modules found in CSV."
  echo "Please review the logs and decide if you can proceed with the available modules only"
else
  echo "All modules were successfully parsed!"
fi

echo "AVM Module Initializer completed successfully!"
echo "Created AVMModuleMaster.csv with required modules"

# List output files
echo "Generated output files:"
ls -la "$working_dir/output/"

# Check if all available modules were successfully parsed
if [[ "$all_modules_available" != true ]]; then
  echo "WARNING: Not all required modules could be parsed with the parser script"
  echo "The following modules are NOT available and will require manual intervention:"
  grep "NotAvailable" "$master_csv" || echo "Error: Could not find modules marked as NotAvailable"
  echo "Please review the logs and decide if you can proceed with the available modules only"
  
  # Let's ask if the user wants to continue with available modules only
  read -p "Do you want to continue with available modules only? (y/n): " -r continue_answer
  if [[ ! $continue_answer =~ ^[Yy]$ ]]; then
    echo "Execution stopped. Please get the missing modules before proceeding."
    exit 1
  fi
  
  echo "Continuing with available modules only..."
else
  echo "All modules were successfully parsed!"
fi

echo "AVM Module Initializer completed successfully!"
echo "You can now proceed with Terraform deployment planning"
