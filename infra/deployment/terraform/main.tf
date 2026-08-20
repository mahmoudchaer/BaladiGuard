data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
  runtime_environment = [
    { name = "APP_ENV", value = var.environment },
    { name = "APP_VERSION", value = var.app_version },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "DATABASE_BACKEND", value = "dynamodb" },
    { name = "DYNAMODB_TABLE_PREFIX", value = "${local.name}-" },
    { name = "AWS_S3_BUCKET", value = aws_s3_bucket.photos.bucket },
    { name = "DYNAMODB_ENDPOINT_URL", value = "" },
    { name = "NOTIFICATION_ADAPTER", value = "real" },
    { name = "NOTIFICATION_SANDBOX", value = var.environment == "staging" ? "true" : "false" },
    { name = "SEED_SAMPLE_TICKETS", value = "false" },
    { name = "SEED_DEMO_STAFF", value = "false" },
    { name = "OTP_DEV_PLAINTEXT_STDOUT", value = "false" },
    { name = "IMAGE_REDACTION_ENABLED", value = "true" },
    { name = "IMAGE_REDACTION_DETECTOR", value = "aws_rekognition" },
    { name = "LOG_FORMAT", value = "json" },
    { name = "METRICS_EMF", value = "true" },
    { name = "TRUST_X_FORWARDED_FOR", value = "true" },
  ]
  runtime_secrets = [
    for key in var.runtime_secret_keys : {
      name      = key
      valueFrom = "${var.runtime_secret_arn}:${key}::"
    }
  ]
  table_arn = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${local.name}-*"
}

resource "aws_vpc" "this" {
  cidr_block           = "10.${var.environment == "production" ? 20 : 10}.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "public" {
  for_each = { for index, az in local.azs : az => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(aws_vpc.this.cidr_block, 8, each.value)
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS from the internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTP redirect only"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "tasks" {
  name_prefix = "${local.name}-tasks-"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "API traffic from ALB only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ecr_repository" "backend" {
  name = "${local.name}-backend"
}

resource "aws_s3_bucket" "photos" {
  bucket = "${local.name}-report-photos-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket                  = aws_s3_bucket.photos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "photos" {
  bucket     = aws_s3_bucket.photos.id
  depends_on = [aws_s3_bucket_versioning.photos]
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

data "aws_iam_policy_document" "photos" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.photos.arn, "${aws_s3_bucket.photos.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "photos" {
  bucket = aws_s3_bucket.photos.id
  policy = data.aws_iam_policy_document.photos.json
}

resource "aws_cloudwatch_log_group" "backend" {
  for_each          = toset(["api", "ai-worker", "redaction-worker", "migration"])
  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.runtime_secret_arn }]
  })
}

resource "aws_iam_role" "runtime" {
  for_each = toset(["api", "ai-worker", "redaction-worker", "migration"])
  name     = "${local.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "runtime_dynamodb" {
  for_each = aws_iam_role.runtime
  role     = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = each.key == "migration" ? [
        "dynamodb:CreateTable", "dynamodb:DescribeTable", "dynamodb:UpdateTable",
        "dynamodb:UpdateContinuousBackups", "dynamodb:ListTagsOfResource", "dynamodb:TagResource"
        ] : [
        "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem", "dynamodb:ConditionCheckItem",
        "dynamodb:DeleteItem", "dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem",
        "dynamodb:Query", "dynamodb:Scan", "dynamodb:TransactGetItems", "dynamodb:TransactWriteItems", "dynamodb:UpdateItem"
      ]
      Resource = [local.table_arn, "${local.table_arn}/index/*"]
    }]
  })
}

resource "aws_iam_role_policy" "runtime_services" {
  for_each = { for key, role in aws_iam_role.runtime : key => role if key != "migration" }
  role     = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectTagging", "s3:PutObjectTagging"]
        Resource = "${aws_s3_bucket.photos.arn}/*"
      }],
      each.key == "api" ? [{
        Effect   = "Allow"
        Action   = ["geo:SearchPlaceIndexForPosition", "geo:SearchPlaceIndexForText", "ses:SendEmail", "sns:Publish"]
        Resource = "*"
      }] : [],
      each.key == "ai-worker" ? [{
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-*"
      }] : [],
      each.key == "redaction-worker" ? [{
        Effect   = "Allow"
        Action   = ["rekognition:DetectFaces"]
        Resource = "*"
      }] : []
    )
  })
}

resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_lb" "api" {
  name                       = "${local.name}-api"
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = values(aws_subnet.public)[*].id
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id
  health_check {
    enabled             = true
    path                = "/health/ready"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
  }
}

