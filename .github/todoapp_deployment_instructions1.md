# TodoApp Deployment with AVM Module Initializer

## AVM Module Initializer Overview

The AVM Module Initializer is an automated workflow that identifies required Azure services from the deployment documentation and initializes Azure Verified Modules (AVM) for TodoApp deployment using Terraform. This tool simplifies the process of setting up Terraform modules by:

1. Extracting required Azure services from DEPLOYMENT.md
2. Downloading the AVM module index CSV
3. For each required service, calling a Python parser to extract module input/output schemas
4. Generating a master CSV (AVMModuleMaster.csv) and JSON files for each module
5. Identifying which modules are available and which require human intervention

### Implementation Details

The AVM Module Initializer has been implemented as a Bash script (`.github/avm_module_initializer.sh`) that:

- Maps required Azure services to AVM module references
- Downloads the AVM module index CSV to a working directory
- Calls a Python parser (`.github/avm_module_parameter_parser.py`) for each required module
- Updates the `ModuleStatus` in `AVMModuleMaster.csv` based on parser results
- Provides clear feedback on unavailable modules
- Prompts for confirmation before proceeding with available modules only

### Usage

To run the AVM Module Initializer:

```bash
.github/avm_module_initializer.sh <path-to-deployment-md-file> [working-directory]
```

Example:
```bash
.github/avm_module_initializer.sh todoapp/DEPLOYMENT.md
```

### Current Module Status

The AVM Module Initializer has successfully processed the following modules:

#### Available Modules:
- Azure API Management Service (`avm-res-apimanagement-service`)
- AKS Managed Clusters (`avm-res-containerservice-managedcluster`)
- Redis Cache (`avm-res-cache-redis`)
- Application Insights (`avm-res-insights-component`)
- CosmosDB Database Account (`avm-res-documentdb-databaseaccount`)
- Resource Group (`avm-res-resources-resourcegroup`)
- Azure Container Registry (`avm-res-containerregistry-registry`)
- Key Vault (`avm-res-keyvault-vault`)

#### Unavailable Modules (Requiring Manual Intervention):
- Azure Monitor Diagnostic Settings (`avm-res-monitor-diagnosticsetting`)
- Azure Front Door (`avm-res-network-frontdoor`)

## Terraform Module Development Instructions

### Schema Validation
- Every variable in `modules/module_name/variables.tf` matches the name, type, and default value in the module's JSON file.
- Every output in `modules/module_name/outputs.tf` matches the name and type in the module's JSON file.
- No custom variables or outputs are introduced beyond the official schema.
- Variable names follow the naming convention (e.g., lowercase, underscores).
- Include error handling in `validate_schema.sh` to report mismatches clearly (e.g., missing inputs, incorrect types).

### Implementation Notes
- The AVM Module JSON files in `.github/output/` should be used as the source of truth for module schema validation
- For each module JSON file (e.g., `avm_res_keyvault_vault.json`), validate:
  - Required inputs are all present with correct types
  - Optional inputs are implemented with correct default values
  - Outputs match exactly as specified
  - Dependencies and provider versions are correctly specified
- Validate that the module source URLs in the Terraform code match the `PublicRegistryReference` column from AVMModuleMaster.csv files in /terraform/modules folder for each identified module in the AVMModuleMaster. Do not create a monolith main.tf - breakdown the deployment into various modules.
- **STRICTLY** follow the official input/output schema as defined in the module's JSON file created by the module parser script.  
  1. Use **ONLY** inputs and outputs documented in the module's JSON.
  2. Do not introduce custom inputs or outputs not defined in the module.

### Handling Unavailable Modules
For modules that are unavailable in the AVM registry:
1. Research and identify alternative modules from trusted sources
2. Document the alternatives clearly, including source URLs and any schema differences
3. Create a fallback plan for manual implementation if no suitable alternative exists
4. Ensure compatibility with the rest of the AVM-based infrastructure

## Next Steps

1. Use the generated `AVMModuleMaster.csv` and JSON files to implement Terraform modules
2. Follow the schema validation requirements strictly
3. Implement the deployment architecture as specified in the DEPLOYMENT.md file
4. Test the deployment in a non-production environment before finalizing
  3. Match input names, types, and default values exactly as specified.
  4. Match output names and types exactly as specified.

### Module Schema Adherence
The JSON schema files in .github/output contain the definitive input/output specifications for each module. These schemas must be followed exactly:
- Each JSON file follows a consistent structure with:
  - Input parameters (required and optional)
  - Output parameters
  - Module requirements (Terraform version, provider versions)
  - Submodule information (if applicable)
- When creating Terraform modules, refer to these JSON files to ensure all variables and outputs match exactly
- Pay particular attention to:
  - Variable types (string, bool, number, complex objects)
  - Default values
  - Required vs. optional parameters
  - Output structure and types

