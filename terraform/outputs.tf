##############################################################
#  Outputs — affichés après terraform apply
##############################################################

output "ec2_public_ip" {
  description = "IP publique de l'instance EC2"
  value       = aws_instance.bot_server.public_ip
}

output "ec2_public_dns" {
  description = "DNS public de l'instance EC2"
  value       = aws_instance.bot_server.public_dns
}

output "ssh_command" {
  description = "Commande SSH pour se connecter"
  value       = "ssh -i ../${var.project_name}-key.pem ec2-user@${aws_instance.bot_server.public_ip}"
}

output "s3_bucket_name" {
  description = "Nom du bucket S3 pour uploader tes docs"
  value       = aws_s3_bucket.docs_bucket.bucket
}

output "s3_upload_command" {
  description = "Commande pour uploader tes fichiers markdown/txt vers S3"
  value       = "aws s3 sync ../docs/ s3://${aws_s3_bucket.docs_bucket.bucket}/docs/"
}

output "bot_logs_command" {
  description = "Commande pour voir les logs du bot en live"
  value       = "ssh -i ../${var.project_name}-key.pem ec2-user@${aws_instance.bot_server.public_ip} 'sudo journalctl -u hermes-bot -f'"
}
