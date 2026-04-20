##############################################################
#  Outputs — affichés après terraform apply
##############################################################

output "elastic_ip" {
  description = "IP fixe (Elastic IP) — ne change plus au redémarrage"
  value       = aws_eip.bot_eip.public_ip
}

output "ec2_public_dns" {
  description = "DNS public de l'instance EC2"
  value       = aws_instance.bot_server.public_dns
}

output "ssh_command" {
  description = "Commande SSH avec IP fixe (vockey)"
  value       = "ssh -i ~/Downloads/labsuser.pem ec2-user@${aws_eip.bot_eip.public_ip}"
}

output "s3_bucket_name" {
  description = "Nom du bucket S3 pour uploader tes docs"
  value       = aws_s3_bucket.docs_bucket.bucket
}

output "s3_upload_command" {
  description = "Commande pour uploader tes fichiers markdown/txt vers S3"
  value       = "aws s3 sync ~/Telegram/docs/ s3://${aws_s3_bucket.docs_bucket.bucket}/docs/"
}

output "bot_logs_command" {
  description = "Commande pour voir les logs du bot en live"
  value       = "ssh -i ~/Downloads/labsuser.pem ec2-user@${aws_eip.bot_eip.public_ip} 'sudo journalctl -u hermes-bot -f'"
}

output "key_reminder" {
  description = "Rappel : où télécharger la clé vockey"
  value       = "Learner Lab > AWS Details > Download PEM > labsuser.pem"
}
