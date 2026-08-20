resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "state" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state.json
}

resource "aws_dynamodb_table" "locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

resource "aws_ecr_repository" "backend" {
  for_each             = toset(["staging", "production"])
  name                 = "baladiguard-${each.key}-backend"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  encryption_configuration {
    encryption_type = "AES256"
  }
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  for_each   = aws_ecr_repository.backend
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the newest 30 releases"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

# Most AWS accounts already have the GitHub OIDC provider (only one is allowed
# per URL).  Set var.github_oidc_provider_arn to the existing provider ARN in
# that case; leave it empty to have this module create the provider.
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.github_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1", # GitHub (legacy)
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd", # GitHub (current)
    "a031c46782e6e6c662c2c87c76da9aa62ccabd8e", # GitHub (current)
  ]
}

locals {
  github_oidc_arn = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "github_trust" {
  for_each = toset(["staging", "production"])
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
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${each.key}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  for_each           = data.aws_iam_policy_document.github_trust
  name               = "baladiguard-${each.key}-github-deploy"
  assume_role_policy = each.value.json
}

# Least-privilege deployment role scoped to resources this module manages.
# The ECS runtime roles in the environment module remain separately scoped.
resource "aws_iam_role_policy" "deploy" {
  for_each = aws_iam_role.github_deploy
  role     = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:DescribeRepositories", "ecr:DescribeImages", "ecr:ListTagsForResource",
          "ecr:PutImage", "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImageTagMutability", "ecr:PutImageScanningConfiguration",
          "ecr:PutLifecyclePolicy", "ecr:GetLifecyclePolicy",
        ]
        Resource = [for repo in aws_ecr_repository.backend : repo.arn]
      },
      {
        Effect = "Allow"
        Action = [
          # Bucket metadata only; object reads remain separately restricted below.
          "s3:Get*",
          "s3:CreateBucket", "s3:DeleteBucket", "s3:ListBucket",
          "s3:GetAccelerateConfiguration", "s3:GetBucketAcl", "s3:GetBucketLocation",
          "s3:GetBucketObjectLockConfiguration", "s3:GetBucketVersioning",
          "s3:GetBucketEncryption", "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketCORS", "s3:GetBucketLifecycleConfiguration",
          "s3:GetBucketLogging", "s3:GetBucketNotification",
          "s3:GetBucketOwnershipControls", "s3:GetBucketPolicyStatus",
          "s3:GetBucketRequestPayment", "s3:GetBucketReplication", "s3:GetBucketWebsite",
          "s3:PutBucketVersioning", "s3:PutBucketEncryption", "s3:PutEncryptionConfiguration",
          "s3:PutBucketPublicAccessBlock", "s3:PutBucketPolicy",
          "s3:PutBucketLifecycleConfiguration", "s3:DeleteBucketLifecycleConfiguration",
          "s3:PutLifecycleConfiguration", "s3:DeleteLifecycleConfiguration",
          "s3:GetBucketPolicy", "s3:DeleteBucketPolicy",
          "s3:GetBucketTagging", "s3:PutBucketTagging",
        ]
        Resource = [
          aws_s3_bucket.state.arn,
          "arn:aws:s3:::baladiguard-*-admin-*",
          "arn:aws:s3:::baladiguard-*-report-photos-*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
        ]
        Resource = [
          "${aws_s3_bucket.state.arn}/*",
          "arn:aws:s3:::baladiguard-*-admin-*/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem",
          "dynamodb:DescribeTable",
        ]
        Resource = aws_dynamodb_table.locks.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:CreateCluster", "ecs:DeleteCluster",
          "ecs:DescribeClusters", "ecs:UpdateClusterSettings",
          "ecs:RegisterTaskDefinition", "ecs:DeregisterTaskDefinition",
          "ecs:DescribeTaskDefinition",
          "ecs:CreateService", "ecs:DeleteService",
          "ecs:UpdateService", "ecs:DescribeServices",
          "ecs:RunTask", "ecs:StopTask", "ecs:DescribeTasks",
          "ecs:ListTasks", "ecs:TagResource", "ecs:UntagResource", "ecs:ListTagsForResource",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateVpc", "ec2:DeleteVpc",
          "ec2:DescribeVpcs", "ec2:DescribeVpcAttribute", "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups", "ec2:DescribeRouteTables",
          "ec2:DescribeInternetGateways", "ec2:DescribeAvailabilityZones",
          "ec2:CreateSubnet", "ec2:DeleteSubnet",
          "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress", "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateInternetGateway", "ec2:DeleteInternetGateway",
          "ec2:AttachInternetGateway", "ec2:DetachInternetGateway",
          "ec2:CreateRoute", "ec2:DeleteRoute",
          "ec2:CreateRouteTable", "ec2:DeleteRouteTable",
          "ec2:AssociateRouteTable", "ec2:DisassociateRouteTable",
          "ec2:ModifyVpcAttribute", "ec2:ModifySubnetAttribute", "ec2:CreateTags", "ec2:DeleteTags",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:CreateTargetGroup", "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:DescribeTags",
          "elasticloadbalancing:CreateListener", "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:SetSecurityGroups",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "acm:RequestCertificate", "acm:DeleteCertificate",
          "acm:DescribeCertificate", "acm:ListCertificates", "acm:ListTagsForCertificate",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["route53:ChangeResourceRecordSets", "route53:GetHostedZone", "route53:ListResourceRecordSets"]
        Resource = "arn:aws:route53:::hostedzone/${var.route53_zone_id}"
      },
      {
        Effect   = "Allow"
        Action   = ["route53:GetChange", "route53:ListHostedZones"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution", "cloudfront:DeleteDistribution",
          "cloudfront:UpdateDistribution", "cloudfront:GetDistribution",
          "cloudfront:CreateInvalidation",
          "cloudfront:CreateOriginAccessControl", "cloudfront:DeleteOriginAccessControl",
          "cloudfront:GetOriginAccessControl",
          "cloudfront:CreateResponseHeadersPolicy", "cloudfront:DeleteResponseHeadersPolicy",
          "cloudfront:GetResponseHeadersPolicy",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy",
          "logs:ListTagsForResource",
        ]
        Resource = "arn:aws:logs:*:*:log-group:/ecs/baladiguard-*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups"]
        Resource = "*"
      },
      {
        # Terraform's provider default_tags are sent with creates across these
        # services. These actions do not support useful resource-level scoping.
        Effect = "Allow"
        Action = [
          "acm:AddTagsToCertificate", "acm:RemoveTagsFromCertificate",
          "cloudfront:TagResource", "cloudfront:UntagResource",
          "elasticloadbalancing:AddTags", "elasticloadbalancing:RemoveTags",
          "logs:TagResource", "logs:UntagResource",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:PassRole",
          "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies", "iam:TagRole",
          "iam:CreateServiceLinkedRole",
        ]
        Resource = "arn:aws:iam::*:role/baladiguard-${each.key}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity",
        ]
        Resource = "*"
      },
    ]
  })
}