For example, the Resource Group module (avm_res_resources_resourcegroup.json) requires parameters like `name`, `location`, and has optional parameters like `lock`, `tags`, and `role_assignments` that must be implemented exactly as defined.ructure engineer. Your task is to generate production-grade Terraform configuration for deploying the TodoApp app adhering to enterprise best practices (Well Architected Framework, Azure Verified Modules).

## Requirements
- Analyse and understand the Azure Services needed to deploy the TodoApp deployment by referring the todoapp/DEPLOYMENT.md file.
- Next create and run a AVM module initializer shell script that will perform the following actions
    1. Create a list of Azure Provider Namespaces for each of the Azure Services needed to deploy the app.
    2. Download the https://raw.githubusercontent.com/Azure/Azure-Verified-Modules/main/docs/static/module-indexes/TerraformResourceModules.csv file to .github/working folder.
    3. Lookup the ModuleName column for each ProviderNamespace and check if the ModuleStatus=Available
    4. For each Module that is available run the .github/avm_module_parameter_parser.py to parse the AVM module's README.md file and extract information about required inputs, optional inputs, and outputs. The python script needs to run as - python3 .github/avm_module_parameter_parser.py Azure/[module_name]/azurerm.
    5. Check for existence of the modules JSON file in the .github/output folder. If the JSON file is missing for any module then hard fail the deployment and wait for human input.
    6. Create csv file AVMModuleMaster.csv that contains the following columns extracted from TerraformResourceModules.csv - ProviderNamespace, ResourceType, ModuleName, RepoURL, PublicRegistryReference, ModuleStatus.

### AVM Module Initializer Implementation
The AVM Module Initializer script has been successfully implemented as `.github/avm_module_initializer.sh`. This script:

- Creates necessary directories (.github/working, .github/output, .github/logs)
- Maps required Azure services to their corresponding AVM modules:
  - Azure Kubernetes Service (Microsoft.ContainerService/managedClusters)
  - Azure Container Registry (Microsoft.ContainerRegistry/registries)
  - Azure Cosmos DB (Microsoft.DocumentDB/databaseAccount)
  - Azure Key Vault (Microsoft.KeyVault/vaults)
  - Azure Application Insights (Microsoft.Insights/components)
  - Azure API Management (Microsoft.ApiManagement/service)
  - Azure Cache for Redis (Microsoft.Cache/Redis)
  - Resource Group (Microsoft.Resources/resourceGroups)
- Downloads the AVM module index CSV
- Calls the parser for each module to generate JSON schema files
- Creates AVMModuleMaster.csv with module information
- Validates that all modules are available
- Includes error handling and human intervention requirements

All modules have been successfully initialized and JSON schema files generated in the `.github/output/` directory. Each JSON file contains detailed input and output parameters that must be strictly adhered to when creating the Terraform modules.
- Run the avm_module_initializer.sh script first to ensure that we have all the required files to plan the deployment. 
- Check for existence of AVMModuleMaster.csv and the JSON files for each ModuleStatus="Available". Hard fail the deployment in case of any errors and wait for human input.

### Validation of AVM Module Initialization
The AVM module initialization has been completed and validated. The script:
- Generated AVMModuleMaster.csv in the .github/output directory
- Created JSON schema files for all required modules in the .github/output directory:
  - avm_res_apimanagement_service.json
  - avm_res_cache_redis.json
  - avm_res_containerregistry_registry.json
  - avm_res_containerservice_managedcluster.json
  - avm_res_documentdb_databaseaccount.json
  - avm_res_insights_component.json
  - avm_res_keyvault_vault.json
  - avm_res_resources_resourcegroup.json
- All modules are available and properly parsed
- The script includes error handling to require human intervention if any module cannot be parsed

The next steps are to use these schema files to generate the Terraform modules.
- Using the AVMModuleMaster.csv plan the terraform modules to be created. Create seperate main/variables/ouput tf files in /terraform/modules folder for each identified module in the AVMModuleMaster. Do not create a monolith main.tf - breakdown the deployment into various modules.
- **STRICTLY** follow the official input/output schema as defined in the module’s JSON file created by the module parser script.  
  1. Use **ONLY** inputs and outputs documented in the module’s JSON.
  2. Do not introduce custom inputs or outputs not defined in the module.
  3. Match input names, types, and default values exactly as specified.
  4. Match output names and types exactly as specified.
- Do not create any modules for Azure Services where ModuleStatus not equal to "Available". Document such modules in the README. It is ok to drop creation of such resources.
- Using the PublicRegistryReference ensure that you strictly use the latest AVM module versions.
- If additional AVM modules are required (e.g., for networking or storage), use the latest versions from the Terraform Registry and document their usage.
- All code must be properly formatted using `terraform fmt` and include comprehensive inline comments and HCL documentation blocks explaining purpose.
- Implement enterprise grade best practices using the Well Architected Guidance for each Azure Service.


