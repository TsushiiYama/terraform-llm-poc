provider "kreuzwerker" {
  host = "https://index.docker.io/v1/"
}

resource "docker_container" "nginx-container" {
  name   = "nginx-container"
  image  = "nginx:latest"
  ports  = ["80"]
}