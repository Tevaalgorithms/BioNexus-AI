output "static_ip" { value = aws_lightsail_static_ip.app.ip_address }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.main.id }
output "cognito_domain" { value = "${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com" }
output "ssm_prefix" { value = local.prefix }
output "runtime_iam_user" { value = aws_iam_user.runtime.name }
output "backup_bucket" { value = aws_lightsail_bucket.backups.name }
