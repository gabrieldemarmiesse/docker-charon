variable TAG {default = "dev"}


group default {
  targets = ["deploy-image"]
}


target "deploy-image" {
  context = "."
  tags = ["gabrieldemarmiesse/docker-charon:${TAG}"]
}
