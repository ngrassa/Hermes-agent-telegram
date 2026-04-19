##############################################################
#  Hermes RAG Telegram Bot — Terraform (AWS Academy)
#  Région : us-east-1  |  Instance : t3.large
##############################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.3.0"
}

provider "aws" {
  region = var.aws_region
}

##############################################################
# Data — AMI Amazon Linux 2023 (dernière version)
##############################################################
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

##############################################################
# Keypair SSH — vockey (AWS Academy)
##############################################################
data "aws_key_pair" "vockey" {
  key_name = "vockey"
}

##############################################################
# IAM — LabInstanceProfile (préexistant, AWS Academy bloque CreateRole)
##############################################################
data "aws_iam_instance_profile" "lab_profile" {
  name = "LabInstanceProfile"
}

##############################################################
# Security Group
##############################################################
resource "aws_security_group" "bot_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group pour le bot Hermes RAG"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = var.project_name
  }
}

##############################################################
# S3 Bucket
##############################################################
resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "docs_bucket" {
  bucket        = "${var.project_name}-docs-${random_id.suffix.hex}"
  force_destroy = true
  tags          = { Project = var.project_name }
}

resource "aws_s3_bucket_versioning" "docs_versioning" {
  bucket = aws_s3_bucket.docs_bucket.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "docs_block" {
  bucket                  = aws_s3_bucket.docs_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

##############################################################
# EC2 Instance
##############################################################
resource "aws_instance" "bot_server" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.large"
  key_name               = data.aws_key_pair.vockey.key_name
  vpc_security_group_ids = [aws_security_group.bot_sg.id]
  iam_instance_profile   = data.aws_iam_instance_profile.lab_profile.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    s3_bucket      = aws_s3_bucket.docs_bucket.bucket
    aws_region     = var.aws_region
    telegram_token = var.telegram_bot_token
    groq_api_key   = var.groq_api_key
    project_name   = var.project_name
  })

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}
