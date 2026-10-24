# One pool, two app clients, server-enforced roles (the clients are not the authorisation boundary).
resource "aws_cognito_user_pool" "main" {
  name                     = var.name
  mfa_configuration        = "ON"
  deletion_protection      = "ACTIVE"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  software_token_mfa_configuration { enabled = true }

  admin_create_user_config {
    allow_admin_create_user_only = true # invite-only: no public registration (AUTH-01/05)
  }

  password_policy {
    minimum_length    = 14
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

locals {
  clients = {
    admin     = { callback = "https://${var.domain_name}/api/auth/callback/admin", logout = "https://${var.domain_name}/admin/login" }
    scientist = { callback = "https://${var.domain_name}/api/auth/callback/scientist", logout = "https://${var.domain_name}/login" }
  }
}

resource "aws_cognito_user_pool_client" "app" {
  for_each     = local.clients
  name         = "bionexus-${each.key}"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = true # confidential: the BFF keeps it server-side
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid"]
  callback_urls                        = [each.value.callback]
  logout_urls                          = [each.value.logout]
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 60
  refresh_token_validity               = 8
  token_validity_units {
    access_token  = "minutes"
    refresh_token = "hours"
  }
}

# Groups mirror product roles for operators' convenience; the API reads roles from its own database.
resource "aws_cognito_user_group" "roles" {
  for_each     = toset(["platform_admin", "scientist"])
  name         = each.key
  user_pool_id = aws_cognito_user_pool.main.id
}

# Branded sign-in page (classic hosted UI): logo and CSS live in ./branding and apply to every app client.
resource "aws_cognito_user_pool_ui_customization" "main" {
  user_pool_id = aws_cognito_user_pool.main.id
  css          = file("${path.module}/branding/hosted-ui.css")
  image_file   = filebase64("${path.module}/branding/logo.png")
  depends_on   = [aws_cognito_user_pool_domain.main]
}
