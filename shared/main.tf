resource "docker_image" "nginx" {
  name = "nginx:latest"
}

resource "docker_container" "nginx" {
  name  = "nginx-container"
  image = docker_image.nginx.name
  ports {
    internal = 80
    external = 8080
  }
  env = [
    "VARIABLE_NAME=value"
  ]
}

resource "docker_image" "nodejs" {
  name = "node:latest"
}

resource "docker_container" "nodejs" {
  name  = "nodejs-container"
  image = docker_image.nodejs.name
  ports {
    internal = 3000
    external = 3000
  }
  env = [
    "VARIABLE_NAME=value"
  ]
}

resource "docker_image" "mongodb" {
  name = "mongo:latest"
}

resource "docker_container" "mongodb" {
  name  = "mongodb-container"
  image = docker_image.mongodb.name
  ports {
    internal = 27017
    external = 27017
  }
  env = [
    "VARIABLE_NAME=value"
  ]
}