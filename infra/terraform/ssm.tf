# All runtime configuration lives in SSM Parameter Store under one prefix. The app reads it at
# start-up and every 5 minutes (settings), so budgets and similar values change without a deploy.
# Keep the refresh interval long: each refresh decrypts every SecureString through KMS (billed per request).
data "aws_caller_identity" "current" {}

locals {
  prefix = "/bionexus/prod"

  plain = {
    AUTH_MODE                   = "cognito"
    PUBLIC_BASE_URL             = "https://${var.domain_name}"
    BIONEXUS_API_URL            = "http://api:8000"
    BIONEXUS_SOURCES            = "live"
    BIONEXUS_INLINE_WORKER      = "0"
    COGNITO_REGION              = var.region
    COGNITO_USER_POOL_ID        = aws_cognito_user_pool.main.id
    COGNITO_DOMAIN              = "${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
    COGNITO_ADMIN_CLIENT_ID     = aws_cognito_user_pool_client.app["admin"].id
    COGNITO_SCIENTIST_CLIENT_ID = aws_cognito_user_pool_client.app["scientist"].id
    BIONEXUS_DEFAULT_MODEL      = var.default_model
    BIONEXUS_MODELS_JSON        = var.models_json
    BIONEXUS_FALLBACK_MODEL     = var.fallback_model
    BIONEXUS_RUN_BUDGET_USD     = tostring(var.run_budget_usd)
    BIONEXUS_RUN_WARN_USD       = tostring(var.run_budget_usd / 2)
    BIONEXUS_RUN_MAX_CALLS      = "40"
    BIONEXUS_TENANT_MONTHLY_USD = tostring(var.tenant_monthly_usd)
  }
  # Operators may edit these in the console; Terraform must not revert them.
  tunable = toset(["BIONEXUS_RUN_BUDGET_USD", "BIONEXUS_RUN_WARN_USD", "BIONEXUS_RUN_MAX_CALLS", "BIONEXUS_TENANT_MONTHLY_USD"])
}

# Values derived from other resources stay in step with Terraform ...
resource "aws_ssm_parameter" "plain" {
  for_each = { for k, v in local.plain : k => v if !contains(local.tunable, k) }
  name     = "${local.prefix}/${each.key}"
  type     = "String"
  value    = each.value
}

# ... while the budgets operators tune are set once and never reverted.
resource "aws_ssm_parameter" "tunable" {
  for_each = { for k, v in local.plain : k => v if contains(local.tunable, k) }
  name     = "${local.prefix}/${each.key}"
  type     = "String"
  value    = each.value
  lifecycle { ignore_changes = [value] }
}

# Generated secrets. They also sit in Terraform state, so use an encrypted remote backend.
resource "random_password" "session" {
  length  = 48
  special = false
}

resource "random_password" "database" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "secret" {
  for_each = {
    SESSION_SECRET                  = random_password.session.result
    POSTGRES_PASSWORD               = random_password.database.result
    BIONEXUS_DATABASE_URL           = "postgresql://bionexus:${random_password.database.result}@db:5432/bionexus"
    COGNITO_ADMIN_CLIENT_SECRET     = aws_cognito_user_pool_client.app["admin"].client_secret
    COGNITO_SCIENTIST_CLIENT_SECRET = aws_cognito_user_pool_client.app["scientist"].client_secret
  }
  name  = "${local.prefix}/${each.key}"
  type  = "SecureString"
  value = each.value
}

# Provider keys cannot be generated: create the parameters empty-ish, then an operator sets them.
resource "aws_ssm_parameter" "provider_keys" {
  for_each = toset(["ANTHROPIC_API_KEY", "OPENAI_API_KEY"])
  name     = "${local.prefix}/${each.key}"
  type     = "SecureString"
  value    = "unset"
  lifecycle { ignore_changes = [value] }
}

# Read-only access for the running containers, limited to this prefix. Lightsail has no instance
# role, so this IAM user's access key is the one bootstrap credential: the operator creates it
# (never Terraform, so it never enters state) and installs it on the host with mode 600.
resource "aws_iam_user" "runtime" {
  name = "${var.name}-runtime-config"
}

data "aws_iam_policy_document" "runtime" {
  statement {
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${local.prefix}*"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

# The admin console's Users page creates and switches off sign-in accounts. Only these six actions,
# only on this pool. Who may use them is decided by the API: the caller must be a platform admin.
data "aws_iam_policy_document" "runtime_users" {
  statement {
    actions = [
      "cognito-idp:AdminCreateUser",
      "cognito-idp:AdminGetUser",
      "cognito-idp:AdminEnableUser",
      "cognito-idp:AdminDisableUser",
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminUserGlobalSignOut",
    ]
    resources = [aws_cognito_user_pool.main.arn]
  }
}

resource "aws_iam_user_policy" "runtime_users" {
  name   = "manage-bionexus-users"
  user   = aws_iam_user.runtime.name
  policy = data.aws_iam_policy_document.runtime_users.json
}

resource "aws_iam_user_policy" "runtime" {
  name   = "read-bionexus-parameters"
  user   = aws_iam_user.runtime.name
  policy = data.aws_iam_policy_document.runtime.json
}

moved {
  from = aws_ssm_parameter.plain["BIONEXUS_RUN_BUDGET_USD"]
  to   = aws_ssm_parameter.tunable["BIONEXUS_RUN_BUDGET_USD"]
}

moved {
  from = aws_ssm_parameter.plain["BIONEXUS_RUN_MAX_CALLS"]
  to   = aws_ssm_parameter.tunable["BIONEXUS_RUN_MAX_CALLS"]
}

moved {
  from = aws_ssm_parameter.plain["BIONEXUS_RUN_WARN_USD"]
  to   = aws_ssm_parameter.tunable["BIONEXUS_RUN_WARN_USD"]
}

moved {
  from = aws_ssm_parameter.plain["BIONEXUS_TENANT_MONTHLY_USD"]
  to   = aws_ssm_parameter.tunable["BIONEXUS_TENANT_MONTHLY_USD"]
}
