# TodoApp Terraform Deployment Instructions

## 1. General Terraform Best Practices

### 1.1 Target Latest Versions
- Use the latest stable Terraform version (e.g., `>= 1.9.0`) and `azurerm` provider (e.g., `~> 4.0`).
- Specify versions in `provider.tf` to ensure consistency:
  ```hcl
  terraform {
    required_version = ">= 1.9.0"
    required_providers {
      azurerm = {
        source  = "hashicorp/azurerm"
        version = "~> 4.0"
      }
    }
  }
  ```

### 1.2 Organize Code
- Structure Terraform configurations for clarity:
  - `main.tf`: Core resources and module calls.
  - `variables.tf`: Input variables with types and descriptions.
  - `outputs.tf`: Output values for module and user reference.
- Run `terraform fmt` to enforce consistent formatting.
- Use consistent naming (e.g., lowercase, underscores) for resources and variables.

### 1.3 Use Modules
- Encapsulate reusable infrastructure in `/terraform/modules/`.
- Reference modules instead of duplicating code to promote reuse and consistency.
- Example module structure:
  ```plaintext
  /terraform/modules/
    keyvault/
      main.tf
      variables.tf
      outputs.tf
  ```

### 1.4 State Management
- Use Azure Storage for remote state with locking to enable team collaboration:
  ```hcl
  terraform {
    backend "azurerm" {
      resource_group_name  = "rg-terraform-state"
      storage_account_name = "tfstate"
      container_name       = "tfstate"
      key                  = "todoapp.tfstate"
    }
  }
  ```
- Never commit state files to source control to avoid conflicts.

### 1.5 Documentation
- Generate documentation using `terraform-docs`:
  ```bash
  terraform-docs markdown . > DEPLOYMENT_README.md
  ```
- Update architecture diagrams in `/docs/diagrams/` using `terraform-visual`:
  ```bash
  terraform-visual --tf-file main.tf --output diagram.png
  ```
- Commit diagrams to `/docs/diagrams/` after significant changes.

### 1.6 Idempotency
- Ensure configurations are idempotent (multiple `terraform apply` runs yield the same result).
- Use lifecycle settings or conditional expressions to handle drift:
  ```hcl
  resource "azurerm_resource_group" "example" {
    name     = "rg-todoapp"
    location = "East US"
    lifecycle {
      ignore_changes = [tags]
    }
  }
  ```

### 1.7 Provider Selection
- Prefer `azurerm` provider for stability and broad Azure service coverage.
- Use `azapi` only for new features or unsupported resources in `azurerm`.
- Document provider choice in code comments:
  ```hcl
  # Using azapi for new Azure Front Door features not yet in azurerm
  resource "azapi_resource" "frontdoor" {
    # ...
  }
  ```

## 2. TodoApp Deployment Overview
- **Goal**: Deploy the TodoApp using Azure Verified Modules (AVM) for the required Azure Services.
- **Architecture**: Analyse the `DEPLOYMENT.md` file to determine the application deployment architecture.
- **Dependencies**: Ensure all modules are sourced from the AVM registry unless unavailable.

## 3. AVM Module Initializer Workflow
- **Purpose**: Automate AVM module discovery and schema generation for TodoApp services.
- **Run the Initializer**:
  ```bash
  .github/avm_module_initializer.sh todoapp/DEPLOYMENT.md .github/output/
  ```
- **Inputs**:
  - Path to `DEPLOYMENT.md` (required).
  - Working directory for outputs (optional, defaults to `.github/output/`).
- **Outputs**:
  - `AVMModuleMaster.csv`: Lists available/unavailable modules and their `PublicRegistryReference` URLs.
  - JSON schemas in `.github/output/` (e.g., `avm_res_keyvault_vault.json`).
- **Error Handling**:
  - Logs errors to `.github/logs/initializer.log`.
  - If the script fails (e.g., network error, missing module):
    - Retry with `--force` flag for transient issues.
    - Exit with non-zero code and notify user.
- **Validation**:
  - Verify `AVMModuleMaster.csv` includes all services from `DEPLOYMENT.md`.
  - Check JSON schemas for completeness (required inputs, outputs, types).