## Remote Terraform State Configuration (only once if not already present)
1. Use an Azure Storage Account as the Terraform backend.
2. Deploy the storage account in a **separate resource group** (optional, controlled by a boolean variable).
3. Enable state locking using Azure Blob Storage’s lease mechanism.
4. Secure the storage account with:
   - RBAC-based access for Terraform.
   - Soft-delete and versioning enabled.
5. Provide a `backend.tf` file with a partial backend configuration, requiring user input for sensitive values (e.g., storage account name, container name).
6. Create a `init.sh` script to check for existing resources, CLI dependencies and configure the remote state only if not already present.

## Naming Conventions and Best Practices
1. Use a consistent naming convention for all resources: `<prefix>-<resource-type>-<name>-<region>` (e.g., `contoso-kv-prod-eastus`).
   - Define `prefix` and `region` as required variables with validation (e.g., regex for naming, allowed regions: `eastus`, `westus`, etc.).
2. Implement a tagging strategy:
   - Mandatory tags: `environment` (e.g., `prod`, `dev`), `owner`, `cost_center`, `created_by` (set to `terraform`).
   - Allow additional custom tags via a `map(string)` variable.
3. Define variables in `variables.tf` with:
   - Clear descriptions.
   - Type constraints (e.g., `string`, `map(string)`).
   - Validation rules (e.g., regex for naming, allowed values for regions).
4. Include comprehensive documentation:
   - Inline comments for each resource and module.
   - HCL documentation blocks for variables, outputs, and modules.
   - A `README.md` in the project root describing the project structure, usage, and prerequisites.

## Project Structure
```
terraform/
├── main.tf               # Main configuration calling modules
├── variables.tf          # Variable definitions with validation
├── terraform.tfvars      # Default variable values
├── outputs.tf            # Output definitions
├── providers.tf          # Provider configurations for multiple subscriptions
├── backend.tf            # Partial backend configuration
├── README.md             # Project documentation
├── modules/
│   ├── keyvault/         # Local module wrapping e.g. avm-res-keyvault-vault
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
├── scripts/
│   ├── init.sh           # Initialize backend infrastructure (only if not present)
│   ├── deploy.sh         # Deploy infrastructure with error handling
│   ├── validate.sh       # Run terraform validate and fmt checks
│   └── validate_schema.sh # Validate input/output schema against module README
├── outputs/
│   ├── module_name.json         # AVM Module specific json for module inputs, outputs, versions and dependencies.
│   └── AVMModuleMaster.csv      # Master CSV containing module metadata from all modules

```

## Shell Scripts
1. **`validate_schema.sh`**:
   - Programmatically validate that all versions, inputs, outputs and dependencies in `modules/module_name/` match the modules JSON schema.   
   - Validate variable types, default values, and naming conventions.
   - Log results to `schema_validation.log` and exit with appropriate codes.
2. **`validate.sh`**:
   - Run `terraform validate` and `terraform fmt -check`.
   - Check Terraform and provider version compatibility.
   - Exit with non-zero code on failure and log to `validate.log`.
3. **`init.sh`**:
   - Check if the required resources (resource group, storage account, container) already exist.
   - If they exist, skip creation and log a message.
   - If not, create the resources and generate the `backend.tf` file.
   - Use `az cli` for resource creation and authentication.
   - Check for prerequisites (e.g., `az cli`, `terraform >= 1.5.0`).
   - Log errors to a file (`init.log`) and exit with appropriate codes.
4. **`deploy.sh`**:
   - Run `terraform init`, `terraform plan`, and `terraform apply` with error handling.
   - Support optional parameters (e.g., `-var-file`, `-auto-approve`).
   - Log output to `deploy.log` and handle retries for transient errors (e.g., API rate limits).


## Schema Validation
- Every variable in `modules/module_name/variables.tf` matches the name, type, and default value in the module’s JSON file.
- Every output in `modules/module_name/outputs.tf` matches the name and type in the module’s JSON file.
- No custom variables or outputs are introduced beyond the official schema.
- Variable names follow the naming convention (e.g., lowercase, underscores).
- Include error handling in `validate_schema.sh` to report mismatches clearly (e.g., missing inputs, incorrect types).

## Script Syntax Verification
- Before running any script, verify its syntax to avoid runtime errors.
- Run `bash -n <script-name>.sh` to check for syntax errors.
- Optionally, use `shellcheck <script-name>.sh` for additional linting.
- Include these instructions in the `README.md`.

## Additional Requirements
- Support multiple environments (e.g., `dev`, `prod`) via `terraform.tfvars` files or workspace-specific configurations.
- Ensure all scripts are idempotent and handle partial failures gracefully.
- Include a `versions.tf` file to pin Terraform and provider versions.
- Provide a sample `terraform.tfvars` with example values for all variables.
- Ensure the configuration is testable:
  - Include instructions in `README.md` for running `terraform plan` and `terraform apply` in a test environment.
  - Suggest tools like `terratest` for integration testing (optional implementation).
