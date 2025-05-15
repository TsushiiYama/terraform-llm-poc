resource "docker_image" "nginx" {
  name = "nginx:latest"
}

reresource "docker_container" "nginx" {
  name = "nginx-container"
  image = docker_image.nginx.name
  ports {
    internal = 80
    external = 8080
  }
}