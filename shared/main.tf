resource "docker_container" "nginx" {
  image = "nginx:latest"
  name = "my-nginx"
}
