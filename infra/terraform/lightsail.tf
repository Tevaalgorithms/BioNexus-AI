resource "aws_lightsail_key_pair" "operator" {
  name = "${var.name}-operator"
}

resource "aws_lightsail_instance" "app" {
  name              = var.name
  availability_zone = "${var.region}a"
  blueprint_id      = "ubuntu_24_04"
  bundle_id         = var.bundle_id
  key_pair_name     = aws_lightsail_key_pair.operator.name
  user_data = templatefile("${path.module}/cloud-init.sh", {
    region          = var.region
    activation_id   = aws_ssm_activation.host.id
    activation_code = aws_ssm_activation.host.activation_code
  })
  ip_address_type = "dualstack"
}

resource "aws_lightsail_static_ip" "app" {
  name = "${var.name}-ip"
}

resource "aws_lightsail_static_ip_attachment" "app" {
  static_ip_name = aws_lightsail_static_ip.app.name
  instance_name  = aws_lightsail_instance.app.name
}

# Only HTTPS/HTTP (redirected) are public. SSH is restricted to named operator networks.
resource "aws_lightsail_instance_public_ports" "app" {
  instance_name = aws_lightsail_instance.app.name

  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
  }
  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
  }
  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
    cidrs     = var.operator_cidrs
  }
}

# Private object storage for off-host backups and artifacts (AWS-10).
resource "aws_lightsail_bucket" "backups" {
  name         = "${var.name}-backups"
  bundle_id    = "small_1_0"
  force_delete = false
}

resource "aws_lightsail_bucket_resource_access" "instance" {
  bucket_name   = aws_lightsail_bucket.backups.name
  resource_name = aws_lightsail_instance.app.name
}

# Buckets are private by default; do not add public access rules. Verify with
# `aws lightsail get-buckets` (accessRules.getObject must be "private").
