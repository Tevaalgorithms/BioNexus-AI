variable "region" {
  type        = string
  description = "AWS Region for Lightsail, Cognito and the budget (record data residency in AWS-01)."
}

variable "name" {
  type    = string
  default = "bionexus-pilot"
}

variable "domain_name" {
  type        = string
  description = "Public host name, e.g. bionexus.example.com. DNS A record points to the static IP output."
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique prefix for the hosted Cognito domain."
}

variable "operator_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH (authorised operator IPs only)."
  validation {
    condition     = !contains(var.operator_cidrs, "0.0.0.0/0")
    error_message = "SSH must not be open to the whole internet."
  }
}

variable "bundle_id" {
  type        = string
  description = "Lightsail Linux (IPv4) bundle id. MVP: the 2 GB / 2 vCPU plan. List ids with `aws lightsail get-bundles` and confirm the price (see docs/costs.md)."
}

variable "monthly_budget_usd" {
  type        = number
  default     = 20
  description = "Total AWS spend you will accept per month. Alerts go to budget_alert_email."
}

variable "run_budget_usd" {
  type        = number
  default     = 0.5
  description = "Hard AI-model spend cap per investigation (applies to new runs; editable later in SSM)."
}

variable "tenant_monthly_usd" {
  type        = number
  default     = 5
  description = "AI-model spend cap per organisation per month. Provider charges are NOT on the AWS bill; also set a limit in the provider's console."
}

variable "budget_alert_email" {
  type = string
}

variable "default_model" {
  type        = string
  description = "Model id for the first configuration release; it must exist in BIONEXUS_MODELS_JSON."
}

variable "models_json" {
  type        = string
  description = "Seed model catalogue as JSON ({\"models\": [...]}) with verified prices. Admins can add more at runtime."
}

variable "fallback_model" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = { project = "bionexus", environment = "pilot" }
}