## 4. Module Implementation and Validation
- **Module Sourcing**:
  - For each module in `AVMModuleMaster.csv`, use the `PublicRegistryReference` URL in `/terraform/modules/*.tf`.
  - Example:
    ```hcl
    module "keyvault" {
      source  = "Azure/avm-res-keyvault-vault/azurerm"
      version = "0.1.0"
      # Inputs from .github/output/avm_res_keyvault_vault.json
      name     = var.keyvault_name
      location = var.location
    }
    ```
- **Module Parser**:
  - For each module in `AVMModuleMaster.csv`, use the `ModuleName` and `RepoURL` columns to parse the modules README.md.
  - Next read and analyse the workflow defined the module parser script `.github/avm_module_parameter_parser.py`
  - Use the parser script workflow to create the JSON schema files for each available module.
- **Schema Validation**:
  - Run `.github/validate_schema.sh` to compare `variables.tf` and `outputs.tf` against JSON schemas in `.github/output/`.
  - Ensure:
    - All required inputs are present with correct types.
    - Optional inputs have correct default values.
    - Outputs match JSON schema exactly.
    - No custom inputs/outputs are introduced.
  - Example validation command:
    ```bash
    .github/validate_schema.sh /terraform/modules/keyvault .github/output/avm_res_keyvault_vault.json
    ```

- **Dependency Management**:
  - Use `depends_on` for modules with dependencies (e.g., AKS requiring Resource Group):
    ```hcl
    module "aks" {
      source  = "Azure/avm-res-containerservice-managedcluster/azurerm"
      version = "0.1.0"
      depends_on = [module.resource_group]
    }
    ```

## 5. Testing and Deployment
- **Validation**:
  - Run the following commands in sequence:
    ```bash
    terraform fmt -check
    terraform validate
    terraform plan -out=tfplan
    ```
  - Save plan output to `.github/plans/plan.out` for review.
- **Idempotency**:
  - Run `terraform apply tfplan` in a sandbox environment.
  - Run `terraform apply` again to confirm zero changes.

- **Handle Drift**:
  - If `terraform plan` detects drift:
    - Log drifted resources to `.github/logs/drift.log`.
    - Use `lifecycle { ignore_changes = [...] }` for acceptable drift.
    - For unresolvable drift, create a GitHub issue with details.
- **Post-Deployment**:
  - Validate outputs against `DEPLOYMENT_README.md`.
  - Update diagrams in `/docs/diagrams/` using `terraform-visual`.

## 6. Instructions for GitHub Copilot
- **Task Sequence**:
  1. Read `DEPLOYMENT.md` to identify required Azure services.
  2. Run `.github/avm_module_initializer.sh` and validate outputs in `.github/output/`.
  3. Generate module configurations in `/terraform/modules/` using JSON schemas.
  4. For unavailable modules, skip and add TODO comments in `main.tf`.
  5. Run validation commands (`terraform fmt`, `validate`, `plan`) and log results to `.github/logs/`.

  
- **Error Handling**:
  - If an error occurs (e.g., missing schema, invalid module):
    - Log to `.github/logs/copilot_errors.log`.
    - Skip problematic module and continue with available modules.
    - Generate a summary report in `.github/logs/summary.txt` listing skipped modules and errors.
- **Output**:
  - Ensure all generated files (e.g., `main.tf`, `variables.tf`) adhere to JSON schemas.
  - Save `terraform plan` output to `.github/plans/plan.out`.

## 7. Maintenance and Updates
- **Module Versioning**:
  - Check `AVMModuleMaster.csv` for new module versions monthly.
  - Update module source URLs in `/terraform/modules/*.tf`:
    ```bash
    terraform init -upgrade
    ```
  - Re-run `.github/validate_schema.sh` to ensure compatibility.
- **Documentation Updates**:
  - Regenerate `DEPLOYMENT_README.md` after module changes:
    ```bash
    terraform-docs markdown . > DEPLOYMENT_README.md
    ```
  - Update diagrams in `/docs/diagrams/` after significant changes.