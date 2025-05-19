resource "docker_image" "elasticsearch" {
  name = "elasticsearch:7.16.3"
}

resource "docker_container" "elasticsearch" {
  name  = "elasticsearch-container"
  image = docker_image.elasticsearch.name
  ports {
    internal = 9200
    external = 9200
  }
  ports {
    internal = 9300
    external = 9300
  }
  env = [
    "ES_JAVA_OPTS=-Xms512m -Xmx512m"
  ]
  network_mode = "elastic-net"
  volume {
    host_path = "/path/to/data"
    container_path = "/usr/share/elasticsearch/data"
  }
}