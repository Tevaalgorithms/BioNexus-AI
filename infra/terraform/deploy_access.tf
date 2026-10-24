# Keyless deployment. The GitHub workflow signs in with short-lived OIDC credentials, pushes images to a private
# registry (ECR) and tells the server to deploy through AWS Systems Manager (SSM). There is no SSH key, no open
# SSH port and no stored AWS key. The server registers with SSM once, using the activation below.

variable "github_repo" {
  type        = string
  description = "GitHub repository allowed to deploy, as owner/name."
}

variable "create_github_oidc_provider" {
  type        = bool
  default     = true
  description = "Set false if this AWS account already has the GitHub OIDC provider."
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  github_oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
  image_names     = ["api", "web"]
}

# ---- Private image registry. Keeps the last 5 images; storage is about $0.10 per GB per month.
resource "aws_ecr_repository" "app" {
  for_each             = toset(local.image_names)
  name                 = "${var.name}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# ---- Lets the server take SSM commands. One-time registration code, valid for 7 days.
data "aws_iam_policy_document" "ssm_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ssm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm_host" {
  name               = "${var.name}-ssm-host"
  assume_role_policy = data.aws_iam_policy_document.ssm_trust.json
}

resource "aws_iam_role_policy_attachment" "ssm_host" {
  role       = aws_iam_role.ssm_host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_ssm_activation" "host" {
  name               = var.name
  iam_role           = aws_iam_role.ssm_host.id
  registration_limit = 1
  expiration_date    = timeadd(timestamp(), "168h")
  depends_on         = [aws_iam_role_policy_attachment.ssm_host]
  lifecycle { ignore_changes = [expiration_date] }
}

# The server's own AWS user may also pull images from the two repositories.
data "aws_iam_policy_document" "runtime_ecr" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }
}

resource "aws_iam_user_policy" "runtime_ecr" {
  name   = "pull-bionexus-images"
  user   = aws_iam_user.runtime.name
  policy = data.aws_iam_policy_document.runtime_ecr.json
}

# ---- The GitHub deploy role: push images, send one shell command to the server, read its result.
data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs that use the "production" environment of this repository (which needs manual approval).
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:production"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${var.name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
}

data "aws_iam_policy_document" "deploy_permissions" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
    ]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }
  statement {
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${var.region}::document/AWS-RunShellScript",
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:managed-instance/*",
    ]
  }
  statement {
    actions   = ["ssm:GetCommandInvocation", "ssm:DescribeInstanceInformation", "ssm:ListCommandInvocations"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy_permissions.json
}

output "deploy_role_arn" { value = aws_iam_role.deploy.arn }
output "ecr_registry" { value = split("/", aws_ecr_repository.app["api"].repository_url)[0] }
output "ssm_activation_id" { value = aws_ssm_activation.host.id }