resource "aws_acm_certificate" "api" {
  domain_name       = var.api_domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_acm_certificate" "admin" {
  domain_name       = var.admin_domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = { for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => dvo }
  zone_id  = var.route53_zone_id
  name     = each.value.resource_record_name
  type     = each.value.resource_record_type
  records  = [each.value.resource_record_value]
  ttl      = 60
}

resource "aws_route53_record" "admin_cert_validation" {
  for_each = { for dvo in aws_acm_certificate.admin.domain_validation_options : dvo.domain_name => dvo }
  zone_id  = var.route53_zone_id
  name     = each.value.resource_record_name
  type     = each.value.resource_record_type
  records  = [each.value.resource_record_value]
  ttl      = 60
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]
}

resource "aws_acm_certificate_validation" "admin" {
  certificate_arn         = aws_acm_certificate.admin.arn
  validation_record_fqdns = [for record in aws_route53_record.admin_cert_validation : record.fqdn]
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

locals {
  commands = {
    api              = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ai-worker        = ["python", "-m", "app.workers.ai_worker"]
    redaction-worker = ["python", "-m", "app.workers.image_redaction_worker"]
    migration        = ["python", "scripts/db/migrate.py"]
  }
  task_resources = {
    api              = { cpu = var.api_cpu, memory = var.api_memory }
    ai-worker        = { cpu = var.worker_cpu, memory = var.worker_memory }
    redaction-worker = { cpu = var.redaction_cpu, memory = var.redaction_memory }
    migration        = { cpu = var.api_cpu, memory = var.api_memory }
  }
}

# Terraform owns the task-definition *shape* (CPU, memory, IAM roles, logging, etc.)
# but uses a placeholder image so it does not create a new revision on every deploy.
# The deploy_backend.py script is the sole publisher of image-bearing revisions and
# snapshots the running service ARN for rollback.  See #328 for rationale.
resource "aws_ecs_task_definition" "backend" {
  for_each                 = local.commands
  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = local.task_resources[each.key].cpu
  memory                   = local.task_resources[each.key].memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.runtime[each.key].arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = each.key
    image        = "public.ecr.aws/docker/library/python:3.12-slim"
    command      = each.value
    essential    = true
    environment  = local.runtime_environment
    secrets      = local.runtime_secrets
    portMappings = each.key == "api" ? [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }] : []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend[each.key].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = each.key
      }
    }
    healthCheck = each.key == "api" ? {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    } : null
  }])

  lifecycle {
    ignore_changes = [container_definitions]
  }
}

resource "aws_ecs_service" "api" {
  name                              = "api"
  cluster                           = aws_ecs_cluster.this.id
  task_definition                   = aws_ecs_task_definition.backend["api"].arn
  desired_count                     = var.api_desired_count
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 60
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  network_configuration {
    subnets          = values(aws_subnet.public)[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.https]
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "worker" {
  for_each        = toset(["ai-worker", "redaction-worker"])
  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = values(aws_subnet.public)[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_route53_record" "api" {
  zone_id = var.route53_zone_id
  name    = var.api_domain_name
  type    = "A"
  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}

# Admin static hosting: private S3 origin, CloudFront OAC, HTTPS only.
resource "aws_s3_bucket" "admin" {
  bucket = "${local.name}-admin-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "admin" {
  bucket                  = aws_s3_bucket.admin.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "admin" {
  bucket = aws_s3_bucket.admin.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "admin" {
  bucket = aws_s3_bucket.admin.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_cloudfront_origin_access_control" "admin" {
  name                              = "${local.name}-admin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_response_headers_policy" "admin" {
  name = "${local.name}-admin-security"
  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

resource "aws_cloudfront_distribution" "admin" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.admin_domain_name]
  origin {
    domain_name              = aws_s3_bucket.admin.bucket_regional_domain_name
    origin_id                = "admin-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.admin.id
  }
  default_cache_behavior {
    target_origin_id           = "admin-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD", "OPTIONS"]
    compress                   = true
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.admin.id
  }
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.admin.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

data "aws_iam_policy_document" "admin" {
  statement {
    sid    = "AllowCloudFrontRead"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.admin.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.admin.arn]
    }
  }
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.admin.arn, "${aws_s3_bucket.admin.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "admin" {
  bucket = aws_s3_bucket.admin.id
  policy = data.aws_iam_policy_document.admin.json
}

resource "aws_route53_record" "admin" {
  zone_id = var.route53_zone_id
  name    = var.admin_domain_name
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.admin.domain_name
    zone_id                = aws_cloudfront_distribution.admin.hosted_zone_id
    evaluate_target_health = false
  }
}
